"""Scout agents — first tier of the multi-agent hierarchy.

Each Scout registers as an agent_subscriber on the CitySimulationEngine and
receives every simulation tick.  On detecting a noteworthy event it publishes
a structured alert to the Redis bus (or in-process fallback).

EVScoutAgent  — watches EV hub saturation, pricing spikes, and demand bursts.
TrafficScoutAgent — watches zone congestion levels.
"""

from datetime import datetime
from redis_bus import (
    bus,
    CHANNEL_SCOUT_EV,
    CHANNEL_SCOUT_TRAFFIC,
)


class EVScoutAgent:
    """Monitors charging infrastructure metrics and publishes EV events."""

    # Thresholds
    SATURATION_RATIO = 0.8   # queue / capacity triggers saturation alert
    PRICE_SPIKE = 0.35       # $/kWh above which price is "spiked"
    DEMAND_BURST_SEEKING = 5 # ≥N residents actively seeking triggers burst

    def __init__(self):
        self.name = "EVScoutAgent"
        self._last_saturation_tick: dict[str, int] = {}

    async def on_tick(self, state: dict, tick: int):
        hubs = state.get("hubs", [])
        residents = state.get("residents", [])
        seeking = [r for r in residents if r.get("state") == "seeking"]

        for hub in hubs:
            if not hub.get("active"):
                continue
            capacity = max(1, hub.get("capacity", 3))
            queue = hub.get("queue", 0)
            price = hub.get("price", 0.0)

            if queue / capacity >= self.SATURATION_RATIO:
                last = self._last_saturation_tick.get(hub["id"], -20)
                if tick - last >= 5:  # debounce: don't spam same hub
                    self._last_saturation_tick[hub["id"]] = tick
                    await bus.publish(CHANNEL_SCOUT_EV, {
                        "event": "hub_saturation",
                        "hub_id": hub["id"],
                        "queue": queue,
                        "capacity": capacity,
                        "ratio": round(queue / capacity, 2),
                        "tick": tick,
                        "ts": datetime.now().isoformat(),
                    })

            if price >= self.PRICE_SPIKE:
                await bus.publish(CHANNEL_SCOUT_EV, {
                    "event": "price_spike",
                    "hub_id": hub["id"],
                    "price": price,
                    "tick": tick,
                    "ts": datetime.now().isoformat(),
                })

        if len(seeking) >= self.DEMAND_BURST_SEEKING:
            await bus.publish(CHANNEL_SCOUT_EV, {
                "event": "demand_burst",
                "seeking_count": len(seeking),
                "total_residents": len(residents),
                "tick": tick,
                "ts": datetime.now().isoformat(),
            })

        weather = state.get("weather", "sunny")
        low_soh_count = sum(1 for r in residents if r.get("soh", 1.0) < 0.9)
        if len(residents) > 0 and low_soh_count / len(residents) >= 0.3:
            last = self._last_saturation_tick.get("degraded_fleet", -20)
            if tick - last >= 10:
                self._last_saturation_tick["degraded_fleet"] = tick
                await bus.publish(CHANNEL_SCOUT_EV, {
                    "event": "degraded_fleet",
                    "low_soh_count": low_soh_count,
                    "tick": tick,
                    "ts": datetime.now().isoformat(),
                })

        if weather in ("extreme_cold", "extreme_heat"):
            charging_count = sum(1 for r in residents if r.get("charging"))
            if charging_count > 0:
                last = self._last_saturation_tick.get("thermal", -20)
                if tick - last >= 10:
                    self._last_saturation_tick["thermal"] = tick
                    await bus.publish(CHANNEL_SCOUT_EV, {
                        "event": "thermal_throttling",
                        "weather": weather,
                        "affected_count": charging_count,
                        "tick": tick,
                        "ts": datetime.now().isoformat(),
                    })

        # Grid wholesale price or congestion risk spikes
        wholesale_price = state.get("market_price_eur_kwh", 0.15)
        congestion_risk = str(state.get("market_congestion_risk", "LAAG")).upper()
        if wholesale_price >= 0.35 or congestion_risk in ("HOOG", "HIGH"):
            last = self._last_saturation_tick.get("grid_stress", -20)
            if tick - last >= 10:
                self._last_saturation_tick["grid_stress"] = tick
                await bus.publish(CHANNEL_SCOUT_EV, {
                    "event": "grid_stress",
                    "wholesale_price": wholesale_price,
                    "congestion_risk": congestion_risk,
                    "tick": tick,
                    "ts": datetime.now().isoformat(),
                })


class TrafficScoutAgent:
    """Monitors zone congestion and publishes traffic events."""

    HIGH_CONGESTION = 0.7  # zone congestion above this is a hotspot

    def __init__(self):
        self.name = "TrafficScoutAgent"
        self._alerted_zones: dict[str, int] = {}

    async def on_tick(self, state: dict, tick: int):
        zone_congestion: dict = state.get("zone_congestion", {})

        for zone_key, level in zone_congestion.items():
            if level >= self.HIGH_CONGESTION:
                last = self._alerted_zones.get(zone_key, -10)
                if tick - last >= 10:  # debounce
                    self._alerted_zones[zone_key] = tick
                    zx, zy = zone_key.split(",")
                    await bus.publish(CHANNEL_SCOUT_TRAFFIC, {
                        "event": "congestion_hotspot",
                        "zone": zone_key,
                        "zone_x": int(zx),
                        "zone_y": int(zy),
                        "level": round(level, 2),
                        "tick": tick,
                        "ts": datetime.now().isoformat(),
                    })
