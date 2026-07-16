import unittest
from unittest.mock import patch, MagicMock
import asyncio
import belgian_traffic
from city_simulation import CitySimulationEngine

# Sample XML data matching DATEX II v3
MOCK_DATEX_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<payload modelBaseVersion="3" 
    xmlns="http://datex2.eu/schema/3/common" 
    xmlns:ns2="http://datex2.eu/schema/3/situation" 
    xmlns:ns4="http://datex2.eu/schema/3/d2Payload" 
    xmlns:ns3="http://datex2.eu/schema/3/locationReferencing"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <ns4:situation id="EVT_ACCIDENT_1">
        <ns2:situationVersionTime>2026-06-27T21:00:00+02:00</ns2:situationVersionTime>
        <ns2:headerInformation>
            <confidentiality>noRestriction</confidentiality>
            <informationStatus>real</informationStatus>
        </ns2:headerInformation>
        <ns2:situationRecord xsi:type="ns2:Accident" id="REC_ACCIDENT_1" version="1">
            <ns2:validity>
                <validityStatus>active</validityStatus>
            </ns2:validity>
            <ns2:description>
                <value lang="nl">Ongeval op de E17 in Gent. Rijstrook versperd.</value>
            </ns2:description>
            <ns3:pointByCoordinates>
                <ns3:pointCoordinates>
                    <ns3:latitude>193000.0</ns3:latitude>
                    <ns3:longitude>104000.0</ns3:longitude>
                </ns3:pointCoordinates>
            </ns3:pointByCoordinates>
        </ns2:situationRecord>
    </ns4:situation>
    <ns4:situation id="EVT_QUEUE_1">
        <ns2:situationVersionTime>2026-06-27T21:00:00+02:00</ns2:situationVersionTime>
        <ns2:headerInformation>
            <confidentiality>noRestriction</confidentiality>
            <informationStatus>real</informationStatus>
        </ns2:headerInformation>
        <ns2:situationRecord xsi:type="ns2:AbnormalTraffic" id="REC_QUEUE_1" version="1">
            <ns2:validity>
                <validityStatus>active</validityStatus>
            </ns2:validity>
            <ns2:description>
                <value lang="nl">Stilstaand verkeer / file op Ring Antwerpen (R1).</value>
            </ns2:description>
            <ns3:pointByCoordinates>
                <ns3:pointCoordinates>
                    <ns3:latitude>212000.0</ns3:latitude>
                    <ns3:longitude>152000.0</ns3:longitude>
                </ns3:pointCoordinates>
            </ns3:pointByCoordinates>
        </ns2:situationRecord>
    </ns4:situation>
    <ns4:situation id="EVT_INACTIVE">
        <ns2:situationVersionTime>2026-06-27T21:00:00+02:00</ns2:situationVersionTime>
        <ns2:headerInformation>
            <confidentiality>noRestriction</confidentiality>
            <informationStatus>real</informationStatus>
        </ns2:headerInformation>
        <ns2:situationRecord xsi:type="ns2:MaintenanceWorks" id="REC_WORKS_1" version="1">
            <ns2:validity>
                <validityStatus>suspended</validityStatus>
            </ns2:validity>
            <ns2:description>
                <value lang="nl">Geplande werken E313.</value>
            </ns2:description>
            <ns3:pointByCoordinates>
                <ns3:pointCoordinates>
                    <ns3:latitude>180000.0</ns3:latitude>
                    <ns3:longitude>219000.0</ns3:longitude>
                </ns3:pointCoordinates>
            </ns3:pointByCoordinates>
        </ns2:situationRecord>
    </ns4:situation>
</payload>
"""

class TestBelgianTraffic(unittest.TestCase):

    def test_coordinate_projection(self):
        # Ghent coordinates in Lambert 72
        sim_x, sim_y = belgian_traffic.project_to_grid(104000.0, 193000.0)
        self.assertTrue(0.0 <= sim_x <= 100.0)
        self.assertTrue(0.0 <= sim_y <= 100.0)
        
        # Test boundaries clamping
        sim_x_min, sim_y_min = belgian_traffic.project_to_grid(0.0, 0.0)
        self.assertEqual(sim_x_min, 0.0)
        self.assertEqual(sim_y_min, 0.0)
        
        sim_x_max, sim_y_max = belgian_traffic.project_to_grid(500000.0, 500000.0)
        self.assertEqual(sim_x_max, 100.0)
        self.assertEqual(sim_y_max, 100.0)

    def test_xml_parsing(self):
        parsed = belgian_traffic.parse_datex_feed(MOCK_DATEX_XML)
        
        # Should parse EVT_ACCIDENT_1 (active accident) and EVT_QUEUE_1 (active queue)
        # Should ignore EVT_INACTIVE (not active)
        self.assertEqual(len(parsed), 2)
        
        accident = next(e for e in parsed if e["id"] == "EVT_ACCIDENT_1")
        self.assertEqual(accident["event_type"], "accident")
        self.assertIn("Ongeval", accident["description"])
        # Ghent maps to zone "1,2"
        self.assertEqual(accident["zone_key"], "1,2")
        
        queue = next(e for e in parsed if e["id"] == "EVT_QUEUE_1")
        self.assertEqual(queue["event_type"], "queue")
        self.assertIn("file op Ring Antwerpen", queue["description"])
        # Antwerp maps to zone "3,3"
        self.assertEqual(queue["zone_key"], "3,3")

    @patch("belgian_traffic.requests.get")
    def test_engine_integration(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = MOCK_DATEX_XML
        mock_get.return_value = mock_response
        
        engine = CitySimulationEngine()
        
        # Run the update
        async def run_update():
            await engine._update_belgian_traffic(120)
            
        asyncio.run(run_update())
        
        # Verify events loaded
        self.assertEqual(len(engine.live_traffic_events), 2)
        self.assertEqual(engine.last_traffic_update_tick, 120)
        
        # Verify speed limits applied:
        # Accident in zone "1,2" -> severity = 0.3
        # Queue in zone "3,3" -> severity = 0.5
        self.assertEqual(engine.traffic_incident_speed_limits.get("1,2"), 0.3)
        self.assertEqual(engine.traffic_incident_speed_limits.get("3,3"), 0.5)
        
        # Verify get_state includes the events
        state = engine.get_state()
        self.assertIn("live_traffic_events", state)
        self.assertEqual(len(state["live_traffic_events"]), 2)

    def test_resident_agent_respects_speed_limits(self):
        from simulation import ResidentAgent, ResidentState
        from city_simulation import CitySimulationEngine
        
        engine = CitySimulationEngine()
        res = ResidentAgent("res_test_speed")
        res.state = ResidentState.DRIVING
        res.x = 30.0  # zone_key "1,2" (30/20=1, 50/20=2)
        res.y = 50.0
        res.path = [(32.0, 50.0)]
        res.base_speed = 2.0
        
        # Test base speed with no restrictions
        with patch("random.uniform", return_value=1.0):
            res.update([], engine)
            self.assertAlmostEqual(res.speed, 2.0)
            
        # Add manual speed limit in zone "1,2"
        engine.zone_speed_limits["1,2"] = 0.5
        with patch("random.uniform", return_value=1.0):
            res.update([], engine)
            self.assertAlmostEqual(res.speed, 1.0)
            
        # Add incident speed limit in zone "1,2"
        engine.traffic_incident_speed_limits["1,2"] = 0.3
        with patch("random.uniform", return_value=1.0):
            res.update([], engine)
            self.assertAlmostEqual(res.speed, 0.6)

if __name__ == "__main__":
    unittest.main()
