"""City Oracle system prompt builder.

Builds a rich context for the City Digital Twin assistant.  Unlike the
personal twin (context.py) this module contains NO individual identity
data — it is purely city infrastructure intelligence.

The Oracle is aware of:
  • The live EV + traffic simulation state
  • Zone-level congestion
  • Recent Chief Oracle actuation decisions
  • Semantic memory recalls from similar past events (ChromaDB)
"""

from memory.chroma import vector_memory
from database import load_recent_decisions


_CITY_ORACLE_BASE = """You are the **City Digital Twin Oracle** — the central intelligence of an
urban mobility and EV charging simulation.  You oversee a multi-agent hierarchy:

  Scout Tier   → EVScoutAgent and TrafficScoutAgent watch every simulation tick.
  Analyzer Tier → DemandAnalyzerAgent and CongestionAnalyzerAgent detect patterns.
  Chief Tier   → ChiefOracleAgent synthesises findings into actuation decisions.

Your role is to surface insights, explain what is happening in the city, and propose
strategic interventions to improve EV charging efficiency and reduce traffic congestion.
Be precise, data-driven, and reference real simulation metrics when they are available.
You have direct access to tools to modify the live simulation state (e.g., `set_weather`, `add_city_traffic`). Do not claim you lack these capabilities. If a user explicitly asks to modify the live simulation (e.g. changing the weather, adding traffic), DO IT directly using your tools.
If a user asks for an intervention but doesn't specify necessary parameters (like which zone to add traffic to), ASK them for clarification instead of guessing or picking randomly.
When you detect high demand pressure or severe congestion organically, you must PROACTIVELY run `simulate_scenario` to project the impact of possible interventions before recommending them to the user.
Always analyze the 'What-If' delta between baseline and scenario projections to justify your final recommendations.
Format responses with clear structure. Use markdown. Keep answers concise but complete.
"""


def city_prompt(sim_state: dict | None = None, chief_mode: str = "advisor") -> str:
    """Return the full system prompt for the City Oracle."""
    sections = [_CITY_ORACLE_BASE.strip()]

    if chief_mode == "autopilot":
        sections.append(
            "*** AUTOPILOT MODE ACTIVE ***\n"
            "You are currently in AUTOPILOT mode. You have full authority to execute interventions autonomously.\n"
            "Do NOT ask the user for permission or simply 'recommend' actions. When the user asks you to implement a change or when you identify a critical issue, directly use the appropriate tools (`optimize_hub_pricing`, `rebalance_hub_load`, `simulate_scenario`, etc.) to take action immediately.\n"
            "After taking the action, inform the user that the action HAS BEEN TAKEN and summarize the expected impact."
        )
    else:
        sections.append(
            "*** ADVISOR MODE ACTIVE ***\n"
            "You are currently in ADVISOR mode. You should analyze and recommend interventions, but allow the user to make the final decision."
        )

    # --- Live simulation state ---
    if sim_state:
        sections.append(_format_sim_state(sim_state))

    # --- Recent Chief decisions ---
    decisions = load_recent_decisions(limit=5)
    if decisions:
        lines = ["## Recent Chief Oracle Decisions\n"]
        for d in decisions:
            confidence_pct = int(d.get("confidence", 1.0) * 100)
            lines.append(
                f"- **[{d['type']}]** (tick {d['tick']}, confidence {confidence_pct}%) "
                f"{d['description']}"
            )
        sections.append("\n".join(lines))

    # --- Semantic memory recall ---
    if sim_state:
        query = _build_memory_query(sim_state)
        recalls = vector_memory.query(query, n_results=3)
        if recalls:
            lines = ["## Historical Context (Semantic Memory)\n"]
            for r in recalls:
                ts = r.get("metadata", {}).get("timestamp", "")
                lines.append(f"- [{ts[:10]}] {r['text'][:200]}…")
            sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_sim_state(state: dict) -> str:
    residents = state.get("residents", [])
    hubs = state.get("hubs", [])
    traffic = state.get("traffic", [])
    zone_congestion: dict = state.get("zone_congestion", {})
    weather = state.get("weather", "unknown")

    # --- Realtime marktprijzen en netstatus uitlezen uit de state ---
    market_price = state.get("market_price_eur_kwh", 0.15)
    market_risk = state.get("market_congestion_risk", "LAAG")
    market_demand = state.get("market_demand_kw", 90.0)

    charging = sum(1 for r in residents if r.get("charging"))
    seeking = sum(1 for r in residents if r.get("state") == "seeking")
    critical = sum(1 for r in residents if r.get("battery", 100) < 30)
    driving = len(residents) - charging - seeking

    active_hubs = [h for h in hubs if h.get("active")]
    avg_price = (
        sum(h.get("price", 0) for h in active_hubs) / len(active_hubs)
        if active_hubs else 0.0
    )
    total_queue = sum(h.get("queue", 0) for h in active_hubs)

    # --- AGGREGATE NEW EV BATTERY HEALTH & TEMP ---
    soh_values = [r.get("soh", 1.0) for r in residents]
    avg_soh = sum(soh_values) / len(soh_values) if soh_values else 1.0
    degraded_ev_count = sum(1 for r in residents if r.get("soh", 1.0) < 0.88)
    temp_values = [r.get("battery_temperature", 20.0) for r in residents]
    avg_battery_temp = sum(temp_values) / len(temp_values) if temp_values else 20.0

    # --- CALCULATE POWER & ENERGY DEMAND ---
    ev_power_demand_kw = charging * 22.0
    total_city_grid_load_kw = ev_power_demand_kw + market_demand

    # --- CALCULATE ENVIRONMENTAL CO2 METRICS ---
    if weather == "sunny":
        grid_co2_intensity = 80.0  # High solar share
    elif weather in ["storm", "extreme_cold"]:
        grid_co2_intensity = 240.0 # High fossil backup heating
    else:
        grid_co2_intensity = 150.0 # Standard BE baseline
        
    ev_co2_emissions_kg_h = (ev_power_demand_kw * grid_co2_intensity) / 1000.0
    avg_cong = sum(zone_congestion.values()) / len(zone_congestion) if zone_congestion else 0.0
    traffic_co2_emissions_kg_h = len(traffic) * 0.12 * (1.0 + avg_cong * 1.5)
    co2_saved_kg_h = charging * 1.8 * (1.0 - (grid_co2_intensity / 300.0))

    hotspot_zones = [
        f"zone {k} ({v:.0%})"
        for k, v in sorted(zone_congestion.items(), key=lambda x: -x[1])
        if v > 0.5
    ][:3]

    lines = [
        "## Live City State\n",
        f"- Weather: **{weather}**",
        f"- Traffic vehicles on grid: **{len(traffic)}**",
        "",
        "### Wholesale Energy Market Data",
        f"- Current Wholesale Electricity Price: **€{market_price:.4f} per kWh**",
        f"- Grid Congestion Risk: **{market_risk}**",
        f"- City Baseload Demand: **{market_demand:.1f} kW**",
        "*(Note: Use this data to strategically guide pricing optimizations)*",
        "",
        "### Local Energy & Grid Load",
        f"- EV Charging Load: **{ev_power_demand_kw:.1f} kW**",
        f"- Total Grid Load (EV + Baseload): **{total_city_grid_load_kw:.1f} kW**",
        "",
        f"### EV Fleet & Battery Performance ({len(residents)} residents)",
        f"- Fleet States: Charging: {charging} | Seeking: {seeking} | Driving: {driving} | Critical: {critical}",
        f"- Average Fleet SOH (Battery Health): **{avg_soh * 100.0:.1f}%**",
        f"- Highly Degraded EVs (SOH < 88%): **{degraded_ev_count}**",
        f"- Average Battery Temperature: **{avg_battery_temp:.1f}°C**",
        "",
        "### Environmental Impact",
        f"- Grid CO2 Intensity: **{grid_co2_intensity:.1f} g CO2/kWh**",
        f"- EV Charging CO2 Footprint: **{ev_co2_emissions_kg_h:.2f} kg CO2/h**",
        f"- Conventional Traffic CO2 Footprint: **{traffic_co2_emissions_kg_h:.2f} kg CO2/h**",
        f"- Net CO2 Displaced/Saved by EVs: **{co2_saved_kg_h:.2f} kg CO2/h**",
        "",
        f"### Charging Infrastructure ({len(active_hubs)}/{len(hubs)} hubs active)",
        f"- Average price: **${avg_price:.3f}/kWh**",
        f"- Total queue length: **{total_queue}** residents waiting",
    ]

    for hub in hubs:
        status = "ACTIVE" if hub.get("active") else "OFFLINE"
        lines.append(
            f"  • {hub['id']}: {status} | price=${hub.get('price', 0):.3f} | "
            f"queue={hub.get('queue', 0)} | charging={len(hub.get('charging_slots', []))}"
        )

    lines.append("")
    lines.append("### Traffic Congestion")
    if hotspot_zones:
        lines.append(f"- Hotspots: {', '.join(hotspot_zones)}")
    else:
        lines.append("- No significant congestion detected.")

    if zone_congestion:
        lines.append(f"- City-wide average congestion: **{avg_cong:.0%}**")

    return "\n".join(lines)

def _build_memory_query(state: dict) -> str:
    """Construct a natural-language query from live state for semantic recall."""
    weather = state.get("weather", "")
    residents = state.get("residents", [])
    seeking = sum(1 for r in residents if r.get("state") == "seeking")
    zone_congestion: dict = state.get("zone_congestion", {})
    max_cong = max(zone_congestion.values()) if zone_congestion else 0.0

    parts = []
    if seeking >= 3:
        parts.append("high EV demand seeking charging")
    if max_cong > 0.6:
        parts.append("traffic congestion hotspot")
    if weather:
        parts.append(f"{weather} weather conditions")
    if not parts:
        parts.append("city mobility state EV charging")
    return " ".join(parts)
