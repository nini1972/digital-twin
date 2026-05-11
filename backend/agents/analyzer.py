"""Analyzer agents — second tier of the multi-agent hierarchy.

Analyzers subscribe to Scout event channels and look for sustained patterns
across a rolling window of events.  When a pattern is confirmed they store
a structured finding in ChromaDB and expose a cache for the Chief agent.

DemandAnalyzerAgent    — detects recurring EV demand / saturation patterns.
CongestionAnalyzerAgent — detects persistent congestion hotspots.
"""

import asyncio
from collections import deque
from datetime import datetime
from typing import Deque

from redis_bus import (
    bus,
    CHANNEL_SCOUT_EV,
    CHANNEL_SCOUT_TRAFFIC,
)
from memory.chroma import vector_memory

# Maximum events retained in the rolling window
WINDOW_SIZE = 20


class DemandAnalyzerAgent:
    """Reads CHANNEL_SCOUT_EV; detects recurring demand / saturation patterns."""

    # A pattern fires when ≥N of the last WINDOW_SIZE events are of this type
    SATURATION_THRESHOLD = 3
    DEMAND_BURST_THRESHOLD = 2
    DEGRADED_FLEET_THRESHOLD = 2
    THERMAL_THROTTLING_THRESHOLD = 2

    def __init__(self):
        self.name = "DemandAnalyzerAgent"
        self._window: Deque[dict] = deque(maxlen=WINDOW_SIZE)
        self.latest_finding: dict | None = None

    async def run(self):
        queue = bus.subscribe_local(CHANNEL_SCOUT_EV)
        print("[DemandAnalyzerAgent] Listening on CHANNEL_SCOUT_EV")
        while True:
            try:
                _, data = await asyncio.wait_for(queue.get(), timeout=5.0)
                self._window.append(data)
                await self._analyze()
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                print(f"[DemandAnalyzerAgent] error: {exc}")
                await asyncio.sleep(1)

    async def _analyze(self):
        saturation_events = [e for e in self._window if e.get("event") == "hub_saturation"]
        burst_events = [e for e in self._window if e.get("event") == "demand_burst"]

        if len(saturation_events) >= self.SATURATION_THRESHOLD:
            hubs_involved = list({e["hub_id"] for e in saturation_events})
            text = (
                f"[{datetime.now().isoformat()}] Recurring hub saturation detected. "
                f"Hubs affected: {', '.join(hubs_involved)}. "
                f"{len(saturation_events)} saturation events in last {WINDOW_SIZE} ticks. "
                f"Peak ratio: {max(e.get('ratio', 0) for e in saturation_events):.0%}."
            )
            finding = {
                "type": "saturation_pattern",
                "hubs_involved": hubs_involved,
                "event_count": len(saturation_events),
                "text": text,
                "ts": datetime.now().isoformat(),
            }
            self.latest_finding = finding
            vector_memory.store("demand_saturation", text, {"hubs": str(hubs_involved)})

        if len(burst_events) >= self.DEMAND_BURST_THRESHOLD:
            max_seeking = max(e.get("seeking_count", 0) for e in burst_events)
            text = (
                f"[{datetime.now().isoformat()}] Demand burst pattern confirmed. "
                f"{len(burst_events)} burst events in last {WINDOW_SIZE} ticks. "
                f"Peak seeking count: {max_seeking} residents simultaneously searching for charge."
            )
            finding = {
                "type": "demand_burst_pattern",
                "event_count": len(burst_events),
                "max_seeking": max_seeking,
                "text": text,
                "ts": datetime.now().isoformat(),
            }
            self.latest_finding = finding
            vector_memory.store("demand_burst", text, {"max_seeking": max_seeking})

        degraded_events = [e for e in self._window if e.get("event") == "degraded_fleet"]
        if len(degraded_events) >= self.DEGRADED_FLEET_THRESHOLD:
            low_soh_count = max(e.get("low_soh_count", 0) for e in degraded_events)
            text = (
                f"[{datetime.now().isoformat()}] Degraded fleet pattern confirmed. "
                f"{len(degraded_events)} events in last {WINDOW_SIZE} ticks. "
                f"Up to {low_soh_count} EVs have severe battery degradation (SOH < 90%)."
            )
            finding = {
                "type": "degraded_fleet_pattern",
                "event_count": len(degraded_events),
                "low_soh_count": low_soh_count,
                "text": text,
                "ts": datetime.now().isoformat(),
            }
            self.latest_finding = finding
            vector_memory.store("degraded_fleet", text, {"low_soh_count": low_soh_count})

        thermal_events = [e for e in self._window if e.get("event") == "thermal_throttling"]
        if len(thermal_events) >= self.THERMAL_THROTTLING_THRESHOLD:
            weather = thermal_events[-1].get("weather", "extreme")
            affected = max(e.get("affected_count", 0) for e in thermal_events)
            text = (
                f"[{datetime.now().isoformat()}] Thermal throttling pattern confirmed. "
                f"{len(thermal_events)} events in last {WINDOW_SIZE} ticks. "
                f"Weather ({weather}) is limiting charging rates for up to {affected} EVs."
            )
            finding = {
                "type": "thermal_throttling_pattern",
                "event_count": len(thermal_events),
                "weather": weather,
                "affected_count": affected,
                "text": text,
                "ts": datetime.now().isoformat(),
            }
            self.latest_finding = finding
            vector_memory.store("thermal_throttling", text, {"weather": weather})


class CongestionAnalyzerAgent:
    """Reads CHANNEL_SCOUT_TRAFFIC; detects persistent congestion hotspots."""

    HOTSPOT_THRESHOLD = 4  # N events for same zone → persistent hotspot

    def __init__(self):
        self.name = "CongestionAnalyzerAgent"
        self._window: Deque[dict] = deque(maxlen=WINDOW_SIZE)
        self.latest_finding: dict | None = None

    async def run(self):
        queue = bus.subscribe_local(CHANNEL_SCOUT_TRAFFIC)
        print("[CongestionAnalyzerAgent] Listening on CHANNEL_SCOUT_TRAFFIC")
        while True:
            try:
                _, data = await asyncio.wait_for(queue.get(), timeout=5.0)
                self._window.append(data)
                await self._analyze()
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                print(f"[CongestionAnalyzerAgent] error: {exc}")
                await asyncio.sleep(1)

    async def _analyze(self):
        zone_counts: dict[str, list] = {}
        for e in self._window:
            if e.get("event") == "congestion_hotspot":
                zone = e["zone"]
                zone_counts.setdefault(zone, []).append(e)

        for zone, events in zone_counts.items():
            if len(events) >= self.HOTSPOT_THRESHOLD:
                avg_level = sum(e["level"] for e in events) / len(events)
                text = (
                    f"[{datetime.now().isoformat()}] Persistent congestion hotspot at zone {zone}. "
                    f"Observed {len(events)} times in last {WINDOW_SIZE} ticks. "
                    f"Average congestion level: {avg_level:.0%}. "
                    f"Recommend traffic rerouting or infrastructure review for zone {zone}."
                )
                finding = {
                    "type": "persistent_hotspot",
                    "zone": zone,
                    "event_count": len(events),
                    "avg_level": round(avg_level, 2),
                    "text": text,
                    "ts": datetime.now().isoformat(),
                }
                self.latest_finding = finding
                vector_memory.store("congestion_hotspot", text, {"zone": zone})
