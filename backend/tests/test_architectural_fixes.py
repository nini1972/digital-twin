import unittest
import sys
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Adjust path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from simulation import ChargingHubAgent
from agents.scout import EVScoutAgent
from agents.analyzer import DemandAnalyzerAgent
from agents.chief import ChiefOracleAgent
import server

class TestArchitecturalFixes(unittest.TestCase):

    def setUp(self):
        # Suppress deprecation warnings about event loops
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)

    def test_charging_hub_price_floor(self):
        """Verify that ChargingHubAgent pricing floor respects wholesale rates."""
        hub = ChargingHubAgent("hub_test")
        hub.price = 0.20
        
        # Test 1: No engine, normal update
        hub.update()
        self.assertAlmostEqual(hub.price, 0.19)  # decremented by 0.01 since queue is 0

        # Test 2: Engine with low market price
        engine = MagicMock()
        engine.current_market_price = 0.10
        hub.update(engine)
        self.assertAlmostEqual(hub.price, 0.18)  # decremented by 0.01 since floor is 0.15 (0.10 + 0.02 = 0.12, clamped to 0.15)

        # Test 3: Engine with wholesale price spike
        engine.current_market_price = 0.40  # floor = 0.42
        hub.update(engine)
        self.assertAlmostEqual(hub.price, 0.42)  # adjusted instantly to floor price

        # Test 4: Verify it doesn't decay below the spiked floor
        hub.update(engine)
        self.assertAlmostEqual(hub.price, 0.42)  # remains at floor

    @patch("server.openai_client")
    def test_allow_code_execution_gate(self, mock_openai):
        """Verify that ALLOW_CODE_EXECUTION=False blocks run_python tool calls."""
        # Mock OpenAI response returning a run_python tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "tc_123"
        mock_tool_call.function.name = "run_python"
        mock_tool_call.function.arguments = '{"code": "print(42)"}'

        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.message.content = ""
        
        # Second response (follow-up) mock
        mock_choice_followup = MagicMock()
        mock_choice_followup.message.tool_calls = None
        mock_choice_followup.message.content = "I cannot run python code."
        
        mock_response_1 = MagicMock()
        mock_response_1.choices = [mock_choice]
        
        mock_response_2 = MagicMock()
        mock_response_2.choices = [mock_choice_followup]
        
        # side_effect allows returning different mock results sequentially
        mock_openai.chat.completions.create.side_effect = [mock_response_1, mock_response_2]

        # Force ALLOW_CODE_EXECUTION to False
        server.ALLOW_CODE_EXECUTION = False
        
        # Mock load_conversation to avoid DB calls
        with patch("server.load_conversation", return_value=[]), \
             patch("server.save_messages"), \
             patch("database.load_recent_decisions", return_value=[]):
            
            # Execute city_chat
            request = server.ChatRequest(message="Execute some code", session_id="test_sess")
            
            # Since city_chat is async, run in loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            resp = loop.run_until_complete(server.city_chat(request))
            loop.close()
            
            # Verify that the completions API was called exactly twice
            self.assertEqual(mock_openai.chat.completions.create.call_count, 2)
            
            # Verify the messages sent in the follow-up call
            call_args = mock_openai.chat.completions.create.call_args_list[1]
            sent_messages = call_args.kwargs["messages"]
            
            # Find the tool response message in the history
            tool_msg = next(m for m in sent_messages if m.get("role") == "tool")
            self.assertEqual(tool_msg["tool_call_id"], "tc_123")
            self.assertEqual(tool_msg["name"], "run_python")
            
            content = tool_msg["content"]
            self.assertIn("Python code execution is disabled on this server by system policy", content)
            self.assertEqual(resp.response, "I cannot run python code.")

    def test_proactive_grid_stress_scout(self):
        """Verify that EVScoutAgent publishes grid_stress events during spikes."""
        scout = EVScoutAgent()
        
        # Mock Redis bus publisher
        with patch("agents.scout.bus.publish", new_callable=AsyncMock) as mock_publish:
            state = {
                "hubs": [],
                "residents": [],
                "market_price_eur_kwh": 0.40,  # exceeds 0.35 threshold
                "market_congestion_risk": "LAAG"
            }
            
            # Run tick
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scout.on_tick(state, tick=5))
            loop.close()
            
            # Verify event was published
            mock_publish.assert_called_once()
            args = mock_publish.call_args[0]
            self.assertEqual(args[0], "scout.ev")  # Correct channel name
            self.assertEqual(args[1]["event"], "grid_stress")
            self.assertEqual(args[1]["wholesale_price"], 0.40)

    def test_demand_analyzer_grid_stress(self):
        """Verify that DemandAnalyzerAgent detects grid_stress_pattern."""
        analyzer = DemandAnalyzerAgent()
        analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.40})
        analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.45})
        
        with patch("agents.analyzer.vector_memory.store") as mock_store:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(analyzer._analyze())
            loop.close()
            
            self.assertIsNotNone(analyzer.latest_finding)
            self.assertEqual(analyzer.latest_finding["type"], "grid_stress_pattern")
            self.assertEqual(analyzer.latest_finding["peak_wholesale_price"], 0.45)
            mock_store.assert_called_once()

    def test_chief_oracle_grid_stress_handling(self):
        """Verify that ChiefOracleAgent handles grid_stress_pattern and logs a decision."""
        chief = ChiefOracleAgent()
        
        # Mock demand_analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.latest_finding = {
            "type": "grid_stress_pattern",
            "peak_wholesale_price": 0.45
        }
        chief.demand_analyzer = mock_analyzer
        
        with patch("agents.chief.save_agent_decision") as mock_save:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(chief._synthesize(tick=30))
            loop.close()
            
            mock_save.assert_called_once()
            args = mock_save.call_args[1]
            self.assertEqual(args["decision_type"], "demand_response")
            self.assertIn("Severe grid energy stress", args["description"])

if __name__ == "__main__":
    unittest.main()
