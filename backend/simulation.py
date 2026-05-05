import random
import asyncio
from enum import Enum
from typing import List

class ResidentState(Enum):
    DRIVING = "driving"
    SEEKING = "seeking"
    WAITING = "waiting"
    CHARGING = "charging"

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
        self.price = 0.20  # $ per kWh
        self.capacity = 4
        self.active = True
        # Residents actively occupying a charging slot
        self.charging_slots: set = set()
        # Residents waiting for a free slot (ordered list of IDs)
        self.waiting_queue: list = []

    @property
    def queue_length(self) -> int:
        """Total demand at this hub: waiting + charging."""
        return len(self.waiting_queue) + len(self.charging_slots)

    def free_completed_slots(self, residents_by_id: dict):
        """Remove residents that finished charging from charging_slots.

        Note: residents that have been removed from the simulation entirely
        (i.e. not present in residents_by_id) are also evicted here, so
        their IDs do not remain as orphaned entries in charging_slots.
        """
        finished = [rid for rid in list(self.charging_slots)
                    if rid not in residents_by_id or residents_by_id[rid].state != ResidentState.CHARGING]
        for rid in finished:
            self.charging_slots.discard(rid)

    def promote_from_queue(self):
        """Move waiting residents into free charging slots."""
        while self.waiting_queue and len(self.charging_slots) < self.capacity:
            next_id = self.waiting_queue.pop(0)
            self.charging_slots.add(next_id)

    def enqueue(self, resident_id: str):
        """Add a resident to the waiting queue (idempotent)."""
        if resident_id not in self.charging_slots and resident_id not in self.waiting_queue:
            self.waiting_queue.append(resident_id)

    def release(self, resident_id: str):
        """Remove a resident from both slots and queue (used when they leave)."""
        self.charging_slots.discard(resident_id)
        if resident_id in self.waiting_queue:
            self.waiting_queue.remove(resident_id)

    def update(self):
        if not self.active:
            return
        # Autonomous pricing logic based on demand
        demand = self.queue_length
        if demand > 2:
            self.price += 0.01  # Increase price if busy
        elif demand == 0 and self.price > 0.15:
            self.price -= 0.01  # Lower price to attract customers


class ResidentAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "resident")
        self.battery = random.uniform(20, 100)
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self.state = ResidentState.DRIVING
        self.current_hub = None
        self.speed = random.uniform(0.5, 2.0)

    @property
    def charging(self) -> bool:
        """Backward-compatible property consumed by legacy code paths."""
        return self.state == ResidentState.CHARGING

    def _leave_hub(self):
        if self.current_hub:
            self.current_hub.release(self.id)
            self.current_hub = None

    def _pick_new_destination(self):
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)

    def update(self, hubs: List[ChargingHubAgent], engine):
        weather = engine.weather

        # --- CHARGING state: resident is in a slot, actively charging ---
        if self.state == ResidentState.CHARGING:
            self.battery = min(100, self.battery + engine.global_charging_speed)
            if self.battery >= 100:
                self._leave_hub()
                self.state = ResidentState.DRIVING
                self._pick_new_destination()
            return

        # --- WAITING state: resident is at hub but waiting for a free slot ---
        if self.state == ResidentState.WAITING:
            if self.current_hub and self.id in self.current_hub.charging_slots:
                # Hub promoted us into a slot
                self.state = ResidentState.CHARGING
            return

        # --- DRIVING / SEEKING: drain battery and move ---
        self.battery = max(0, self.battery - engine.global_battery_drain)

        dx = self.destination_x - self.x
        dy = self.destination_y - self.y
        dist = (dx**2 + dy**2)**0.5

        if dist > 1:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed
        else:
            if self.state == ResidentState.DRIVING:
                self._pick_new_destination()

        # Determine battery threshold and search radius multiplier based on weather
        if weather in ("storm", "extreme_heat"):
            seek_threshold = 40
            radius_multiplier = 2.0
        else:
            seek_threshold = 30
            radius_multiplier = 1.0

        # Seek charge if battery is below threshold
        if self.battery < seek_threshold:
            active_hubs = [h for h in hubs if h.active]
            if active_hubs:
                # Score hubs by weighted distance + price
                def hub_score(h):
                    dist_sq = (h.x - self.x)**2 + (h.y - self.y)**2
                    return engine.distance_weight * dist_sq + engine.price_weight * h.price

                target = min(active_hubs, key=hub_score)
                self.state = ResidentState.SEEKING
                self.destination_x = target.x
                self.destination_y = target.y

                # Arrival radius scales with weather: base radius = sqrt(4) ≈ 2 grid units.
                # In storm/extreme_heat the multiplier is 2.0, so the squared threshold
                # becomes 4 * 2² = 16, meaning sqrt(16) = 4 grid units — 2× the base distance.
                arrival_radius = 4 * (radius_multiplier ** 2)
                if (target.x - self.x)**2 + (target.y - self.y)**2 < arrival_radius:
                    # Arrived — join the hub queue
                    self.current_hub = target
                    target.enqueue(self.id)
                    self.state = ResidentState.WAITING


class SimulationEngine:
    def __init__(self):
        # Global simulation parameters that the Oracle can modify
        self.global_charging_speed = 5.0
        self.global_battery_drain = 0.2
        self.weather = "sunny"

        # Hub-selection weights (Oracle can tune these)
        self.distance_weight = 1.0
        self.price_weight = 50.0

        # Initialize the city with 20 residents and 3 charging hubs
        self.residents = [ResidentAgent(f"res_{i}") for i in range(20)]
        self.hubs = [ChargingHubAgent(f"hub_{i}") for i in range(3)]
        self.running = False
        self.subscribers = []

    def get_state(self):
        return {
            "residents": [
                {
                    "id": r.id,
                    "x": r.x,
                    "y": r.y,
                    "battery": r.battery,
                    "charging": r.charging,
                    "state": r.state.value,
                }
                for r in self.residents
            ],
            "hubs": [
                {
                    "id": h.id,
                    "x": h.x,
                    "y": h.y,
                    "price": h.price,
                    "queue": h.queue_length,
                    "slots_used": len(h.charging_slots),
                    "active": h.active,
                }
                for h in self.hubs
            ],
            "weather": self.weather,
        }

    async def run(self):
        from database import save_telemetry, save_market_event
        self.running = True
        tick_counter = 0
        while self.running:
            tick_counter += 1

            # Build a lookup for fast resident access
            residents_by_id = {r.id: r for r in self.residents}

            # Step 1: Each hub frees slots for finished residents, then promotes waiters
            for hub in self.hubs:
                if hub.active:
                    hub.free_completed_slots(residents_by_id)
                    hub.promote_from_queue()

            # Step 2: Update all residents
            for res in self.residents:
                res.update(self.hubs, self)

            # Step 3: Update hub pricing and gather metrics
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
                    for hub in self.hubs:
                        if hub.active:
                            hub.price += 0.05
                    save_market_event("high_demand_surge", "Queue lengths are high, prices surged.")
                elif total_queue == 0:
                    for hub in self.hubs:
                        if hub.active and hub.price > 0.15:
                            hub.price -= 0.02
                    save_market_event("low_demand_drop", "Zero queues, prices dropped to attract residents.")

            # Log telemetry every 10 ticks (5 seconds)
            if tick_counter % 10 == 0:
                save_telemetry(self.weather, active_hubs_count, avg_price, total_queue)

            # Broadcast state to all connected websocket clients
            state = self.get_state()
            for sub in list(self.subscribers):
                await sub(state)

            await asyncio.sleep(0.5)  # Fast simulation tick


# Create a global instance of the engine
engine = SimulationEngine()
