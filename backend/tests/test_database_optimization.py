import unittest
import sys
import os
import sqlite3
import asyncio
from unittest.mock import patch

# Adjust path to import backend modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import database
from agents.analyzer import DemandAnalyzerAgent, CongestionAnalyzerAgent

class TestDatabaseOptimization(unittest.TestCase):

    def setUp(self):
        # Setup temporary SQLite database for testing pruning
        self.db_path = os.path.join(os.path.dirname(__file__), 'test_sim.db')
        self.original_db_path = database.DB_PATH
        database.DB_PATH = self.db_path
        database.init_db()
        
        # Suppress deprecation warnings about event loops
        import warnings
        warnings.filterwarnings("ignore", category=DeprecationWarning)

    def tearDown(self):
        database.DB_PATH = self.original_db_path
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_sqlite_pruning(self):
        """Verify that prune_old_data deletes rows exceeding specified limits."""
        # Insert 10 telemetry rows
        for i in range(10):
            database.save_telemetry(weather="sunny", active_hubs=3, avg_price=0.25, total_queue=i)
            
        # Insert 10 market events
        for i in range(10):
            database.save_market_event(event_type="test_event", description=f"desc_{i}")
            
        # Insert 10 decisions
        for i in range(10):
            database.save_agent_decision(agent_name="Chief", decision_type="test_dec", description=f"dec_{i}", tick=i)

        # Confirm counts before pruning
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM telemetry")
        self.assertEqual(cursor.fetchone()[0], 10)
        
        cursor.execute("SELECT COUNT(*) FROM market_events")
        self.assertEqual(cursor.fetchone()[0], 10)
        
        cursor.execute("SELECT COUNT(*) FROM agent_decisions")
        self.assertEqual(cursor.fetchone()[0], 10)
        
        conn.close()

        # Run pruning
        database.prune_old_data(max_telemetry=3, max_events=2, max_decisions=4)

        # Confirm counts after pruning
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM telemetry")
        self.assertEqual(cursor.fetchone()[0], 3)
        
        cursor.execute("SELECT COUNT(*) FROM market_events")
        self.assertEqual(cursor.fetchone()[0], 2)
        
        cursor.execute("SELECT COUNT(*) FROM agent_decisions")
        self.assertEqual(cursor.fetchone()[0], 4)
        
        # Verify the kept records are the latest ones
        cursor.execute("SELECT total_queue FROM telemetry ORDER BY id ASC")
        queues = [r[0] for r in cursor.fetchall()]
        self.assertEqual(queues, [7, 8, 9])  # the latest 3 inserted
        
        conn.close()

    def test_analyzer_vector_cooldown(self):
        """Verify that DemandAnalyzerAgent debounces writes to ChromaDB using tick cooldown."""
        analyzer = DemandAnalyzerAgent()
        
        # Scenario 1: Initial pattern confirmed -> Stores in ChromaDB
        analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.40, "tick": 10})
        analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.45, "tick": 12})
        
        with patch("agents.analyzer.vector_memory.store") as mock_store:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(analyzer._analyze())
            
            # Stored once
            self.assertEqual(mock_store.call_count, 1)
            self.assertEqual(analyzer._last_stored_ticks.get("grid_stress"), 12)
            
            # Scenario 2: Another event inside cooldown tick range (tick 15, < 100 cooldown)
            analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.46, "tick": 15})
            loop.run_until_complete(analyzer._analyze())
            
            # Not stored again (call count remains 1)
            self.assertEqual(mock_store.call_count, 1)
            
            # Scenario 3: Event after cooldown tick range (tick 120, > 100 cooldown)
            analyzer._window.append({"event": "grid_stress", "wholesale_price": 0.47, "tick": 120})
            loop.run_until_complete(analyzer._analyze())
            
            # Stored again (call count becomes 2)
            self.assertEqual(mock_store.call_count, 2)
            self.assertEqual(analyzer._last_stored_ticks.get("grid_stress"), 120)
            
            loop.close()

    def test_congestion_analyzer_vector_cooldown(self):
        """Verify that CongestionAnalyzerAgent debounces writes per-zone using tick cooldown."""
        analyzer = CongestionAnalyzerAgent()
        
        # Confirm persistent hotspot for Zone "1,1" at tick 10
        for i in range(4):
            analyzer._window.append({"event": "congestion_hotspot", "zone": "1,1", "level": 0.80, "tick": 10})
            
        with patch("agents.analyzer.vector_memory.store") as mock_store:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(analyzer._analyze())
            
            # Stored once
            self.assertEqual(mock_store.call_count, 1)
            self.assertEqual(analyzer._last_stored_ticks.get("hotspot_1,1"), 10)
            
            # Repeat hotspot at tick 15 (inside cooldown)
            analyzer._window.append({"event": "congestion_hotspot", "zone": "1,1", "level": 0.85, "tick": 15})
            loop.run_until_complete(analyzer._analyze())
            
            # Clogged / blocked by cooldown
            self.assertEqual(mock_store.call_count, 1)
            
            # Different zone "2,2" at tick 15 (should not be blocked by zone "1,1"'s cooldown)
            for i in range(4):
                analyzer._window.append({"event": "congestion_hotspot", "zone": "2,2", "level": 0.80, "tick": 15})
            loop.run_until_complete(analyzer._analyze())
            
            # Stores for zone 2,2 (call count becomes 2)
            self.assertEqual(mock_store.call_count, 2)
            self.assertEqual(analyzer._last_stored_ticks.get("hotspot_2,2"), 15)
            
            loop.close()

if __name__ == "__main__":
    unittest.main()
