"""Chief Oracle agent — third tier of the multi-agent hierarchy.

Synthesises Analyzer findings every 30 simulation ticks (~15 seconds) into
actuation decisions.  Decisions are saved to the `agent_decisions` SQLite
table and made available to city_context.py for Oracle chat enrichment.
"""

import asyncio
from datetime import datetime

from database import save_agent_decision, load_recent_decisions
from memory.chroma import vector_memory
import city_tools


# How many ticks between Chief synthesis cycles
CHIEF_CYCLE_TICKS = 30
DECISION_REPEAT_COOLDOWN_TICKS = 120


class ChiefOracleAgent:
    """Rule-based synthesiser that converts Analyzer patterns into decisions."""

    def __init__(self, city_engine=None, demand_analyzer=None, congestion_analyzer=None):
        self.name = "ChiefOracleAgent"
        self.city_engine = city_engine
        self.demand_analyzer = demand_analyzer
        self.congestion_analyzer = congestion_analyzer
        self.mode = "advisor"  # "advisor" or "autopilot"
        self._cycle_count = 0
        self._last_tick = 0
        self._last_decision_ticks: dict[tuple[str, str], int] = {}
        self._tool_last_executed_at: dict[str, float] = {}

    def _emit_decision_once(
        self,
        *,
        decision_type: str,
        description: str,
        confidence: float,
        tick: int,
        cooldown_ticks: int = DECISION_REPEAT_COOLDOWN_TICKS,
    ) -> bool:
        """Persist a decision only if an identical one is not still in cooldown."""
        key = (decision_type, description)
        last_tick = self._last_decision_ticks.get(key, -cooldown_ticks)
        if tick - last_tick < cooldown_ticks:
            return False
        save_agent_decision(
            agent_name=self.name,
            decision_type=decision_type,
            description=description,
            confidence=confidence,
            tick=tick,
        )
        self._last_decision_ticks[key] = tick
        return True

    async def on_tick(self, state: dict, tick: int):
        """Called from CitySimulationEngine after Scout agents."""
        if tick - self._last_tick < CHIEF_CYCLE_TICKS:
            return
        self._last_tick = tick
        self._cycle_count += 1
        await self._synthesize(tick)

    async def _synthesize(self, tick: int):
        """Evaluate latest Analyzer findings and log decisions."""
        decisions_made = 0

        # --- Demand decision ---
        if self.demand_analyzer and self.demand_analyzer.latest_finding:
            finding = self.demand_analyzer.latest_finding
            ftype = finding.get("type", "")
            if ftype == "saturation_pattern":
                hubs = finding.get("hubs_involved", [])
                description = (
                    f"Recurring saturation on hubs {hubs}. "
                    f"Recommend activating demand-response pricing and promoting off-peak charging incentives."
                )
                if self._emit_decision_once(
                    decision_type="demand_response",
                    description=description,
                    confidence=0.85,
                    tick=tick,
                ):
                    decisions_made += 1
                    if self.mode == "autopilot" and self.city_engine:
                        try:
                            # Automatically invoke optimization when saturated
                            res = city_tools.optimize_hub_pricing(
                                self.city_engine, 
                                self._tool_last_executed_at, 
                                objective="queue_reduction"
                            )
                            print(f"[ChiefOracle] Autopilot executed optimize_hub_pricing: {res}")
                        except Exception as e:
                            print(f"[ChiefOracle] Autopilot error in optimize_hub_pricing: {e}")
            elif ftype == "demand_burst_pattern":
                max_seeking = finding.get("max_seeking", 0)
                description = (
                    f"Demand burst detected ({max_seeking} residents seeking simultaneously). "
                    f"Recommend hub capacity expansion at high-density zones and resident incentive broadcast."
                )
                if self._emit_decision_once(
                    decision_type="capacity_expansion",
                    description=description,
                    confidence=0.80,
                    tick=tick,
                ):
                    decisions_made += 1
            elif ftype == "degraded_fleet_pattern":
                description = (
                    f"Significant EV fleet battery degradation detected. "
                    f"Routing efficiency drops and charging times increase. "
                    f"Recommend prioritizing battery health preservation routines and building more charging capacity."
                )
                if self._emit_decision_once(
                    decision_type="capacity_expansion",
                    description=description,
                    confidence=0.85,
                    tick=tick,
                ):
                    decisions_made += 1
            elif ftype == "thermal_throttling_pattern":
                weather = finding.get("weather", "extreme")
                description = (
                    f"Charging rates severely limited due to {weather} weather (Thermal Throttling). "
                    f"Recommend rerouting EVs to indoor/climate-controlled hubs and reducing vehicle speeds."
                )
                if self._emit_decision_once(
                    decision_type="traffic_rerouting",
                    description=description,
                    confidence=0.92,
                    tick=tick,
                ):
                    decisions_made += 1

        # --- Congestion decision ---
        if self.congestion_analyzer and self.congestion_analyzer.latest_finding:
            finding = self.congestion_analyzer.latest_finding
            if finding.get("type") == "persistent_hotspot":
                zone = finding.get("zone")
                avg_level = finding.get("avg_level", 0)
                description = (
                    f"Persistent congestion hotspot at zone {zone} (avg {avg_level:.0%}). "
                    f"Recommend traffic rerouting algorithms and smart signal timing optimisation."
                )
                if self._emit_decision_once(
                    decision_type="traffic_rerouting",
                    description=description,
                    confidence=0.90,
                    tick=tick,
                ):
                    decisions_made += 1
                    if self.mode == "autopilot" and self.city_engine:
                        try:
                            res = city_tools.rebalance_hub_load(
                                self.city_engine, 
                                self._tool_last_executed_at, 
                                strategy="hybrid", 
                                zone=zone
                            )
                            print(f"[ChiefOracle] Autopilot executed rebalance_hub_load: {res}")
                        except Exception as e:
                            print(f"[ChiefOracle] Autopilot error in rebalance_hub_load: {e}")

        # --- Semantic recall: query ChromaDB for similar past events ---
        if decisions_made == 0:
            recalls = vector_memory.query("hub saturation demand burst congestion", n_results=2)
            if recalls:
                description = (
                    "No active patterns this cycle. "
                    f"Historical context: {recalls[0]['text'][:120]}…"
                )
                self._emit_decision_once(
                    decision_type="status_nominal",
                    description=description,
                    confidence=1.0,
                    tick=tick,
                )

    def get_latest_decisions(self, n: int = 5) -> list[dict]:
        """Return the n most recent decisions (for city_context enrichment)."""
        decisions = load_recent_decisions(limit=n)
        return decisions

    def set_mode(self, new_mode: str):
        """Set Oracle mode (advisor or autopilot)."""
        if new_mode in ("advisor", "autopilot"):
            self.mode = new_mode
            print(f"[ChiefOracle] Mode changed to {self.mode}")
