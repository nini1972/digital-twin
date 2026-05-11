import json
import subprocess
from typing import Any, Callable


def _handle_set_weather(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    weather = function_args.get("weather", "sunny")
    city_engine.weather = weather
    return {"status": "success", "message": f"City weather set to {weather}."}


def _handle_set_hub_active_state(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    from simulation import ResidentState

    hub_id = function_args.get("hub_id")
    active = bool(function_args.get("active", True))
    hub = next((h for h in city_engine.hubs if h.id == hub_id), None)
    if not hub:
        return {"status": "error", "message": f"Hub {hub_id} not found."}

    hub.active = active
    impacted = 0
    if not active:
        for res in city_engine.residents:
            if getattr(res, "current_hub", None) is hub and getattr(res, "state", None) in (ResidentState.WAITING, ResidentState.CHARGING):
                impacted += 1
                hub.release(res.id)
                res.current_hub = None
                res.state = ResidentState.SEEKING
        hub.waiting_queue.clear()
        hub.charging_slots.clear()

    return {
        "status": "success",
        "message": f"Hub {hub.id} set to {'ACTIVE' if active else 'NON_ACTIVE' }.",
        "impacted_residents": impacted,
    }


def _handle_trigger_hub_maintenance(city_engine: Any) -> dict[str, Any]:
    import random

    active_hubs = [h for h in city_engine.hubs if h.active]
    if not active_hubs:
        return {"status": "error", "message": "No active hubs available for maintenance."}
    selected = random.choice(active_hubs)
    selected.active = False
    selected.waiting_queue.clear()
    selected.charging_slots.clear()
    return {
        "status": "success",
        "message": f"Maintenance triggered: {selected.id} set to NON_ACTIVE.",
    }


def _handle_set_hub_price(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    hub_id = function_args.get("hub_id")
    price = function_args.get("price")
    hub = next((h for h in city_engine.hubs if h.id == hub_id), None)
    if not hub:
        return {"status": "error", "message": f"Hub {hub_id} not found."}
    hub.price = float(price)
    return {"status": "success", "message": f"Set {hub.id} price to {hub.price:.3f}."}


def _handle_add_city_resident(city_engine: Any) -> dict[str, Any]:
    from simulation import ResidentAgent

    new_res = ResidentAgent(f"res_{len(city_engine.residents)}")
    city_engine.residents.append(new_res)
    return {"status": "success", "message": f"Added resident {new_res.id}."}


def _handle_add_city_hub(city_engine: Any) -> dict[str, Any]:
    from simulation import ChargingHubAgent

    new_hub = ChargingHubAgent(f"hub_{len(city_engine.hubs)}")
    city_engine.hubs.append(new_hub)
    return {"status": "success", "message": f"Added hub {new_hub.id}."}


def _handle_add_city_traffic(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    from city_simulation import TrafficFlowAgent
    import random

    count = int(function_args.get("count", 1))
    zone = function_args.get("zone", "")
    added = 0
    for _ in range(count):
        new_t = TrafficFlowAgent(f"traffic_{len(city_engine.traffic_agents)}")
        if zone:
            try:
                zx, zy = (int(v) for v in zone.split(","))
                zone_size = getattr(city_engine, "ZONE_SIZE", 20)
                new_t.x = zx * zone_size + random.uniform(0, zone_size)
                new_t.y = zy * zone_size + random.uniform(0, zone_size)
            except Exception:
                pass
        city_engine.traffic_agents.append(new_t)
        added += 1
    return {"status": "success", "message": f"Added {added} traffic agent(s)."}


def _handle_reroute_traffic(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    zone = function_args.get("zone", "")
    if not zone:
        return {"status": "error", "message": "zone parameter required."}
    count = city_engine.reroute_traffic_from_zone(zone)
    return {
        "status": "success",
        "message": f"Rerouted {count} traffic agent(s) out of zone {zone}.",
        "rerouted": count,
    }


def _handle_set_signal_timing(function_args: dict[str, Any], city_engine: Any) -> dict[str, Any]:
    zone = function_args.get("zone", "")
    multiplier = float(function_args.get("multiplier", 1.0))
    if not zone:
        return {"status": "error", "message": "zone parameter required."}
    city_engine.set_zone_speed_limit(zone, multiplier)
    action = "cleared" if multiplier >= 1.0 else f"set to {multiplier:.1f}x"
    return {
        "status": "success",
        "message": f"Signal timing for zone {zone} {action}.",
    }


def _handle_run_python(function_args: dict[str, Any], city_engine: Any, runner_path: str, python_executable: str) -> dict[str, Any]:
    code = function_args.get("code", "")
    if not code:
        return {"status": "error", "message": "code parameter required."}
    if len(code) > 4000:
        return {"status": "error", "message": "Code exceeds 4000 character limit."}

    try:
        sim_state = city_engine.get_state()
        sim_metrics = city_engine.get_city_metrics()
        proc = subprocess.run(
            [python_executable, runner_path],
            input=json.dumps({"code": code, "state": sim_state, "metrics": sim_metrics}),
            capture_output=True,
            text=True,
            timeout=5,
        )
        runner_result = json.loads(proc.stdout) if proc.stdout.strip() else {"output": "", "error": "No output from runner."}
        if runner_result.get("error"):
            return {"status": "error", "message": runner_result["error"], "output": runner_result.get("output", "")}
        return {"status": "success", "output": runner_result.get("output", "")}
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Code execution timed out after 5 seconds."}
    except Exception as exc:
        return {"status": "error", "message": f"Runner error: {exc}"}


def _handle_forecast_city_load(function_args: dict[str, Any], helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    horizon = int(function_args.get("horizon_ticks", 30))
    return {"status": "success", "forecast": helpers["forecast_city_load"](horizon)}


def _handle_analyze_resident_segments(helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    return {"status": "success", "segments": helpers["analyze_resident_segments"]()}


def _handle_evaluate_weather_impact(function_args: dict[str, Any], helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    weather = str(function_args.get("weather", "sunny"))
    horizon = int(function_args.get("horizon_ticks", 30))
    return {"status": "success", "impact": helpers["evaluate_weather_impact"](weather, horizon)}


def _handle_rebalance_hub_load(function_args: dict[str, Any], helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    return helpers["rebalance_hub_load"](
        strategy=str(function_args.get("strategy", "hybrid")),
        max_actions=int(function_args.get("max_actions", 3)),
        zone=function_args.get("zone"),
        aggressiveness=float(function_args.get("aggressiveness", 0.5)),
    )


def _handle_optimize_hub_pricing(function_args: dict[str, Any], helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    return helpers["optimize_hub_pricing"](
        objective=str(function_args.get("objective", "balanced")),
        floor=function_args.get("floor"),
        ceiling=function_args.get("ceiling"),
        max_delta=float(function_args.get("max_delta", 0.02)),
        fairness_weight=float(function_args.get("fairness_weight", 0.5)),
    )


def _handle_simulate_scenario(function_args: dict[str, Any], helpers: dict[str, Callable[..., Any]]) -> dict[str, Any]:
    scenario_actions = function_args.get("scenario_actions", [])
    try:
        horizon_ticks = int(function_args.get("horizon_ticks", 30))
    except (TypeError, ValueError):
        horizon_ticks = 30
    try:
        runs = int(function_args.get("runs", 3))
    except (TypeError, ValueError):
        runs = 3
    if not isinstance(scenario_actions, list):
        return {"status": "error", "message": "scenario_actions must be an array of action objects."}
    return helpers["simulate_scenario"](scenario_actions=scenario_actions, horizon_ticks=horizon_ticks, runs=runs)


def execute_city_tool_call(
    function_name: str,
    function_args: dict[str, Any],
    city_engine: Any,
    helpers: dict[str, Callable[..., Any]],
    runner_path: str,
    python_executable: str,
) -> dict[str, Any]:
    handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "set_weather": lambda: _handle_set_weather(function_args, city_engine),
        "set_hub_active_state": lambda: _handle_set_hub_active_state(function_args, city_engine),
        "trigger_hub_maintenance": lambda: _handle_trigger_hub_maintenance(city_engine),
        "set_hub_price": lambda: _handle_set_hub_price(function_args, city_engine),
        "add_city_resident": lambda: _handle_add_city_resident(city_engine),
        "add_city_hub": lambda: _handle_add_city_hub(city_engine),
        "add_city_traffic": lambda: _handle_add_city_traffic(function_args, city_engine),
        "reroute_traffic": lambda: _handle_reroute_traffic(function_args, city_engine),
        "set_signal_timing": lambda: _handle_set_signal_timing(function_args, city_engine),
        "run_python": lambda: _handle_run_python(function_args, city_engine, runner_path, python_executable),
        "forecast_city_load": lambda: _handle_forecast_city_load(function_args, helpers),
        "analyze_resident_segments": lambda: _handle_analyze_resident_segments(helpers),
        "evaluate_weather_impact": lambda: _handle_evaluate_weather_impact(function_args, helpers),
        "rebalance_hub_load": lambda: _handle_rebalance_hub_load(function_args, helpers),
        "optimize_hub_pricing": lambda: _handle_optimize_hub_pricing(function_args, helpers),
        "simulate_scenario": lambda: _handle_simulate_scenario(function_args, helpers),
    }

    handler = handlers.get(function_name)
    if handler is None:
        return {"status": "error", "message": "Unknown city tool."}
    return handler()
