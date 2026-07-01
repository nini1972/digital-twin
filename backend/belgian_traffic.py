"""Belgian Traffic Open Data Ingestor.

Fetches and parses the live DATEX II v3 XML feed from the Vlaams Verkeerscentrum,
mapping coordinates to the Digital Twin's grid coordinate system.
"""

import xml.etree.ElementTree as ET
import requests
import asyncio
from typing import List, Dict, Any

# Bounding box for Flanders / Brussels in Lambert 72 (meters)
MIN_X = 20000.0
MAX_X = 240000.0
MIN_Y = 160000.0
MAX_Y = 230000.0

def project_to_grid(x: float, y: float) -> tuple[float, float]:
    """Map Lambert 72 (x, y) to 100x100 grid coordinates."""
    # Clamp coordinates to bounding box
    cx = max(MIN_X, min(MAX_X, x))
    cy = max(MIN_Y, min(MAX_Y, y))
    
    norm_x = (cx - MIN_X) / (MAX_X - MIN_X)
    norm_y = (cy - MIN_Y) / (MAX_Y - MIN_Y)
    
    sim_x = norm_x * 100.0
    sim_y = norm_y * 100.0
    return sim_x, sim_y

def parse_datex_feed(xml_content: bytes) -> List[Dict[str, Any]]:
    """Parse the XML content from a DATEX II v3 feed, returning active accidents and queues."""
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"[BelgianTraffic] XML parse error: {e}")
        return []
        
    situations = []
    
    # We find all elements whose tag ends with '}situation' to be namespace prefix independent
    for sit in root.iter():
        if not sit.tag.endswith('}situation'):
            continue
            
        sit_id = sit.get("id", "")
        
        # Check if active
        status_el = None
        for child in sit.iter():
            if child.tag.endswith('}validityStatus'):
                status_el = child
                break
        status = status_el.text if status_el is not None else "unknown"
        if status != "active":
            continue
            
        # Find record
        record = None
        for child in sit.iter():
            if child.tag.endswith('}situationRecord'):
                record = child
                break
        if record is None:
            continue
            
        # Get type
        xsi_type = record.get("{http://www.w3.org/2001/XMLSchema-instance}type", "")
        type_lower = xsi_type.lower()
        
        # We focus on:
        # 1. Accidents
        # 2. Severe traffic queues / Abnormal traffic
        is_accident = "accident" in type_lower
        is_queue = "abnormaltraffic" in type_lower or "congestion" in type_lower or "queue" in type_lower
        
        # Extract description
        desc_text = ""
        for desc_node in record.iter():
            if desc_node.tag.endswith('}description'):
                # Look for value inside description
                for val_node in desc_node.iter():
                    if val_node.tag.endswith('}value') and val_node.text:
                        desc_text = val_node.text
                        break
                break
                
        # Fallback keyword match in description for works that cause delays or queues
        desc_lower = desc_text.lower()
        if not is_accident and not is_queue:
            # If the event description specifically mentions traffic queues or accidents, include it
            if any(k in desc_lower for k in ["ongeval", "ongeluk", "accident", "file ", "files ", "wachtrij", "congestie", "verkeershinder"]):
                if any(k in desc_lower for k in ["ongeval", "ongeluk", "accident"]):
                    is_accident = True
                else:
                    is_queue = True
                    
        if not is_accident and not is_queue:
            continue
            
        # Extract coordinates
        x_val = None
        y_val = None
        for coord_node in record.iter():
            if coord_node.tag.endswith('}pointCoordinates'):
                for child in coord_node:
                    if child.tag.endswith('}latitude'):
                        if child.text:
                            y_val = float(child.text)  # Northing (Y)
                    elif child.tag.endswith('}longitude'):
                        if child.text:
                            x_val = float(child.text)  # Easting (X)
                break
                
        if x_val is None or y_val is None:
            continue
            
        sim_x, sim_y = project_to_grid(x_val, y_val)
        
        # Calculate zone key "zx,zy"
        zx = int(sim_x // 20)
        zy = int(sim_y // 20)
        # clamp to 0..4
        zx = max(0, min(4, zx))
        zy = max(0, min(4, zy))
        zone_key = f"{zx},{zy}"
        
        situations.append({
            "id": sit_id,
            "event_type": "accident" if is_accident else "queue",
            "description": desc_text or f"Incident ({xsi_type})",
            "x": sim_x,
            "y": sim_y,
            "zone_key": zone_key
        })
        
    return situations

async def fetch_belgian_traffic() -> List[Dict[str, Any]]:
    """Fetch and parse live traffic events from Vlaams Verkeerscentrum."""
    url = "https://www.verkeerscentrum.be/uitwisseling/datex2v3"
    try:
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: requests.get(url, timeout=10)
        )
        if response.status_code == 200:
            return parse_datex_feed(response.content)
        else:
            print(f"[BelgianTraffic] HTTP error: {response.status_code}")
            return []
    except Exception as e:
        print(f"[BelgianTraffic] Fetch error: {e}")
        return []
