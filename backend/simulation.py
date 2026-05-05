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
        self.active = True

    def update(self):
        if not self.active:
            return
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
        self.current_hub = None
        self.speed = random.uniform(0.5, 2.0)

    def update(self, hubs: List[ChargingHubAgent], engine):
        if self.charging and self.current_hub:
            # Enforce hub capacity: only charge if within the first 'capacity' slots. The rest wait.
            if self.current_hub.queue_length < self.current_hub.capacity:
                self.battery += engine.global_charging_speed  # Charging speed
            self.current_hub.queue_length += 1
            
            if self.battery >= 100:
                self.battery = 100
                self.charging = False
                self.current_hub = None
                self.destination_x = random.uniform(0, 100)
                self.destination_y = random.uniform(0, 100)
            return

        self.battery -= engine.global_battery_drain  # Battery drain per tick
        
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
            active_hubs = [h for h in hubs if h.active]
            if active_hubs:
                # Find the nearest hub
                nearest = min(active_hubs, key=lambda h: (h.x - self.x)**2 + (h.y - self.y)**2)
                self.destination_x = nearest.x
                self.destination_y = nearest.y
                
                # If arrived at hub
                if (nearest.x - self.x)**2 + (nearest.y - self.y)**2 < 4:
                    self.charging = True
                    self.current_hub = nearest

class SimulationEngine:
    def __init__(self):
        # Global simulation parameters that the Oracle can modify
        self.global_charging_speed = 5.0
        self.global_battery_drain = 0.2
        self.weather = "sunny"
        
        # Initialize the city with 20 residents and 3 charging hubs
        self.residents = [ResidentAgent(f"res_{i}") for i in range(20)]
        self.hubs = [ChargingHubAgent(f"hub_{i}") for i in range(3)]
        self.running = False
        self.subscribers = []

    def get_state(self):
        return {
            "residents": [{"id": r.id, "x": r.x, "y": r.y, "battery": r.battery, "charging": r.charging} for r in self.residents],
            "hubs": [{"id": h.id, "x": h.x, "y": h.y, "price": h.price, "queue": h.queue_length, "active": h.active} for h in self.hubs],
            "weather": self.weather
        }

    async def run(self):
        from database import save_telemetry, save_market_event
        self.running = True
        tick_counter = 0
        while self.running:
            tick_counter += 1
            # Reset queue lengths to recount
            for hub in self.hubs:
                hub.queue_length = 0
                
            # Update all residents
            for res in self.residents:
                res.update(self.hubs, self)
            
            # Update all hubs
            active_hubs_count = 0
            total_queue = 0
            total_price = 0
            for hub in self.hubs:
                hub.update()
                if hub.active:
                    active_hubs_count += 1
                    total_queue += hub.queue_length
                    total_price += hub.price

            avg_price = total_price / max(1, active_hubs_count)

            # Automated Market Event Loop
            if tick_counter % 20 == 0:  # Every 20 ticks (10 seconds)
                if total_queue > active_hubs_count * 2:
                    # High demand, price surge event
                    for hub in self.hubs:
                        if hub.active:
                            hub.price += 0.05
                    save_market_event("high_demand_surge", "Queue lengths are high, prices surged.")
                elif total_queue == 0:
                    # Low demand, price drop
                    for hub in self.hubs:
                        if hub.active and hub.price > 0.15:
                            hub.price -= 0.02
                    save_market_event("low_demand_drop", "Zero queues, prices dropped to attract residents.")

            # Log telemetry every 10 ticks (5 seconds)
            if tick_counter % 10 == 0:
                save_telemetry(self.weather, active_hubs_count, avg_price, total_queue)

            # Broadcast state to all connected websocket clients
            state = self.get_state()
            # Create a copy of subscribers list to iterate safely
            for sub in list(self.subscribers):
                await sub(state)
            
            await asyncio.sleep(0.5) # Fast simulation tick

# Create a global instance of the engine
engine = SimulationEngine()
