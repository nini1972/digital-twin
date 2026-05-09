import copy
import unittest
from types import SimpleNamespace

import server


class FakeCityEngine:
    MIN_PRICE = 0.10
    MAX_PRICE = 0.80
    ZONE_SIZE = 20

    def __init__(self):
        self.weather = "sunny"
        self.zone_congestion = {"1,2": 0.82, "0,0": 0.21}
        self.zone_speed_limits = {}
        self.hubs = [
            SimpleNamespace(id="hub_0", queue_length=10, capacity=4, price=0.18, active=True),
            SimpleNamespace(id="hub_1", queue_length=1, capacity=4, price=0.24, active=True),
            SimpleNamespace(id="hub_2", queue_length=0, capacity=4, price=0.30, active=True),
        ]
        self.residents = [
            SimpleNamespace(id="res_0", battery=12.0, state=SimpleNamespace(value="seeking")),
            SimpleNamespace(id="res_1", battery=33.0, state=SimpleNamespace(value="waiting")),
            SimpleNamespace(id="res_2", battery=58.0, state=SimpleNamespace(value="driving")),
            SimpleNamespace(id="res_3", battery=85.0, state=SimpleNamespace(value="charging")),
        ]
        self.traffic_agents = [
            SimpleNamespace(id="traffic_0", x=25.0, y=45.0),
            SimpleNamespace(id="traffic_1", x=31.0, y=52.0),
            SimpleNamespace(id="traffic_2", x=6.0, y=8.0),
        ]

    def get_city_metrics(self):
        active_hubs = [hub for hub in self.hubs if hub.active]
        total_queue = sum(hub.queue_length for hub in active_hubs)
        avg_price = sum(hub.price for hub in active_hubs) / max(1, len(active_hubs))
        seeking_count = sum(1 for resident in self.residents if resident.state.value == "seeking")
        return {
            "active_hubs": len(active_hubs),
            "total_queue": total_queue,
            "seeking_count": seeking_count,
            "avg_congestion": sum(self.zone_congestion.values()) / len(self.zone_congestion),
            "avg_price": avg_price,
            "weather": self.weather,
        }

    def get_state(self):
        return {
            "weather": self.weather,
            "zone_congestion": copy.deepcopy(self.zone_congestion),
            "zone_speed_limits": copy.deepcopy(self.zone_speed_limits),
            "hubs": [
                {
                    "id": hub.id,
                    "price": hub.price,
                    "queue": hub.queue_length,
                    "queue_total": hub.queue_length,
                    "capacity": hub.capacity,
                    "active": hub.active,
                }
                for hub in self.hubs
            ],
            "residents": [
                {
                    "id": resident.id,
                    "battery": resident.battery,
                    "state": resident.state.value,
                    "charging": resident.state.value == "charging",
                    "x": 50.0,
                    "y": 50.0,
                }
                for resident in self.residents
            ],
            "traffic": [
                {"id": traffic.id, "x": traffic.x, "y": traffic.y}
                for traffic in self.traffic_agents
            ],
        }

    def reroute_traffic_from_zone(self, zone):
        return server._zone_population(zone)

    def set_zone_speed_limit(self, zone, multiplier):
        self.zone_speed_limits[zone] = multiplier


class CityToolTests(unittest.TestCase):
    def setUp(self):
        self.original_engine = server.city_engine
        self.original_cooldowns = dict(server._TOOL_LAST_EXECUTED_AT)
        server.city_engine = FakeCityEngine()
        server._TOOL_LAST_EXECUTED_AT.clear()

    def tearDown(self):
        server.city_engine = self.original_engine
        server._TOOL_LAST_EXECUTED_AT.clear()
        server._TOOL_LAST_EXECUTED_AT.update(self.original_cooldowns)

    def test_forecast_city_load_returns_hotspots_and_recommendations(self):
        forecast = server._forecast_city_load(horizon_ticks=60)

        self.assertEqual(forecast["projected_hotspots"][0]["zone"], "1,2")
        self.assertGreater(forecast["projected_total_queue"], 11.0)
        self.assertGreaterEqual(len(forecast["recommendations"]), 1)

    def test_analyze_resident_segments_computes_pressure_band(self):
        segments = server._analyze_resident_segments()

        self.assertEqual(segments["battery_segments"]["battery_critical"]["count"], 1)
        self.assertEqual(segments["battery_segments"]["battery_low"]["count"], 1)
        self.assertEqual(segments["state_segments"]["charging"]["count"], 1)
        self.assertEqual(segments["demand_risk_band"], "high")
        self.assertEqual(segments["charging_pressure_index"], 0.5)

    def test_evaluate_weather_impact_increases_stress_for_storm(self):
        storm = server._evaluate_weather_impact("storm", horizon_ticks=30)
        sunny = server._evaluate_weather_impact("sunny", horizon_ticks=30)

        self.assertEqual(storm["target_weather"], "storm")
        self.assertGreater(storm["weather_stress_index"], sunny["weather_stress_index"])
        self.assertGreater(storm["projected_total_queue"], sunny["projected_total_queue"])

    def test_optimize_hub_pricing_respects_bounds_and_spread(self):
        result = server.optimize_hub_pricing(
            objective="queue_reduction",
            floor=0.15,
            ceiling=0.32,
            max_delta=0.5,
            fairness_weight=0.8,
        )

        self.assertEqual(result["status"], "success")
        prices = [hub.price for hub in server.city_engine.hubs if hub.active]
        self.assertTrue(all(0.15 <= price <= 0.32 for price in prices))
        self.assertLessEqual(max(prices) - min(prices), server.MAX_PRICE_SPREAD)
        self.assertEqual(result["constraints"]["max_delta"], server.MAX_PRICE_DELTA_PER_CALL)

    def test_rebalance_hub_load_applies_bounded_actions(self):
        result = server.rebalance_hub_load(strategy="reroute", max_actions=3, zone="1,2", aggressiveness=1.0)

        self.assertEqual(result["status"], "success")
        self.assertLessEqual(len(result["applied_actions"]), 3)
        self.assertIn("1,2", {action.get("zone") for action in result["applied_actions"] if "zone" in action})
        self.assertIn("1,2", server.city_engine.zone_speed_limits)

    def test_simulate_scenario_rejects_invalid_actions(self):
        result = server.simulate_scenario([{"type": "launch_rocket"}], horizon_ticks=30, runs=2)

        self.assertEqual(result["status"], "error")
        self.assertIn("validation_errors", result)
        self.assertIn("unsupported", result["validation_errors"][0])

    def test_simulate_scenario_does_not_mutate_live_state(self):
        before = server.city_engine.get_state()

        result = server.simulate_scenario(
            [
                {"type": "set_hub_price", "hub_id": "hub_0", "price": 0.5},
                {"type": "add_city_resident", "count": 3},
                {"type": "optimize_hub_pricing", "objective": "fairness"},
                {"type": "rebalance_hub_load", "strategy": "hybrid", "zone": "1,2"},
            ],
            horizon_ticks=20,
            runs=2,
        )
        after = server.city_engine.get_state()

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["safety"]["mutates_live_state"])
        self.assertEqual(before, after)


class CityScenarioSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def test_city_scenario_schema_exposes_supported_actions(self):
        result = await server.city_scenario_schema()

        self.assertEqual(result["endpoint"], "/city/scenario/schema")
        self.assertIn("optimize_hub_pricing", result["actions"])
        self.assertEqual(result["simulate_scenario"]["max_actions"], server.MAX_TOOL_ACTIONS)


if __name__ == "__main__":
    unittest.main()