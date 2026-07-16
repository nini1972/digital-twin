"""City simulation: combined EV charging + urban traffic.

Extends the base EV simulation engine with TrafficFlowAgent — non-EV vehicles
that move around the grid and create zone-level congestion.  Congestion raises
battery drain for EV residents passing through the affected zone, forcing more
frequent charging stops and pressuring hub capacity.
"""

import random
import asyncio
from typing import List, Callable

from simulation import SimulationEngine, ResidentAgent, ChargingHubAgent, WEATHER_CONFIG
from pathfinding import astar_path


class TrafficFlowAgent:
    """A non-EV vehicle that contributes to local road congestion."""

    def __init__(self, agent_id: str):
        self.id = agent_id
        self.type = "traffic"
        self.x = random.uniform(0, 100)
        self.y = random.uniform(0, 100)
        self.speed = random.uniform(1.0, 3.0)
        self.speed_multiplier: float = 1.0  # Modified by zone signal timing
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self.path: List[tuple[float, float]] = []

    def _pick_new_destination(self, engine):
        self.destination_x = random.uniform(0, 100)
        self.destination_y = random.uniform(0, 100)
        self._compute_path(engine)

    def _compute_path(self, engine):
        def cost_fn(a, b):
            base_cost = 10.0
            congestion = engine.get_congestion_for(b[0], b[1])
            return base_cost * (1.0 + congestion * 5.0)
        self.path = astar_path((self.x, self.y), (self.destination_x, self.destination_y), cost_fn)

    def update(self, engine):
        if not self.path:
            self._pick_new_destination(engine)

        next_waypoint = self.path[0]
        dx = next_waypoint[0] - self.x
        dy = next_waypoint[1] - self.y
        dist = (dx ** 2 + dy ** 2) ** 0.5
        
        effective_speed = self.speed * self.speed_multiplier

        if dist > effective_speed:
            self.x += (dx / dist) * effective_speed
            self.y += (dy / dist) * effective_speed
        else:
            self.x = next_waypoint[0]
            self.y = next_waypoint[1]
            self.path.pop(0)
            if not self.path:
                self._pick_new_destination(engine)


class CitySimulationEngine(SimulationEngine):
    """Extended engine that adds urban traffic + zone congestion mechanics."""

    # 100-unit grid divided into 5×5 zones (each zone = 20×20 units)
    ZONE_SIZE = 20
    # Maximum extra battery drain added at 100% zone congestion
    CONGESTION_DRAIN_BONUS = 0.15
    MIN_PRICE = 0.10
    MAX_PRICE = 0.80

    # ------------------------------------------------------------------
    # Initialisatie
    # ------------------------------------------------------------------
    def __init__(self):
        super().__init__()
        # Override scale: larger city
        self.residents = [ResidentAgent(f"res_{i}") for i in range(25)]
        self.hubs = [ChargingHubAgent(f"hub_{i}") for i in range(4)]
        self.traffic_agents: List[TrafficFlowAgent] = [
            TrafficFlowAgent(f"traffic_{i}") for i in range(15)
        ]
        # zone_key ("zx,zy") → congestion 0..1
        self.zone_congestion: dict[str, float] = {}
        # zone_key → speed multiplier (1.0 = normal, <1.0 = throttled by signal timing)
        self.zone_speed_limits: dict[str, float] = {}
        # zone_key → speed multiplier from real-world Belgian traffic incidents
        self.traffic_incident_speed_limits: dict[str, float] = {}
        # Live Belgian traffic events list
        self.live_traffic_events: List[dict] = []
        self.last_traffic_update_tick: int = 0
        # Callbacks invoked after each tick: (state_dict, tick_counter) → None
        self.agent_subscribers: List[Callable] = []
        self.thought_subscribers: List[Callable] = []
        
        # --- NIEUW: Realtime marktprijs variabelen initialiseren ---
        self.current_market_price: float = 0.15  # Standaard startprijs
        self.current_market_demand: float = 90.0
        self.current_congestion_risk: str = "LAAG"

    # ------------------------------------------------------------------
    # Energiemarkt Actuatie (Aangeroepen door FastAPI POST /city)
    # ------------------------------------------------------------------

    def update_market_conditions(self, price: float, demand: float, risk: str):
        """
        Updates the digital twin engine with real-time electricity market data.
        This data will be automatically exposed to the AI Oracle Agents.
        """
        self.current_market_price = price
        self.current_market_demand = demand
        self.current_congestion_risk = risk
        print(f"⚡ [CityEngine] Live marktomstandigheden bijgewerkt: €{price}/kWh | Congestierisico net: {risk}")



    # ------------------------------------------------------------------
    # Zone helpers
    # ------------------------------------------------------------------

    def _zone_key(self, x: float, y: float) -> str:
        zx = int(x // self.ZONE_SIZE)
        zy = int(y // self.ZONE_SIZE)
        return f"{zx},{zy}"

    def _compute_congestion(self):
        """Recompute per-zone congestion from current traffic agent positions."""
        counts: dict[str, int] = {}
        for t in self.traffic_agents:
            key = self._zone_key(t.x, t.y)
            counts[key] = counts.get(key, 0) + 1
        # ≥10 traffic agents in a zone → 100% congestion
        self.zone_congestion = {k: min(1.0, v / 10.0) for k, v in counts.items()}

    def get_congestion_for(self, x: float, y: float) -> float:
        """Return congestion level 0..1 for the zone containing (x, y)."""
        return self.zone_congestion.get(self._zone_key(x, y), 0.0)

    # ------------------------------------------------------------------
    # Traffic actuation (called by City Oracle tools)
    # ------------------------------------------------------------------

    def reroute_traffic_from_zone(self, zone_key: str) -> int:
        """Force all traffic agents in zone_key to pick a new destination
        outside that zone.  Simulates rerouting vehicles away from a hotspot.
        Returns the number of agents rerouted."""
        zx, zy = (int(v) for v in zone_key.split(","))
        zone_x_min = zx * self.ZONE_SIZE
        zone_x_max = zone_x_min + self.ZONE_SIZE
        zone_y_min = zy * self.ZONE_SIZE
        zone_y_max = zone_y_min + self.ZONE_SIZE
        rerouted = 0
        for t in self.traffic_agents:
            if zone_x_min <= t.x < zone_x_max and zone_y_min <= t.y < zone_y_max:
                # Assign destination in a different zone
                while True:
                    new_x = random.uniform(0, 100)
                    new_y = random.uniform(0, 100)
                    if not (zone_x_min <= new_x < zone_x_max and zone_y_min <= new_y < zone_y_max):
                        break
                t.destination_x = new_x
                t.destination_y = new_y
                rerouted += 1
        return rerouted

    def set_zone_speed_limit(self, zone_key: str, multiplier: float):
        """Set a speed multiplier for all traffic in a zone.
        multiplier=1.0 → normal speed; 0.3 → heavy throttle (red light phase).
        Clamp to [0.1, 1.0].  Set to 1.0 to clear any restriction."""
        multiplier = max(0.1, min(1.0, multiplier))
        if multiplier >= 1.0:
            self.zone_speed_limits.pop(zone_key, None)
        else:
            self.zone_speed_limits[zone_key] = multiplier

    # ------------------------------------------------------------------
    # State snapshot
    # ------------------------------------------------------------------

    def get_state(self):
        state = super().get_state()
        state["traffic"] = [
            {"id": t.id, "x": round(t.x, 2), "y": round(t.y, 2)}
            for t in self.traffic_agents
        ]
        state["zone_congestion"] = self.zone_congestion
        state["zone_speed_limits"] = self.zone_speed_limits
        state["traffic_incident_speed_limits"] = self.traffic_incident_speed_limits
        
        # --- NIEUW: Voeg marktdata toe aan de hoofdstate ---
        state["market_price_eur_kwh"] = self.current_market_price
        state["market_congestion_risk"] = self.current_congestion_risk
        state["market_demand_kw"] = self.current_market_demand
        
        # --- NIEUW: Voeg de metrics toe zodat de ProfitMarginWidget ze ontvangt! ---
        state["metrics"] = self.get_city_metrics()
        # --- NIEUW: Voeg live Belgische verkeersincidenten toe ---
        state["live_traffic_events"] = self.live_traffic_events
        return state

    def get_city_metrics(self) -> dict:
        """Compact metrics dict consumed by Scout agents and context builders."""
        active_hubs = [h for h in self.hubs if h.active]
        total_queue = sum(h.queue_length for h in active_hubs)
        avg_price = (
            sum(h.price for h in active_hubs) / len(active_hubs) if active_hubs else 0.0
        )
        charging_count = sum(1 for r in self.residents if r.charging)
        seeking_count = sum(
            1 for r in self.residents if r.state.value == "seeking"
        )
        congestion_values = list(self.zone_congestion.values())
        avg_congestion = (
            sum(congestion_values) / len(congestion_values) if congestion_values else 0.0
        )
        hotspot = (
            max(self.zone_congestion, key=lambda k: self.zone_congestion[k])
            if self.zone_congestion else "none"
        )
        
        # --- BEREKENING REALTIME WINSTMARGE ---
        # Wholesale inkoopprijs ophalen uit de engine (default naar 0.10)
        wholesale_price = getattr(self, "current_market_price", 0.10)
        
        # Winstmarge per kWh (Gemiddelde verkoopprijs minus de inkoopprijs)
        profit_margin_eur_kwh = avg_price - wholesale_price
        
        # Geschatte winst per uur (laadcount * gemiddelde laadsnelheid van 22kW * marge)
        estimated_hourly_profit = charging_count * 22.0 * profit_margin_eur_kwh

        # --- NIEUWE TRAFFIC FLOW EN ZONE CONGESTIE METRIEKEN ---
        zone_congestion_details = {
            "residential": round(self.zone_congestion.get("residential", 0.0), 3),
            "commercial": round(self.zone_congestion.get("commercial", 0.0), 3),
            "industrial": round(self.zone_congestion.get("industrial", 0.0), 3),
            "highway": round(self.zone_congestion.get("highway", 0.0), 3)
        }

        # --- NIEUWE EV BATTERIJ PRESTATIE METRIEKEN ---
        soh_values = [getattr(r, "state_of_health", 1.0) for r in self.residents]
        avg_soh = sum(soh_values) / len(soh_values) if soh_values else 1.0
        degraded_ev_count = sum(1 for r in self.residents if getattr(r, "state_of_health", 1.0) < 0.88)
        temp_values = [getattr(r, "battery_temperature", 20.0) for r in self.residents]
        avg_battery_temp = sum(temp_values) / len(temp_values) if temp_values else 20.0

        # --- NIEUWE GEBRUIKERSGEDRAG PATRONEN ---
        charging_demand_ratio = (seeking_count + total_queue) / max(1, len(self.residents))

        # --- NIEUWE LOKALE ENERGIEVRAAG ---
        ev_power_demand_kw = charging_count * 22.0
        city_base_demand_kw = getattr(self, "current_market_demand", 90.0)
        total_city_grid_load_kw = ev_power_demand_kw + city_base_demand_kw

        # --- NIEUWE MILIEU-IMPACT METRIEKEN ---
        w_config = WEATHER_CONFIG.get(self.weather, WEATHER_CONFIG["sunny"])
        grid_co2_intensity = w_config["grid_co2_intensity"]
            
        ev_co2_emissions_kg_h = (ev_power_demand_kw * grid_co2_intensity) / 1000.0
        traffic_co2_emissions_kg_h = len(self.traffic_agents) * 0.12 * (1.0 + avg_congestion * 1.5)
        # Schatting van CO2 besparing door EV t.o.v. verbrandingsmotoren (1.8 kg CO2 per uur per ladend voertuig, geschaald met CO2 intensiteit)
        co2_saved_kg_h = charging_count * 1.8 * (1.0 - (grid_co2_intensity / 300.0))

        return {
            "residents": len(self.residents),
            "traffic_agents": len(self.traffic_agents),
            "active_hubs": len(active_hubs),
            "total_queue": total_queue,
            "avg_price": round(avg_price, 3),
            "charging_count": charging_count,
            "seeking_count": seeking_count,
            "avg_congestion": round(avg_congestion, 3),
            "congestion_hotspot": hotspot,
            "weather": self.weather,
            
            # --- DASHBOARD FINANCIËLE METRIEKEN ---
            "wholesale_energy_price_eur_kwh": round(wholesale_price, 4),
            "profit_margin_eur_kwh": round(profit_margin_eur_kwh, 4),
            "estimated_hourly_profit_eur": round(max(0.0, estimated_hourly_profit), 2),
            "roi_efficiency_index": round((avg_price / max(0.01, wholesale_price)), 2),

            # --- NIEUWE VERKEERS-, BATTERIJ-, ENERGIE- EN MILIEU-METRIEKEN ---
            "zone_congestion_details": zone_congestion_details,
            "avg_fleet_soh": round(avg_soh, 3),
            "degraded_ev_count": degraded_ev_count,
            "avg_battery_temp": round(avg_battery_temp, 1),
            "charging_demand_ratio": round(charging_demand_ratio, 3),
            "ev_power_demand_kw": round(ev_power_demand_kw, 1),
            "city_base_demand_kw": round(city_base_demand_kw, 1),
            "total_city_grid_load_kw": round(total_city_grid_load_kw, 1),
            "grid_co2_intensity": round(grid_co2_intensity, 1),
            "ev_co2_emissions_kg_h": round(ev_co2_emissions_kg_h, 2),
            "traffic_co2_emissions_kg_h": round(traffic_co2_emissions_kg_h, 2),
            "co2_saved_kg_h": round(max(0.0, co2_saved_kg_h), 2)
        }


    async def _update_belgian_traffic(self, current_tick: int):
        try:
            from belgian_traffic import fetch_belgian_traffic
            events = await fetch_belgian_traffic()
            self.live_traffic_events = events
            self.last_traffic_update_tick = current_tick
            
            # Rebuild incident-based speed limits
            new_limits: dict[str, float] = {}
            for ev in events:
                zk = ev["zone_key"]
                severity = 0.3 if ev["event_type"] == "accident" else 0.5
                new_limits[zk] = min(new_limits.get(zk, 1.0), severity)
            self.traffic_incident_speed_limits = new_limits
        except Exception as e:
            print(f"[CityEngine] Belgian traffic update error: {e}")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self):
        from database import save_telemetry, save_market_event, prune_old_data

        self.running = True
        tick_counter = 0

        while self.running:
            tick_counter += 1

            # --- Periodically update Belgian Traffic Open Data (every 120 ticks = 1 min) ---
            if tick_counter == 1 or (tick_counter - self.last_traffic_update_tick >= 120):
                if not getattr(self, "_traffic_fetching_task", None) or self._traffic_fetching_task.done():
                    self._traffic_fetching_task = asyncio.create_task(self._update_belgian_traffic(tick_counter))

            # --- Traffic layer ---
            for t in self.traffic_agents:
                zk = self._zone_key(t.x, t.y)
                manual_mult = self.zone_speed_limits.get(zk, 1.0)
                incident_mult = self.traffic_incident_speed_limits.get(zk, 1.0)
                t.speed_multiplier = min(manual_mult, incident_mult)
                t.update(self)
            self._compute_congestion()

            # --- EV layer with congestion-aware drain ---
            residents_by_id = {r.id: r for r in self.residents}

            for hub in self.hubs:
                if hub.active:
                    hub.free_completed_slots(residents_by_id)
                    hub.promote_from_queue()

            # Track previous states
            prev_states = {r.id: r.state for r in self.residents}

            for res in self.residents:
                congestion = self.get_congestion_for(res.x, res.y)
                drain_boost = congestion * self.CONGESTION_DRAIN_BONUS
                original_drain = self.global_battery_drain
                self.global_battery_drain += drain_boost
                res.update(self.hubs, self)
                self.global_battery_drain = original_drain
                
                # Check if state changed and trigger subscribers
                if res.state != prev_states[res.id]:
                    for cb in self.thought_subscribers:
                        try:
                            # Fire and forget thought generation callback
                            asyncio.create_task(cb(res, prev_states[res.id], res.state, tick_counter))
                        except Exception as exc:
                            print(f"[CityEngine] thought_subscriber error: {exc}")

            # --- Hub pricing & metrics ---
            active_hubs_count = 0
            total_queue = 0
            total_price = 0.0
            for hub in self.hubs:
                hub.update(self)
                if hub.active:
                    active_hubs_count += 1
                    total_queue += hub.queue_length
                    total_price += hub.price

            # --- Continuous city market adaptation ---
            # Makes hub prices respond in near-real-time to active demand pressure,
            # not only at the 20-tick event boundary.
                        # --- Continuous city market adaptation ---
            # Makes hub prices respond in near-real-time to active demand pressure.
                        # --- Continuous city market adaptation ---
            # Makes hub prices respond in near-real-time to active demand pressure.
            seeking_count = sum(
                1 for r in self.residents if getattr(r.state, "value", "") == "seeking"
            )
            if active_hubs_count > 0:
                seeking_per_hub = seeking_count / active_hubs_count
                for hub in self.hubs:
                    if not hub.active:
                        continue
                    pressure = hub.queue_length + 0.5 * seeking_per_hub
                    
                    # NIEUW: De bodemprijs is de MIN_PRICE óf de live inkoopprijs van de stroom
                    # Dit voorkomt dat we laden onder de kostprijs van de energie!
                    dynamic_floor = max(self.MIN_PRICE, getattr(self, "current_market_price", 0.10))
                    
                    if pressure >= hub.capacity * 0.8:
                        hub.price += 0.008
                    elif pressure <= 0.4:
                        hub.price -= 0.004
                    
                    # GECORRIGEERD: Gebruik dynamic_floor in plaats van self.MIN_PRICE
                    hub.price = min(self.MAX_PRICE, max(dynamic_floor, hub.price))

            # Recompute totals after adaptation so telemetry reflects true current prices.
            total_price = sum(h.price for h in self.hubs if h.active)

            avg_price = total_price / max(1, active_hubs_count)

            # --- Market event loop (every 20 ticks) ---
                        # --- Market event loop (every 20 ticks) ---
            if tick_counter % 20 == 0:
                dynamic_floor = max(self.MIN_PRICE, getattr(self, "current_market_price", 0.10))
                
                if total_queue > active_hubs_count * 2:
                    for hub in self.hubs:
                        if hub.active:
                            hub.price += 0.05
                            hub.price = min(self.MAX_PRICE, hub.price)
                    save_market_event(
                        "city_high_demand_surge",
                        "City: Queue lengths high — prices surged.",
                    )
                # GECORRIGEERD: Val terug naar de dynamic_floor als er geen wachtrijen zijn
                elif total_queue == 0:
                    for hub in self.hubs:
                        if hub.active and hub.price > dynamic_floor:
                            hub.price -= 0.02
                            hub.price = max(dynamic_floor, hub.price)
                    save_market_event(
                        "city_low_demand_drop",
                        "City: Zero queues — prices dropped to market floor to attract residents.",
                    )
                else:
                    save_market_event(
                        "city_market_stable",
                        "City: Market stable — prices adjusted based on queue pressure.",
                    )

            # --- Telemetry (every 10 ticks) ---
            if tick_counter % 10 == 0:
                save_telemetry(self.weather, active_hubs_count, avg_price, total_queue)

            # --- Database pruning (every 1000 ticks) ---
            if tick_counter % 1000 == 0:
                prune_old_data()

            # --- Notify Scout / agent subscribers ---
            if self.agent_subscribers:
                state = self.get_state()
                for cb in list(self.agent_subscribers):
                    try:
                        await cb(state, tick_counter)
                    except Exception as exc:
                        print(f"[CityEngine] agent_subscriber error: {exc}")

            # --- Broadcast to WebSocket subscribers ---
            state = self.get_state()
            for sub in list(self.subscribers):
                await sub(state)

            await asyncio.sleep(0.5)


# Global instance — imported by server.py and agent modules
city_engine = CitySimulationEngine()
