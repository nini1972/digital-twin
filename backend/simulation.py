import random
import asyncio
from enum import Enum
from typing import List
from pathfinding import astar_path

WEATHER_CONFIG = {
    "sunny": {
        "hvac_drain": 0.05,
        "ambient_temp": 20.0,
        "charge_multiplier": 1.0,
        "drain_multiplier": 1.0,
        "evaluate_drain": 0.2,
        "evaluate_charge": 5.0,
        "city_factor": 1.0,
        "grid_co2_intensity": 80.0,
        "seek_threshold": 30,
        "radius_multiplier": 1.0,
    },
    "clear_night": {
        "hvac_drain": 0.05,
        "ambient_temp": 10.0,
        "charge_multiplier": 1.0,
        "drain_multiplier": 1.0,
        "evaluate_drain": 0.2,
        "evaluate_charge": 5.0,
        "city_factor": 1.0,
        "grid_co2_intensity": 150.0,
        "seek_threshold": 30,
        "radius_multiplier": 1.0,
    },
    "storm": {
        "hvac_drain": 0.05,
        "ambient_temp": 10.0,
        "charge_multiplier": 0.6,
        "drain_multiplier": 1.3,
        "evaluate_drain": 0.5,
        "evaluate_charge": 2.0,
        "city_factor": 1.35,
        "grid_co2_intensity": 240.0,
        "seek_threshold": 40,
        "radius_multiplier": 2.0,
    },
    "extreme_heat": {
        "hvac_drain": 0.15,
        "ambient_temp": 35.0,
        "charge_multiplier": 0.8,
        "drain_multiplier": 1.45,
        "evaluate_drain": 0.8,
        "evaluate_charge": 4.0,
        "city_factor": 1.5,
        "grid_co2_intensity": 150.0,
        "seek_threshold": 40,
        "radius_multiplier": 2.0,
    },
    "extreme_cold": {
        "hvac_drain": 0.15,
        "ambient_temp": -5.0,
        "charge_multiplier": 0.6,
        "drain_multiplier": 1.2,
        "evaluate_drain": 0.4,
        "evaluate_charge": 3.0,
        "city_factor": 1.2,
        "grid_co2_intensity": 240.0,
        "seek_threshold": 40,
        "radius_multiplier": 2.0,
    },
    "winter": {
        "hvac_drain": 0.15,
        "ambient_temp": 0.0,
        "charge_multiplier": 0.6,
        "drain_multiplier": 1.2,
        "evaluate_drain": 0.4,
        "evaluate_charge": 3.0,
        "city_factor": 1.2,
        "grid_co2_intensity": 240.0,
        "seek_threshold": 40,
        "radius_multiplier": 2.0,
    },
    "snow": {
        "hvac_drain": 0.12,
        "ambient_temp": -2.0,
        "charge_multiplier": 0.5,
        "drain_multiplier": 1.35,
        "evaluate_drain": 0.6,
        "evaluate_charge": 2.5,
        "city_factor": 1.4,
        "grid_co2_intensity": 240.0,
        "seek_threshold": 40,
        "radius_multiplier": 2.0,
    },
    "rain": {
        "hvac_drain": 0.05,
        "ambient_temp": 12.0,
        "charge_multiplier": 0.9,
        "drain_multiplier": 1.1,
        "evaluate_drain": 0.3,
        "evaluate_charge": 4.5,
        "city_factor": 1.1,
        "grid_co2_intensity": 150.0,
        "seek_threshold": 30,
        "radius_multiplier": 1.0,
    }
}


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

    def update(self, engine=None):
        if not self.active:
            return
        # Autonomous pricing logic based on demand
        demand = self.queue_length
        
        # Determine the price floor based on wholesale rate
        floor_price = 0.15
        if engine is not None and hasattr(engine, "current_market_price"):
            # Enforce floor: wholesale cost + small retail margin (e.g. 0.02 EUR/kWh)
            floor_price = max(0.15, getattr(engine, "current_market_price", 0.10) + 0.02)

        if self.price < floor_price:
            self.price = floor_price  # Instantly adjust up to avoid selling at a loss
        elif demand > 2:
            self.price = min(0.80, self.price + 0.01)  # Increase price if busy
        elif demand == 0 and self.price > floor_price:
            self.price = max(floor_price, self.price - 0.01)  # Lower price, but respect the floor


class ResidentAgent(Agent):
    def __init__(self, agent_id: str):
        super().__init__(agent_id, "resident")
        self.vehicle_type = random.choice(["sedan", "suv", "truck"])
        if self.vehicle_type == "sedan":
            self.base_capacity = 60.0
            self.efficiency = 0.15  # kWh per unit distance
        elif self.vehicle_type == "suv":
            self.base_capacity = 85.0
            self.efficiency = 0.25
        else:
            self.base_capacity = 120.0
            self.efficiency = 0.35

        # Battery Degradation (State of Health)
        self.state_of_health = random.uniform(0.85, 1.0)
        self.battery_capacity = self.base_capacity * self.state_of_health

        self.battery = random.uniform(20, self.battery_capacity)
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self.state = ResidentState.DRIVING
        self.current_hub: ChargingHubAgent | None = None
        self.base_speed = random.uniform(0.5, 2.0)
        self.speed = self.base_speed
        self.path: List[tuple[float, float]] = []
        
        self.current_aero_drag = 0.0
        self.current_regen_efficiency = 0.4
        self.battery_temperature = random.uniform(15.0, 25.0)
        self.payload_weight = random.uniform(50.0, 300.0)

    @property
    def charging(self) -> bool:
        """Backward-compatible property consumed by legacy code paths."""
        return self.state == ResidentState.CHARGING

    def _leave_hub(self):
        if self.current_hub:
            self.current_hub.release(self.id)
            self.current_hub = None

    def _pick_new_destination(self, engine):
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self._compute_path(engine, self.destination_x, self.destination_y)

    def _compute_path(self, engine, target_x, target_y):
        def cost_fn(a, b):
            base_cost = 10.0
            if hasattr(engine, 'get_congestion_for'):
                congestion = engine.get_congestion_for(b[0], b[1])
                return base_cost * (1.0 + congestion * 5.0)
            return base_cost
        self.path = astar_path((self.x, self.y), (target_x, target_y), cost_fn)

    def update(self, hubs: List[ChargingHubAgent], engine):
        weather = engine.weather

        # Get congestion (default 0 if basic engine)
        congestion = 0.0
        if hasattr(engine, 'get_congestion_for'):
            congestion = engine.get_congestion_for(self.x, self.y)

        # Retrieve weather configuration (default to nominal sunny settings if weather is unrecognized)
        w_config = WEATHER_CONFIG.get(weather, WEATHER_CONFIG["sunny"])
        hvac_drain = w_config["hvac_drain"]
        ambient_temp = w_config["ambient_temp"]

        # Thermal dynamics (slowly adjust to ambient)
        self.battery_temperature += (ambient_temp - self.battery_temperature) * 0.05

        if self.state in (ResidentState.CHARGING, ResidentState.WAITING):
            self.speed = 0.0
            self.current_aero_drag = 0.0

        # --- CHARGING state: resident is in a slot, actively charging ---
        if self.state == ResidentState.CHARGING:
            # Advanced Physics: Non-linear charging curve & temperature effects
            soc = self.battery / self.battery_capacity
            charge_rate = engine.global_charging_speed
            
            # Tapering (DC Fast Charging curve)
            if soc > 0.95:
                charge_rate *= 0.2
            elif soc > 0.80:
                charge_rate *= 0.5
            
            # Weather impacts on charging (Coldgate & Thermal Throttling)
            charge_rate *= w_config["charge_multiplier"]
            
            # Charging heats up the battery
            self.battery_temperature += 0.5

            self.battery = min(self.battery_capacity, self.battery + charge_rate)
            if self.battery >= self.battery_capacity:
                self._leave_hub()
                self.state = ResidentState.DRIVING
                self._pick_new_destination(engine)
            return

        # --- WAITING state: resident is at hub but waiting for a free slot ---
        if self.state == ResidentState.WAITING:
            self.battery = max(0, self.battery - hvac_drain)
            hub = self.current_hub

            if hub is None or getattr(hub, "active", True) is False:
                # Hub is unavailable while we are waiting; leave its queue and re-seek.
                self._leave_hub()
                self.state = ResidentState.SEEKING
                self.path = [] # Clear path to force re-seek
            elif self.id in hub.charging_slots:
                # Hub promoted us into a slot
                self.state = ResidentState.CHARGING
                return
            else:
                return

        # --- DRIVING / SEEKING: move and drain battery ---
        if not self.path:
            if self.state == ResidentState.DRIVING:
                self._pick_new_destination(engine)
            elif self.state == ResidentState.SEEKING:
                self._compute_path(engine, self.destination_x, self.destination_y)

        # Dynamic speed calculation based on congestion, speed limits, and randomness
        if self.state in (ResidentState.DRIVING, ResidentState.SEEKING):
            speed_variance = random.uniform(0.85, 1.15)
            # Speed is reduced by congestion (max 80% reduction)
            congestion_factor = max(0.2, 1.0 - (congestion * 0.8))
            
            # Retrieve speed limit multiplier for the current zone from the engine
            speed_multiplier = 1.0
            if hasattr(engine, "_zone_key"):
                zone_key = engine._zone_key(self.x, self.y)
                manual_mult = getattr(engine, "zone_speed_limits", {}).get(zone_key, 1.0)
                incident_mult = getattr(engine, "traffic_incident_speed_limits", {}).get(zone_key, 1.0)
                speed_multiplier = min(manual_mult, incident_mult)
                
            self.speed = self.base_speed * speed_variance * congestion_factor * speed_multiplier

        distance_moved = 0.0
        if self.path:
            next_waypoint = self.path[0]
            dx = next_waypoint[0] - self.x
            dy = next_waypoint[1] - self.y
            dist = (dx**2 + dy**2)**0.5

            if dist > self.speed:
                distance_moved = self.speed
                self.x += (dx / dist) * self.speed
                self.y += (dy / dist) * self.speed
            else:
                distance_moved = dist
                self.x = next_waypoint[0]
                self.y = next_waypoint[1]
                self.path.pop(0)
                if not self.path and self.state == ResidentState.DRIVING:
                    self._pick_new_destination(engine)

        # Advanced Physics: Aerodynamic drag and Regenerative Braking
        # Drag increases squarely with speed
        self.current_aero_drag = (self.speed ** 2) * 0.02
        
        # Driving heats up the battery
        self.battery_temperature += (self.speed * 0.1)
        
        # Payload penalty based on weight
        payload_penalty = (self.payload_weight / 1000.0) * 0.05 * distance_moved
        
        # Base drain: efficiency * distance + aero_drag + payload penalty
        base_driving_drain = distance_moved * self.efficiency + self.current_aero_drag + payload_penalty
        
        # Congestion penalty mitigated by regen braking (stop-and-go recoups energy)
        self.current_regen_efficiency = 0.4
        congestion_penalty = (congestion * 0.5) * (1.0 - self.current_regen_efficiency)
        
        driving_drain = base_driving_drain * (1.0 + congestion_penalty)
        self.battery = max(0, self.battery - (hvac_drain + driving_drain))

        # Recompute percentage for threshold checks
        battery_percentage = (self.battery / self.battery_capacity) * 100

        # Determine battery threshold and search radius multiplier based on weather configuration
        seek_threshold = w_config["seek_threshold"]
        radius_multiplier = w_config["radius_multiplier"]

        # Seek charge if battery percentage is below threshold
        if battery_percentage < seek_threshold and self.state == ResidentState.DRIVING:
            active_hubs = [h for h in hubs if h.active]
            if active_hubs:
                # Score hubs by weighted distance, price, and waiting list (queue length)
                def hub_score(h):
                    dist = ((h.x - self.x)**2 + (h.y - self.y)**2)**0.5
                    queue_penalty = getattr(engine, 'wait_weight', 15.0) * h.queue_length
                    return engine.distance_weight * dist + engine.price_weight * h.price + queue_penalty

                target = min(active_hubs, key=hub_score)
                self.state = ResidentState.SEEKING
                self.destination_x = target.x
                self.destination_y = target.y
                self._compute_path(engine, target.x, target.y)

        if self.state == ResidentState.SEEKING:
            # Re-evaluate arrival logic
            arrival_radius = 4 * (radius_multiplier ** 2)
            if (self.destination_x - self.x)**2 + (self.destination_y - self.y)**2 < arrival_radius:
                # Arrived — join the hub queue
                active_hubs = [h for h in hubs if h.active]
                # Find the hub we arrived at (closest one to destination_x, destination_y)
                if active_hubs:
                    target = min(active_hubs, key=lambda h: (h.x - self.destination_x)**2 + (h.y - self.destination_y)**2)
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
        self.wait_weight = 15.0

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
                    "battery": (r.battery / r.battery_capacity) * 100.0,
                    "battery_raw": r.battery,
                    "battery_capacity": r.battery_capacity,
                    "soh": r.state_of_health,
                    "aero_drag": r.current_aero_drag,
                    "regen_efficiency": r.current_regen_efficiency,
                    "battery_temperature": r.battery_temperature,
                    "payload_weight": r.payload_weight,
                    "vehicle_type": r.vehicle_type,
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
                    "queue_total": h.queue_length,
                    "waiting": len(h.waiting_queue),
                    "charging": len(h.charging_slots),
                    "slots_used": len(h.charging_slots),
                    "capacity": h.capacity,
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
