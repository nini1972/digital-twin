import copy
import random
import time
from typing import Optional
from simulation import WEATHER_CONFIG


MIN_ACTIVE_HUBS_FOR_OPTIMIZATION = 2
MAX_TOOL_ACTIONS = 5
MAX_PRICE_DELTA_PER_CALL = 0.05
MIN_PRICE_DELTA_PER_CALL = 0.005
MAX_PRICE_SPREAD = 0.35
MIN_SIGNAL_MULTIPLIER = 0.4
TOOL_COOLDOWN_SECONDS = 5.0
MAX_TRAFFIC_REROUTE_PER_CALL = 10

SCENARIO_ACTION_ALLOWED_FIELDS: dict[str, set[str]] = {
    "set_weather": {"type", "weather"},
    "add_city_hub": {"type", "count"},
    "add_city_resident": {"type", "count"},
    "add_city_traffic": {"type", "count"},
    "set_hub_price": {"type", "hub_id", "price"},
    "set_hub_active_state": {"type", "hub_id", "active"},
    "set_signal_timing": {"type", "zone", "multiplier"},
    "reroute_traffic": {"type", "zone"},
    "optimize_hub_pricing": {"type", "objective", "floor", "ceiling", "max_delta", "fairness_weight"},
    "rebalance_hub_load": {"type", "strategy", "max_actions", "zone", "aggressiveness"},
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _top_congestion_hotspots(city_engine, limit: int = 3) -> list[dict]:
    hotspots = sorted(city_engine.zone_congestion.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [{"zone": zone, "congestion": round(level, 3)} for zone, level in hotspots]


def _forecast_recommendations(*, projected_queue: float, active_hubs: int, projected_price: float, current_price: float, weather: str) -> list[str]:
    recommendations: list[str] = []
    if projected_queue > active_hubs * 3:
        recommendations.append("Apply traffic reroute and temporary signal throttling in top hotspot zones.")
    if projected_price > current_price + 0.05:
        recommendations.append("Enable fairness-aware dynamic pricing with bounded per-tick deltas.")
    if weather in ("storm", "extreme_heat"):
        recommendations.append("Pre-stage additional active hub capacity before weather stress peak.")
    if recommendations:
        return recommendations
    return ["Maintain current policy and continue monitoring trend drift."]


def _battery_segment_key(battery: float) -> str:
    if battery < 20:
        return "battery_critical"
    if battery < 40:
        return "battery_low"
    if battery < 70:
        return "battery_mid"
    return "battery_high"


def _check_tool_cooldown(tool_last_executed_at: dict[str, float], tool_name: str) -> Optional[str]:
    now = time.time()
    last = tool_last_executed_at.get(tool_name, 0.0)
    wait = TOOL_COOLDOWN_SECONDS - (now - last)
    if wait > 0:
        return f"Tool '{tool_name}' cooling down. Retry in {wait:.1f}s."
    tool_last_executed_at[tool_name] = now
    return None


def _active_hubs(city_engine) -> list:
    return [hub for hub in city_engine.hubs if getattr(hub, "active", False)]


def _zone_population(city_engine, zone_key: str) -> int:
    try:
        zx, zy = (int(v) for v in zone_key.split(","))
    except Exception:
        return 0
    zone_size = getattr(city_engine, "ZONE_SIZE", 20)
    x_min = zx * zone_size
    x_max = x_min + zone_size
    y_min = zy * zone_size
    y_max = y_min + zone_size
    return sum(
        1
        for traffic in getattr(city_engine, "traffic_agents", [])
        if x_min <= getattr(traffic, "x", 0.0) < x_max and y_min <= getattr(traffic, "y", 0.0) < y_max
    )


def _parse_bool(value, *, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def forecast_city_load(city_engine, horizon_ticks: int = 30) -> dict:
    horizon_ticks = max(5, min(120, int(horizon_ticks)))
    metrics = city_engine.get_city_metrics()
    active_hubs = max(1, int(metrics.get("active_hubs", 1)))
    total_queue = float(metrics.get("total_queue", 0))
    seeking = float(metrics.get("seeking_count", 0))
    avg_congestion = float(metrics.get("avg_congestion", 0.0))
    avg_price = float(metrics.get("avg_price", 0.20))
    weather = str(metrics.get("weather", "sunny"))

    weather_factor = WEATHER_CONFIG.get(weather, WEATHER_CONFIG["sunny"]).get("city_factor", 1.1)
    horizon_scale = horizon_ticks / 30.0
    pressure = (total_queue + 0.8 * seeking) / active_hubs
    growth = 1.0 + (0.12 * horizon_scale * weather_factor) + (0.35 * avg_congestion)
    projected_queue = max(0.0, total_queue * growth + 0.4 * seeking)

    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    projected_price = avg_price * (1.0 + 0.08 * horizon_scale + 0.10 * pressure / 4.0)
    projected_price = min(max_price, max(min_price, projected_price))

    confidence = 0.82 - (0.18 * min(1.0, avg_congestion)) - (0.08 * max(0.0, horizon_scale - 1.0))
    confidence = round(max(0.45, min(0.9, confidence)), 2)

    return {
        "horizon_ticks": horizon_ticks,
        "weather": weather,
        "projected_total_queue": round(projected_queue, 2),
        "projected_avg_price": round(projected_price, 3),
        "projected_hotspots": _top_congestion_hotspots(city_engine, limit=3),
        "confidence": confidence,
        "recommendations": _forecast_recommendations(
            projected_queue=projected_queue,
            active_hubs=active_hubs,
            projected_price=projected_price,
            current_price=avg_price,
            weather=weather,
        ),
    }


def analyze_resident_segments(city_engine) -> dict:
    residents = list(city_engine.residents)
    total = max(1, len(residents))
    segment_counts = {"battery_critical": 0, "battery_low": 0, "battery_mid": 0, "battery_high": 0}
    state_counts: dict[str, int] = {"driving": 0, "seeking": 0, "waiting": 0, "charging": 0}

    for resident in residents:
        battery = float(getattr(resident, "battery", 0.0))
        state = str(getattr(getattr(resident, "state", None), "value", "driving"))
        segment_counts[_battery_segment_key(battery)] += 1
        state_counts[state] = state_counts.get(state, 0) + 1

    active_hubs = [h for h in city_engine.hubs if h.active]
    total_capacity = sum(h.capacity for h in active_hubs)
    total_queue = sum(h.queue_length for h in active_hubs)
    
    if total_capacity > 0:
        # Hub capacity utilization (queue + charging occupancy / capacity)
        hub_pressure = total_queue / total_capacity
    else:
        hub_pressure = 0.0

    fleet_pressure = (state_counts.get("seeking", 0) + state_counts.get("waiting", 0)) / total

    # Combined pressure index considers both grid queue/chargers load and fleet seeking activity
    pressure_index = max(hub_pressure, fleet_pressure)
    risk_band = "high" if pressure_index >= 0.4 else "medium" if pressure_index >= 0.2 else "low"

    return {
        "residents": len(residents),
        "battery_segments": {key: {"count": value, "ratio": round(value / total, 3)} for key, value in segment_counts.items()},
        "state_segments": {key: {"count": value, "ratio": round(value / total, 3)} for key, value in state_counts.items()},
        "charging_pressure_index": round(pressure_index, 3),
        "demand_risk_band": risk_band,
    }


def evaluate_weather_impact(city_engine, target_weather: str, horizon_ticks: int = 30) -> dict:
    horizon_ticks = max(5, min(120, int(horizon_ticks)))
    weather = (target_weather or "sunny").strip().lower()
    if weather not in WEATHER_CONFIG:
        weather = "sunny"

    baseline = city_engine.get_city_metrics()
    baseline_profile = WEATHER_CONFIG["sunny"]
    profile = WEATHER_CONFIG[weather]
    weather_stress = (profile["evaluate_drain"] / baseline_profile["evaluate_drain"]) * (baseline_profile["evaluate_charge"] / profile["evaluate_charge"])
    horizon_scale = horizon_ticks / 30.0
    projected_queue = float(baseline.get("total_queue", 0)) * (1.0 + (weather_stress - 1.0) * 0.45 * horizon_scale)
    projected_congestion = float(baseline.get("avg_congestion", 0.0)) * (1.0 + (weather_stress - 1.0) * 0.30 * horizon_scale)
    projected_congestion = min(1.0, max(0.0, projected_congestion))
    actions = [
        "Pre-position active hubs near current hotspot zones.",
        "Use temporary signal timing to prevent congestion spillover.",
        "Apply bounded dynamic pricing to smooth charging arrivals.",
    ]
    if weather in {"sunny", "clear_night"}:
        actions = ["Run normal policy; reserve interventions for demand spikes only."]

    return {
        "target_weather": weather,
        "horizon_ticks": horizon_ticks,
        "baseline_weather": baseline.get("weather", "unknown"),
        "weather_stress_index": round(weather_stress, 3),
        "projected_total_queue": round(projected_queue, 2),
        "projected_avg_congestion": round(projected_congestion, 3),
        "recommended_actions": actions,
    }


def optimize_hub_pricing(city_engine, tool_last_executed_at: dict[str, float], objective: str = "balanced", floor: Optional[float] = None, ceiling: Optional[float] = None, max_delta: float = 0.02, fairness_weight: float = 0.5) -> dict:
    cooldown_error = _check_tool_cooldown(tool_last_executed_at, "optimize_hub_pricing")
    if cooldown_error:
        return {"status": "error", "message": cooldown_error}

    hubs = _active_hubs(city_engine)
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {"status": "error", "message": f"Need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs for optimization."}

    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    floor = _clamp(float(floor if floor is not None else min_price), min_price, max_price)
    ceiling = _clamp(float(ceiling if ceiling is not None else max_price), floor, max_price)
    max_delta = _clamp(float(max_delta), MIN_PRICE_DELTA_PER_CALL, MAX_PRICE_DELTA_PER_CALL)
    fairness_weight = _clamp(float(fairness_weight), 0.0, 1.0)
    objective = str(objective or "balanced").strip().lower()

    avg_queue = sum(hub.queue_length for hub in hubs) / len(hubs)
    avg_price = sum(hub.price for hub in hubs) / len(hubs)
    updates = []
    for hub in hubs:
        pressure = (hub.queue_length - avg_queue) / max(1, hub.capacity)
        fairness_pull = avg_price - hub.price
        if objective == "queue_reduction":
            raw_delta = max_delta * pressure
        elif objective == "max_throughput":
            raw_delta = max_delta * (1.2 * pressure)
        elif objective == "fairness":
            raw_delta = (1.0 - fairness_weight) * max_delta * pressure + fairness_weight * fairness_pull
        else:
            raw_delta = 0.65 * max_delta * pressure + 0.35 * fairness_weight * fairness_pull

        delta = _clamp(raw_delta, -max_delta, max_delta)
        old_price = float(hub.price)
        new_price = _clamp(old_price + delta, floor, ceiling)
        hub.price = new_price
        updates.append({"hub_id": hub.id, "queue": hub.queue_length, "old_price": round(old_price, 3), "new_price": round(new_price, 3), "delta": round(new_price - old_price, 3)})

    prices = [float(hub.price) for hub in hubs]
    spread = max(prices) - min(prices)
    if spread > MAX_PRICE_SPREAD:
        center = sum(prices) / len(prices)
        for hub in hubs:
            hub.price = _clamp(hub.price, center - MAX_PRICE_SPREAD / 2, center + MAX_PRICE_SPREAD / 2)
            hub.price = _clamp(hub.price, floor, ceiling)

    return {
        "status": "success",
        "objective": objective,
        "constraints": {"floor": round(floor, 3), "ceiling": round(ceiling, 3), "max_delta": round(max_delta, 3), "max_spread": MAX_PRICE_SPREAD},
        "updates": updates,
    }


def rebalance_hub_load(city_engine, tool_last_executed_at: dict[str, float], strategy: str = "hybrid", max_actions: int = 3, zone: Optional[str] = None, aggressiveness: float = 0.5) -> dict:
    cooldown_error = _check_tool_cooldown(tool_last_executed_at, "rebalance_hub_load")
    if cooldown_error:
        return {"status": "error", "message": cooldown_error}

    hubs = _active_hubs(city_engine)
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {"status": "error", "message": f"Need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs to rebalance load."}

    strategy = str(strategy or "hybrid").strip().lower()
    if strategy not in {"reroute", "price", "hybrid"}:
        strategy = "hybrid"
    max_actions = int(_clamp(float(max_actions), 1, MAX_TOOL_ACTIONS))
    aggressiveness = _clamp(float(aggressiveness), 0.1, 1.0)

    actions = []
    avg_queue = sum(hub.queue_length for hub in hubs) / len(hubs)
    overloaded = [hub for hub in hubs if hub.queue_length >= max(hub.capacity, avg_queue + 1)]
    underused = [hub for hub in hubs if hub.queue_length <= max(0.0, avg_queue - 1)]

    if strategy in {"price", "hybrid"} and max_actions > 0:
        bump = _clamp(0.02 * aggressiveness, MIN_PRICE_DELTA_PER_CALL, MAX_PRICE_DELTA_PER_CALL)
        min_price = getattr(city_engine, "MIN_PRICE", 0.10)
        max_price = getattr(city_engine, "MAX_PRICE", 0.80)
        for hub in overloaded[:max_actions]:
            old = hub.price
            hub.price = _clamp(hub.price + bump, min_price, max_price)
            actions.append({"type": "price_increase", "hub_id": hub.id, "old": round(old, 3), "new": round(hub.price, 3)})
            if len(actions) >= max_actions:
                break
        for hub in underused:
            if len(actions) >= max_actions:
                break
            old = hub.price
            hub.price = _clamp(hub.price - bump, min_price, max_price)
            actions.append({"type": "price_decrease", "hub_id": hub.id, "old": round(old, 3), "new": round(hub.price, 3)})

    if strategy in {"reroute", "hybrid"} and len(actions) < max_actions:
        zone_target = zone
        if not zone_target:
            hotspots = sorted(city_engine.zone_congestion.items(), key=lambda item: item[1], reverse=True)
            zone_target = hotspots[0][0] if hotspots else None
        if zone_target:
            zone_population = _zone_population(city_engine, zone_target)
            if zone_population <= MAX_TRAFFIC_REROUTE_PER_CALL:
                rerouted = city_engine.reroute_traffic_from_zone(zone_target)
                actions.append({"type": "reroute", "zone": zone_target, "rerouted": int(rerouted)})
                if len(actions) < max_actions:
                    throttle = _clamp(1.0 - 0.4 * aggressiveness, MIN_SIGNAL_MULTIPLIER, 1.0)
                    city_engine.set_zone_speed_limit(zone_target, throttle)
                    actions.append({"type": "signal_timing", "zone": zone_target, "multiplier": round(throttle, 2)})
            else:
                actions.append({"type": "reroute_skipped", "zone": zone_target, "reason": f"zone population {zone_population} exceeds safety cap {MAX_TRAFFIC_REROUTE_PER_CALL}"})

    return {
        "status": "success",
        "strategy": strategy,
        "applied_actions": actions[:max_actions],
        "safety": {"max_actions": max_actions, "max_price_delta": MAX_PRICE_DELTA_PER_CALL, "max_reroute_agents": MAX_TRAFFIC_REROUTE_PER_CALL, "cooldown_seconds": TOOL_COOLDOWN_SECONDS},
    }


def _state_avg_congestion(state: dict) -> float:
    values = list((state.get("zone_congestion") or {}).values())
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _state_metrics(state: dict) -> dict:
    hubs = state.get("hubs", [])
    residents = state.get("residents", [])
    traffic = state.get("traffic", [])
    active_hubs = [hub for hub in hubs if hub.get("active", True)]
    total_queue = float(sum(float(hub.get("queue", 0.0)) for hub in active_hubs))
    avg_price = float(sum(float(hub.get("price", 0.2)) for hub in active_hubs) / len(active_hubs)) if active_hubs else 0.0
    seeking_count = sum(1 for resident in residents if str(resident.get("state", "")) == "seeking")
    charging_count = sum(1 for resident in residents if str(resident.get("state", "")) == "charging")
    waiting_count = sum(1 for resident in residents if str(resident.get("state", "")) == "waiting")
    return {
        "residents": len(residents),
        "traffic_agents": len(traffic),
        "active_hubs": len(active_hubs),
        "total_queue": round(total_queue, 3),
        "avg_price": round(avg_price, 3),
        "seeking_count": seeking_count,
        "charging_count": charging_count,
        "waiting_count": waiting_count,
        "avg_congestion": round(_state_avg_congestion(state), 3),
        "weather": state.get("weather", "sunny"),
    }


def _normalize_scenario_action(city_engine, raw: dict, index: int) -> tuple[Optional[dict], Optional[str]]:
    if not isinstance(raw, dict):
        return None, f"scenario_actions[{index}] must be an object"

    action_type = str(raw.get("type", "")).strip().lower()
    if action_type not in SCENARIO_ACTION_ALLOWED_FIELDS:
        allowed = ", ".join(sorted(SCENARIO_ACTION_ALLOWED_FIELDS.keys()))
        return None, f"scenario_actions[{index}].type '{action_type}' is unsupported. Allowed: {allowed}"

    normalized = {"type": action_type}
    if action_type == "set_weather":
        weather = str(raw.get("weather", "sunny")).strip().lower()
        if weather not in WEATHER_CONFIG:
            allowed = ", ".join(sorted(WEATHER_CONFIG.keys()))
            return None, f"scenario_actions[{index}].weather must be one of: {allowed}"
        normalized["weather"] = weather
    elif action_type in {"add_city_hub", "add_city_resident", "add_city_traffic"}:
        normalized["count"] = str(int(_clamp(float(raw.get("count", 1)), 1, 20)))
    elif action_type == "set_hub_price":
        hub_id = str(raw.get("hub_id", "")).strip()
        if not hub_id:
            return None, f"scenario_actions[{index}].hub_id is required"
        min_price = getattr(city_engine, "MIN_PRICE", 0.10)
        max_price = getattr(city_engine, "MAX_PRICE", 0.80)
        normalized["hub_id"] = hub_id
        normalized["price"] = str(_clamp(float(raw.get("price", 0.2)), min_price, max_price))
    elif action_type == "set_hub_active_state":
        hub_id = str(raw.get("hub_id", "")).strip()
        if not hub_id:
            return None, f"scenario_actions[{index}].hub_id is required"
        normalized["hub_id"] = hub_id
        normalized["active"] = str(_parse_bool(raw.get("active", True), default=True))
    elif action_type == "set_signal_timing":
        zone = str(raw.get("zone", "")).strip()
        if not zone:
            return None, f"scenario_actions[{index}].zone is required"
        normalized["zone"] = zone
        normalized["multiplier"] = str(_clamp(float(raw.get("multiplier", 1.0)), MIN_SIGNAL_MULTIPLIER, 1.0))
    elif action_type == "reroute_traffic":
        zone = str(raw.get("zone", "")).strip()
        if not zone:
            return None, f"scenario_actions[{index}].zone is required"
        normalized["zone"] = zone
    elif action_type == "optimize_hub_pricing":
        normalized["objective"] = str(raw.get("objective", "balanced"))
        if "floor" in raw:
            normalized["floor"] = str(float(raw.get("floor", 0.0)))
        if "ceiling" in raw:
            normalized["ceiling"] = str(float(raw.get("ceiling", 1.0)))
        normalized["max_delta"] = str(float(raw.get("max_delta", 0.02)))
        normalized["fairness_weight"] = str(float(raw.get("fairness_weight", 0.5)))
    elif action_type == "rebalance_hub_load":
        normalized["strategy"] = str(raw.get("strategy", "hybrid"))
        normalized["max_actions"] = str(int(_clamp(float(raw.get("max_actions", 3)), 1, MAX_TOOL_ACTIONS)))
        zone = str(raw.get("zone", "")).strip()
        if zone:
            normalized["zone"] = zone
        normalized["aggressiveness"] = str(_clamp(float(raw.get("aggressiveness", 0.5)), 0.1, 1.0))

    return normalized, None


def _normalize_scenario_actions(city_engine, actions: list[dict]) -> tuple[list[dict], list[str]]:
    normalized: list[dict] = []
    errors: list[str] = []
    for index, raw in enumerate(actions[:MAX_TOOL_ACTIONS]):
        item, error = _normalize_scenario_action(city_engine, raw, index)
        if error:
            errors.append(error)
        elif item is not None:
            normalized.append(item)
    return normalized, errors


def _scenario_zone_population(city_engine, state: dict, zone_key: str) -> int:
    try:
        zx, zy = (int(v) for v in zone_key.split(","))
    except Exception:
        return 0
    zone_size = getattr(city_engine, "ZONE_SIZE", 20)
    x_min = zx * zone_size
    x_max = x_min + zone_size
    y_min = zy * zone_size
    y_max = y_min + zone_size
    return sum(1 for traffic in state.get("traffic", []) if x_min <= float(traffic.get("x", 0.0)) < x_max and y_min <= float(traffic.get("y", 0.0)) < y_max)


def _scenario_optimize_hub_pricing(city_engine, state: dict, objective: str = "balanced", floor: Optional[float] = None, ceiling: Optional[float] = None, max_delta: float = 0.02, fairness_weight: float = 0.5) -> dict:
    hubs = [hub for hub in state.get("hubs", []) if hub.get("active", True)]
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {"status": "skipped", "reason": f"need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs"}

    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    floor = _clamp(float(floor if floor is not None else min_price), min_price, max_price)
    ceiling = _clamp(float(ceiling if ceiling is not None else max_price), floor, max_price)
    max_delta = _clamp(float(max_delta), MIN_PRICE_DELTA_PER_CALL, MAX_PRICE_DELTA_PER_CALL)
    fairness_weight = _clamp(float(fairness_weight), 0.0, 1.0)
    objective = str(objective or "balanced").strip().lower()

    avg_queue = sum(float(hub.get("queue", 0.0)) for hub in hubs) / len(hubs)
    avg_price = sum(float(hub.get("price", 0.20)) for hub in hubs) / len(hubs)
    updates = []
    for hub in hubs:
        queue = float(hub.get("queue", 0.0))
        capacity = max(1.0, float(hub.get("capacity", 4)))
        price = float(hub.get("price", 0.20))
        pressure = (queue - avg_queue) / capacity
        fairness_pull = avg_price - price
        if objective == "queue_reduction":
            raw_delta = max_delta * pressure
        elif objective == "max_throughput":
            raw_delta = max_delta * (1.2 * pressure)
        elif objective == "fairness":
            raw_delta = (1.0 - fairness_weight) * max_delta * pressure + fairness_weight * fairness_pull
        else:
            raw_delta = 0.65 * max_delta * pressure + 0.35 * fairness_weight * fairness_pull
        delta = _clamp(raw_delta, -max_delta, max_delta)
        new_price = _clamp(price + delta, floor, ceiling)
        hub["price"] = new_price
        updates.append({"hub_id": hub.get("id", "unknown"), "old_price": round(price, 3), "new_price": round(new_price, 3), "delta": round(new_price - price, 3)})

    prices = [float(hub.get("price", 0.20)) for hub in hubs]
    spread = max(prices) - min(prices)
    if spread > MAX_PRICE_SPREAD:
        center = sum(prices) / len(prices)
        for hub in hubs:
            bounded = _clamp(float(hub.get("price", 0.20)), center - MAX_PRICE_SPREAD / 2, center + MAX_PRICE_SPREAD / 2)
            hub["price"] = _clamp(bounded, floor, ceiling)

    return {
        "status": "success",
        "objective": objective,
        "updates": updates,
        "constraints": {"floor": round(floor, 3), "ceiling": round(ceiling, 3), "max_delta": round(max_delta, 3), "max_spread": MAX_PRICE_SPREAD},
    }


def _scenario_rebalance_hub_load(city_engine, state: dict, strategy: str = "hybrid", max_actions: int = 3, zone: Optional[str] = None, aggressiveness: float = 0.5) -> dict:
    hubs = [hub for hub in state.get("hubs", []) if hub.get("active", True)]
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {"status": "skipped", "reason": f"need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs"}

    strategy = str(strategy or "hybrid").strip().lower()
    if strategy not in {"reroute", "price", "hybrid"}:
        strategy = "hybrid"
    max_actions = int(_clamp(float(max_actions), 1, MAX_TOOL_ACTIONS))
    aggressiveness = _clamp(float(aggressiveness), 0.1, 1.0)
    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    zone_congestion = state.setdefault("zone_congestion", {})
    zone_speed_limits = state.setdefault("zone_speed_limits", {})
    actions: list[dict] = []
    avg_queue = sum(float(hub.get("queue", 0.0)) for hub in hubs) / len(hubs)
    overloaded = [hub for hub in hubs if float(hub.get("queue", 0.0)) >= max(float(hub.get("capacity", 4)), avg_queue + 1)]
    underused = [hub for hub in hubs if float(hub.get("queue", 0.0)) <= max(0.0, avg_queue - 1)]

    if strategy in {"price", "hybrid"}:
        bump = _clamp(0.02 * aggressiveness, MIN_PRICE_DELTA_PER_CALL, MAX_PRICE_DELTA_PER_CALL)
        for hub in overloaded:
            if len(actions) >= max_actions:
                break
            old = float(hub.get("price", 0.20))
            new = _clamp(old + bump, min_price, max_price)
            hub["price"] = new
            actions.append({"type": "price_increase", "hub_id": hub.get("id", "unknown"), "old": round(old, 3), "new": round(new, 3)})
        for hub in underused:
            if len(actions) >= max_actions:
                break
            old = float(hub.get("price", 0.20))
            new = _clamp(old - bump, min_price, max_price)
            hub["price"] = new
            actions.append({"type": "price_decrease", "hub_id": hub.get("id", "unknown"), "old": round(old, 3), "new": round(new, 3)})

    if strategy in {"reroute", "hybrid"} and len(actions) < max_actions:
        zone_target = str(zone).strip() if zone else ""
        if not zone_target:
            hotspots = sorted(zone_congestion.items(), key=lambda item: item[1], reverse=True)
            zone_target = hotspots[0][0] if hotspots else ""
        if zone_target:
            zone_population = _scenario_zone_population(city_engine, state, zone_target)
            if zone_population <= MAX_TRAFFIC_REROUTE_PER_CALL:
                if zone_target in zone_congestion:
                    zone_congestion[zone_target] = _clamp(float(zone_congestion[zone_target]) * 0.75, 0.0, 1.0)
                actions.append({"type": "reroute", "zone": zone_target, "rerouted": zone_population})
                if len(actions) < max_actions:
                    throttle = _clamp(1.0 - 0.4 * aggressiveness, MIN_SIGNAL_MULTIPLIER, 1.0)
                    zone_speed_limits[zone_target] = throttle
                    actions.append({"type": "signal_timing", "zone": zone_target, "multiplier": round(throttle, 2)})
            else:
                actions.append({"type": "reroute_skipped", "zone": zone_target, "reason": f"zone population {zone_population} exceeds safety cap {MAX_TRAFFIC_REROUTE_PER_CALL}"})

    return {
        "status": "success",
        "strategy": strategy,
        "applied_actions": actions[:max_actions],
        "safety": {"max_actions": max_actions, "max_price_delta": MAX_PRICE_DELTA_PER_CALL, "max_reroute_agents": MAX_TRAFFIC_REROUTE_PER_CALL},
    }


def _apply_scenario_actions(city_engine, state: dict, actions: list[dict]) -> list[dict]:
    hubs = state.get("hubs", [])
    residents = state.get("residents", [])
    traffic = state.get("traffic", [])
    zone_congestion = state.setdefault("zone_congestion", {})
    zone_speed_limits = state.setdefault("zone_speed_limits", {})
    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    applied = []

    for raw in actions[:MAX_TOOL_ACTIONS]:
        action_type = str(raw.get("type", "")).strip().lower()
        if action_type == "set_weather":
            weather = str(raw.get("weather", "sunny")).strip().lower()
            if weather in WEATHER_CONFIG:
                state["weather"] = weather
                applied.append({"type": "set_weather", "weather": weather})
        elif action_type == "add_city_hub":
            count = int(_clamp(float(raw.get("count", 1)), 1, 5))
            base_idx = len(hubs)
            for index in range(count):
                hubs.append({"id": f"sim_hub_{base_idx + index}", "x": 50.0, "y": 50.0, "price": 0.20, "queue": 0, "queue_total": 0, "waiting": 0, "charging": 0, "slots_used": 0, "capacity": 4, "active": True})
            applied.append({"type": "add_city_hub", "count": str(count)})
        elif action_type == "add_city_resident":
            count = int(_clamp(float(raw.get("count", 1)), 1, 20))
            base_idx = len(residents)
            for index in range(count):
                residents.append({"id": f"sim_res_{base_idx + index}", "x": 50.0, "y": 50.0, "battery": 55.0, "charging": False, "state": "driving"})
            applied.append({"type": "add_city_resident", "count": str(count)})
        elif action_type == "add_city_traffic":
            count = int(_clamp(float(raw.get("count", 1)), 1, 20))
            base_idx = len(traffic)
            for index in range(count):
                traffic.append({"id": f"sim_traffic_{base_idx + index}", "x": 50.0, "y": 50.0})
            applied.append({"type": "add_city_traffic", "count": str(count)})
        elif action_type == "set_hub_price":
            hub_id = str(raw.get("hub_id", ""))
            price = _clamp(float(raw.get("price", 0.2)), min_price, max_price)
            hub = next((candidate for candidate in hubs if str(candidate.get("id")) == hub_id), None)
            if hub:
                hub["price"] = price
                applied.append({"type": "set_hub_price", "hub_id": hub_id, "price": str(round(price, 3))})
        elif action_type == "set_hub_active_state":
            hub_id = str(raw.get("hub_id", ""))
            active = bool(raw.get("active", True))
            hub = next((candidate for candidate in hubs if str(candidate.get("id")) == hub_id), None)
            if hub:
                hub["active"] = active
                applied.append({"type": "set_hub_active_state", "hub_id": hub_id, "active": str(active)})
        elif action_type == "set_signal_timing":
            zone = str(raw.get("zone", ""))
            if zone:
                multiplier = _clamp(float(raw.get("multiplier", 1.0)), MIN_SIGNAL_MULTIPLIER, 1.0)
                zone_speed_limits[zone] = multiplier
                if zone in zone_congestion:
                    zone_congestion[zone] = _clamp(float(zone_congestion[zone]) * multiplier, 0.0, 1.0)
                applied.append({"type": "set_signal_timing", "zone": zone, "multiplier": str(round(multiplier, 2))})
        elif action_type == "reroute_traffic":
            zone = str(raw.get("zone", ""))
            if zone and zone in zone_congestion:
                zone_congestion[zone] = _clamp(float(zone_congestion[zone]) * 0.75, 0.0, 1.0)
                applied.append({"type": "reroute_traffic", "zone": zone})
        elif action_type == "optimize_hub_pricing":
            applied.append({"type": "optimize_hub_pricing", "outcome": str(_scenario_optimize_hub_pricing(city_engine, state, objective=str(raw.get("objective", "balanced")), floor=raw.get("floor"), ceiling=raw.get("ceiling"), max_delta=float(raw.get("max_delta", 0.02)), fairness_weight=float(raw.get("fairness_weight", 0.5))))})
        elif action_type == "rebalance_hub_load":
            applied.append({"type": "rebalance_hub_load", "outcome": str(_scenario_rebalance_hub_load(city_engine, state, strategy=str(raw.get("strategy", "hybrid")), max_actions=int(raw.get("max_actions", 3)), zone=raw.get("zone"), aggressiveness=float(raw.get("aggressiveness", 0.5))))})

    return applied


def _run_projection(city_engine, state: dict, horizon_ticks: int, runs: int) -> dict:
    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    outcomes = []
    runs_trajectories = []
    
    for _ in range(runs):
        simulation = copy.deepcopy(state)
        hubs = simulation.get("hubs", [])
        residents = simulation.get("residents", [])
        weather = str(simulation.get("weather", "sunny"))
        w_config = WEATHER_CONFIG.get(weather, WEATHER_CONFIG["sunny"])
        # Weather affects both drain rate (more seeking) and charging speed
        weather_drain_mult = w_config["drain_multiplier"]
        weather_charge_mult = w_config["charge_multiplier"]
        
        trajectory = []
        for _tick in range(horizon_ticks):
            active_hubs = [hub for hub in hubs if hub.get("active", True)]
            if not active_hubs:
                trajectory.append(_state_metrics(simulation))
                continue
                
            avg_congestion = _state_avg_congestion(simulation)
            
            # Simple state transition modeling for credibility
            driving = [r for r in residents if r.get("state") == "driving"]
            seeking = [r for r in residents if r.get("state") == "seeking"]
            charging = [r for r in residents if r.get("state") == "charging"]
            
            # 1. Driving -> Seeking (battery drain)
            new_seeking_rate = 0.05 * weather_drain_mult
            for r in driving:
                if random.random() < new_seeking_rate:
                    r["state"] = "seeking"
                    
            # 2. Seeking -> Waiting (arrival rate influenced by congestion)
            arrival_rate = 0.15 * (1.0 - 0.5 * avg_congestion)
            for r in seeking:
                if random.random() < arrival_rate:
                    r["state"] = "waiting"
                    
            # 3. Charging -> Driving (completion rate)
            completion_rate = 0.20 * weather_charge_mult
            for r in charging:
                if random.random() < completion_rate:
                    r["state"] = "driving"
                    
            # 4. Transition Waiting -> Charging based on available slots
            waiting_now = [r for r in residents if r.get("state") == "waiting"]
            total_waiting = len(waiting_now)
            total_charging = len([r for r in residents if r.get("state") == "charging"])
            total_capacity = sum(int(h.get("capacity", 4)) for h in active_hubs)
            
            available_slots = max(0, total_capacity - total_charging)
            can_start = min(total_waiting, available_slots)
            
            for r in waiting_now[:can_start]:
                r["state"] = "charging"
                
            # 5. Distribute remaining queue to hubs and update dynamic prices
            remaining_waiting = len([r for r in residents if r.get("state") == "waiting"])
            if remaining_waiting > 0:
                base_queue = remaining_waiting / len(active_hubs)
                for hub in active_hubs:
                    capacity = float(hub.get("capacity", 4))
                    price_factor = 1.0 + (0.5 - float(hub.get("price", 0.2)))
                    queue_alloc = base_queue * price_factor
                    
                    hub["queue"] = queue_alloc
                    hub["queue_total"] = queue_alloc
                    
                    pressure = queue_alloc / max(1.0, capacity)
                    new_price = float(hub.get("price", 0.2)) + 0.01 * pressure - 0.005 * (1.0 - pressure)
                    hub["price"] = _clamp(new_price, min_price, max_price)
            else:
                for hub in active_hubs:
                    hub["queue"] = 0.0
                    hub["queue_total"] = 0.0
                    new_price = float(hub.get("price", 0.2)) - 0.005
                    hub["price"] = _clamp(new_price, min_price, max_price)

            # Update traffic congestion (simple decay + stochastic + throttle)
            for zone, cong in simulation.get("zone_congestion", {}).items():
                throttle = simulation.get("zone_speed_limits", {}).get(zone, 1.0)
                simulation["zone_congestion"][zone] = _clamp(cong * 0.95 * throttle + random.uniform(-0.02, 0.05), 0.0, 1.0)

            trajectory.append(_state_metrics(simulation))

        runs_trajectories.append(trajectory)
        outcomes.append(_state_metrics(simulation))

    # Compute average trajectory across runs
    avg_trajectory = []
    if runs_trajectories and horizon_ticks > 0:
        for tick in range(horizon_ticks):
            tick_metrics = [runs_trajectories[run][tick] for run in range(runs)]
            avg_trajectory.append({
                "total_queue": round(sum(m["total_queue"] for m in tick_metrics) / runs, 3),
                "avg_price": round(sum(m["avg_price"] for m in tick_metrics) / runs, 3),
                "avg_congestion": round(sum(m["avg_congestion"] for m in tick_metrics) / runs, 3),
                "active_hubs": round(sum(m["active_hubs"] for m in tick_metrics) / runs, 3),
            })

    return {
        "total_queue": round(sum(outcome["total_queue"] for outcome in outcomes) / len(outcomes), 3),
        "avg_price": round(sum(outcome["avg_price"] for outcome in outcomes) / len(outcomes), 3),
        "avg_congestion": round(sum(outcome["avg_congestion"] for outcome in outcomes) / len(outcomes), 3),
        "active_hubs": round(sum(outcome["active_hubs"] for outcome in outcomes) / len(outcomes), 3),
        "trajectory": avg_trajectory
    }


def simulate_scenario(city_engine, scenario_actions: list[dict], horizon_ticks: int = 30, runs: int = 3) -> dict:
    horizon_ticks = int(_clamp(float(horizon_ticks), 5, 120))
    runs = int(_clamp(float(runs), 1, 10))
    normalized_actions, validation_errors = _normalize_scenario_actions(city_engine, scenario_actions or [])
    if validation_errors:
        return {"status": "error", "message": "Invalid scenario_actions payload.", "validation_errors": validation_errors, "normalized_actions": normalized_actions, "safety": {"mutates_live_state": False, "max_actions": MAX_TOOL_ACTIONS}}

    baseline_state = copy.deepcopy(city_engine.get_state())
    scenario_state = copy.deepcopy(baseline_state)
    applied = _apply_scenario_actions(city_engine, scenario_state, normalized_actions)
    baseline = _run_projection(city_engine, baseline_state, horizon_ticks=horizon_ticks, runs=runs)
    scenario = _run_projection(city_engine, scenario_state, horizon_ticks=horizon_ticks, runs=runs)
    delta = {
        "total_queue": round(scenario["total_queue"] - baseline["total_queue"], 3),
        "avg_price": round(scenario["avg_price"] - baseline["avg_price"], 3),
        "avg_congestion": round(scenario["avg_congestion"] - baseline["avg_congestion"], 3),
        "active_hubs": round(scenario["active_hubs"] - baseline["active_hubs"], 3),
    }
    recommendation = "adopt"
    if delta["total_queue"] > 0.5 and delta["avg_congestion"] > 0.03:
        recommendation = "reject"
    elif delta["total_queue"] > 0.0:
        recommendation = "caution"

    return {
        "status": "success",
        "horizon_ticks": horizon_ticks,
        "runs": runs,
        "applied_actions": applied,
        "baseline": baseline,
        "scenario": scenario,
        "delta": delta,
        "recommendation": recommendation,
        "safety": {"mutates_live_state": False, "max_actions": MAX_TOOL_ACTIONS, "max_horizon_ticks": 120, "max_runs": 10},
    }


def build_scenario_schema(city_engine) -> dict:
    return {
        "endpoint": "/city/scenario/schema",
        "purpose": "Catalog of supported scenario action shapes for safe what-if simulation payloads.",
        "simulate_scenario": {
            "horizon_ticks": {"type": "integer", "min": 5, "max": 120, "default": 30},
            "runs": {"type": "integer", "min": 1, "max": 10, "default": 3},
            "max_actions": MAX_TOOL_ACTIONS,
            "supported_action_types": list(sorted(SCENARIO_ACTION_ALLOWED_FIELDS.keys())),
        },
        "actions": {
            "set_weather": {"required": ["type", "weather"], "optional": [], "constraints": {"weather": ["sunny", "storm", "extreme_heat"]}, "example": {"type": "set_weather", "weather": "storm"}},
            "add_city_hub": {"required": ["type"], "optional": ["count"], "constraints": {"count": {"min": 1, "max": 20, "default": 1}}, "example": {"type": "add_city_hub", "count": 2}},
            "add_city_resident": {"required": ["type"], "optional": ["count"], "constraints": {"count": {"min": 1, "max": 20, "default": 1}}, "example": {"type": "add_city_resident", "count": 8}},
            "add_city_traffic": {"required": ["type"], "optional": ["count"], "constraints": {"count": {"min": 1, "max": 20, "default": 1}}, "example": {"type": "add_city_traffic", "count": 6}},
            "set_hub_price": {"required": ["type", "hub_id", "price"], "optional": [], "constraints": {"price": {"min": getattr(city_engine, 'MIN_PRICE', 0.10), "max": getattr(city_engine, 'MAX_PRICE', 0.80)}}, "example": {"type": "set_hub_price", "hub_id": "hub_0", "price": 0.28}},
            "set_hub_active_state": {"required": ["type", "hub_id", "active"], "optional": [], "constraints": {"active": [True, False]}, "example": {"type": "set_hub_active_state", "hub_id": "hub_1", "active": False}},
            "reroute_traffic": {"required": ["type", "zone"], "optional": [], "constraints": {"zone": "string formatted as 'zx,zy'"}, "example": {"type": "reroute_traffic", "zone": "1,2"}},
            "set_signal_timing": {"required": ["type", "zone"], "optional": ["multiplier"], "constraints": {"multiplier": {"min": MIN_SIGNAL_MULTIPLIER, "max": 1.0, "default": 1.0}}, "example": {"type": "set_signal_timing", "zone": "1,2", "multiplier": 0.6}},
            "optimize_hub_pricing": {"required": ["type"], "optional": ["objective", "floor", "ceiling", "max_delta", "fairness_weight"], "constraints": {"objective": ["balanced", "queue_reduction", "max_throughput", "fairness"], "max_delta": {"min": MIN_PRICE_DELTA_PER_CALL, "max": MAX_PRICE_DELTA_PER_CALL, "default": 0.02}, "fairness_weight": {"min": 0.0, "max": 1.0, "default": 0.5}}, "example": {"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03}},
            "rebalance_hub_load": {"required": ["type"], "optional": ["strategy", "max_actions", "zone", "aggressiveness"], "constraints": {"strategy": ["price", "reroute", "hybrid"], "max_actions": {"min": 1, "max": MAX_TOOL_ACTIONS, "default": 3}, "aggressiveness": {"min": 0.1, "max": 1.0, "default": 0.5}}, "example": {"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7}},
        },
        "examples": [
            {"type": "set_weather", "weather": "storm"},
            {"type": "add_city_hub", "count": 2},
            {"type": "set_signal_timing", "zone": "1,2", "multiplier": 0.55},
            {"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03},
            {"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7},
        ],
    }
