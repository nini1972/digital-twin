import random
import asyncio
from typing import List

class Agent:
    def __init__(self, agent_id: str, agent_type: str):
        self.id = agent_id
        self.type = agent_type
        # Initialize in a 100x100 city grid
        self.x = random.uniform(0, 100)
        self.y = random.uniform(0, 100)

class ChargingHubAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "charging_hub")
        self.price = 0.20 # $ per kWh
        self.capacity = 4
        self.queue_length = 0

    def update(self):
        # Autonomous pricing logic based on demand
        if self.queue_length > 2:
            self.price += 0.01  # Increase price if busy
        elif self.queue_length == 0 and self.price > 0.15:
            self.price -= 0.01  # Lower price to attract customers

class ResidentAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "resident")
        self.battery = random.uniform(20, 100)
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self.charging = False
        self.speed = random.uniform(0.5, 2.0)

    def update(self, hubs: List[ChargingHubAgent]):
        if self.charging:
            self.battery += 5  # Charging speed
            if self.battery >= 100:
                self.battery = 100
                self.charging = False
                self.destination_x = random.uniform(0, 100)
                self.destination_y = random.uniform(0, 100)
            return

        self.battery -= 0.2  # Battery drain per tick
        
        # Move towards destination
        dx = self.destination_x - self.x
        dy = self.destination_y - self.y
        dist = (dx**2 + dy**2)**0.5
        
        if dist > 1:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        else:
            # Reached destination, pick a new one
            self.destination_x = random.uniform(0, 100)
            self.destination_y = random.uniform(0, 100)

        # Seek charge if battery is low
        if self.battery < 30:
            if hubs:
                # Find the nearest hub
                nearest = min(hubs, key=lambda h: (h.x - self.x)**2 + (h.y - self.y)**2)
                self.destination_x = nearest.x
                self.destination_y = nearest.y
                
                # If arrived at hub
                if (nearest.x - self.x)**2 + (nearest.y - self.y)**2 < 4:
                    self.charging = True
                    nearest.queue_length += 1

class SimulationEngine:
    def __init__(self):
        # Initialize the city with 20 residents and 3 charging hubs
        self.residents = [ResidentAgent(f"res_{i}") for i in range(20)]
        self.hubs = [ChargingHubAgent(f"hub_{i}") for i in range(3)]
        self.running = False
        self.subscribers = []

    def get_state(self):
        return {
            "residents": [{"id": r.id, "x": r.x, "y": r.y, "battery": r.battery, "charging": r.charging} for r in self.residents],
            "hubs": [{"id": h.id, "x": h.x, "y": h.y, "price": h.price, "queue": h.queue_length} for h in self.hubs]
        }

    async def run(self):
        self.running = True
        while self.running:
            # Reset queue lengths to recount
            for hub in self.hubs:
                hub.queue_length = 0
                
            # Update all residents
            for res in self.residents:
                res.update(self.hubs)
            
            # Update all hubs
            for hub in self.hubs:
                hub.update()

            # Broadcast state to all connected websocket clients
            state = self.get_state()
            # Create a copy of subscribers list to iterate safely
            for sub in list(self.subscribers):
                await sub(state)
            
            await asyncio.sleep(0.5) # Fast simulation tick

# Create a global instance of the engine
engine = SimulationEngine()
