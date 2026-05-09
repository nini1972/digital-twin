import copy
import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import server
from tests.test_city_tools import FakeCityEngine


@asynccontextmanager
async def _noop_lifespan(_app):
    yield


class CityScenarioEndpointE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._original_lifespan = server.app.router.lifespan_context
        server.app.router.lifespan_context = _noop_lifespan

    @classmethod
    def tearDownClass(cls):
        server.app.router.lifespan_context = cls._original_lifespan

    def setUp(self):
        self.original_engine = server.city_engine
        self.original_cooldowns = dict(server._TOOL_LAST_EXECUTED_AT)
        server.city_engine = FakeCityEngine()
        server._TOOL_LAST_EXECUTED_AT.clear()

    def tearDown(self):
        server.city_engine = self.original_engine
        server._TOOL_LAST_EXECUTED_AT.clear()
        server._TOOL_LAST_EXECUTED_AT.update(self.original_cooldowns)

    def test_get_city_scenario_schema_endpoint(self):
        with TestClient(server.app) as client:
            response = client.get("/city/scenario/schema")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["endpoint"], "/city/scenario/schema")
        self.assertIn("simulate_scenario", payload)
        self.assertIn("optimize_hub_pricing", payload["actions"])

    def test_post_city_scenario_run_endpoint(self):
        before = copy.deepcopy(server.city_engine.get_state())
        request_payload = {
            "scenario_actions": [
                {"type": "set_weather", "weather": "storm"},
                {"type": "rebalance_hub_load", "strategy": "hybrid", "zone": "1,2", "max_actions": 3},
            ],
            "horizon_ticks": 20,
            "runs": 2,
        }

        with TestClient(server.app) as client:
            response = client.post("/city/scenario/run", json=request_payload)

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "success")
        self.assertIn("delta", payload)
        self.assertFalse(payload["safety"]["mutates_live_state"])

        after = server.city_engine.get_state()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()