from typing import Any


def _tool(name: str, description: str, parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def _scalar_prop(kind: str, description: str | None = None, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": kind}
    if description:
        payload["description"] = description
    payload.update(extra)
    return payload


def _bounded_number(minimum: float | None = None, maximum: float | None = None, description: str | None = None) -> dict[str, Any]:
    payload = _scalar_prop("number", description)
    if minimum is not None:
        payload["minimum"] = minimum
    if maximum is not None:
        payload["maximum"] = maximum
    return payload


def _bounded_integer(minimum: int | None = None, maximum: int | None = None, description: str | None = None) -> dict[str, Any]:
    payload = _scalar_prop("integer", description)
    if minimum is not None:
        payload["minimum"] = minimum
    if maximum is not None:
        payload["maximum"] = maximum
    return payload


def build_city_chat_tools() -> list[dict[str, Any]]:
    common_zone = {"type": "string", "description": "Zone key in 'zx,zy' format."}
    weather_enum = ["sunny", "storm", "extreme_heat"]
    action_enum = [
        "set_weather",
        "add_city_hub",
        "add_city_resident",
        "add_city_traffic",
        "set_hub_price",
        "set_hub_active_state",
        "reroute_traffic",
        "set_signal_timing",
        "optimize_hub_pricing",
        "rebalance_hub_load",
    ]

    return [
        _tool(
            "set_hub_active_state",
            "Set a city charging hub active or non-active state by hub id.",
            {
                "type": "object",
                "properties": {
                    "hub_id": {"type": "string", "description": "Hub id, e.g. hub_0"},
                    "active": _scalar_prop("boolean", "true=active, false=non-active"),
                },
                "required": ["hub_id", "active"],
            },
        ),
        _tool(
            "trigger_hub_maintenance",
            "Randomly disable one active city hub to simulate breakdown/maintenance.",
            {"type": "object", "properties": {}},
        ),
        _tool(
            "set_hub_price",
            "Set city hub price manually.",
            {
                "type": "object",
                "properties": {
                    "hub_id": {"type": "string"},
                    "price": _scalar_prop("number"),
                },
                "required": ["hub_id", "price"],
            },
        ),
        _tool("add_city_resident", "Add one EV resident to city simulation.", {"type": "object", "properties": {}}),
        _tool("add_city_hub", "Add one charging hub to city simulation.", {"type": "object", "properties": {}}),
        _tool("add_city_traffic", "Add one traffic agent to city simulation.", {"type": "object", "properties": {}}),
        _tool(
            "reroute_traffic",
            "Reroute all traffic agents currently in a congested zone to new destinations outside that zone, immediately reducing congestion there.",
            {
                "type": "object",
                "properties": {"zone": common_zone},
                "required": ["zone"],
            },
        ),
        _tool(
            "set_signal_timing",
            "Adjust smart traffic signal timing in a zone by setting a speed multiplier. Lower multiplier throttles traffic flow (simulates red-light phases). 1.0 = normal, 0.3 = heavy throttle. Use to prevent new vehicles from flooding a congested zone.",
            {
                "type": "object",
                "properties": {
                    "zone": common_zone,
                    "multiplier": _scalar_prop("number", "Speed multiplier 0.1..1.0. 1.0 clears the restriction."),
                },
                "required": ["zone", "multiplier"],
            },
        ),
        _tool(
            "run_python",
            (
                "Execute a Python code snippet to analyse the current live city simulation data. "
                "Two variables are pre-injected: "
                "`state` (dict) - full simulation snapshot with keys: residents (list of {id,x,y,state,battery,charging,current_hub}), "
                "hubs (list of {id,x,y,active,price,capacity,queue,charging_slots}), "
                "traffic (list of {id,x,y}), zone_congestion (dict), zone_speed_limits (dict), weather (str); "
                "`metrics` (dict) - aggregated city metrics with keys: residents, traffic_agents, active_hubs, total_queue, avg_price, "
                "charging_count, seeking_count, avg_congestion, congestion_hotspot, weather. "
                "Use print() to output results. Allowed imports: json, math, statistics, collections, itertools, datetime. "
                "Max code length: 4000 chars. Execution timeout: 5 seconds."
            ),
            {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute. Use print() to return analysis results."},
                },
                "required": ["code"],
            },
        ),
        _tool(
            "forecast_city_load",
            "Forecast short-term city charging demand, queue pressure, and pricing trends.",
            {
                "type": "object",
                "properties": {
                    "horizon_ticks": _bounded_integer(5, 120, "Forecast horizon in simulation ticks (5-120, default 30)."),
                },
            },
        ),
        _tool(
            "analyze_resident_segments",
            "Analyze resident cohorts by battery and behavior to surface demand patterns.",
            {"type": "object", "properties": {}},
        ),
        _tool(
            "evaluate_weather_impact",
            "Estimate how target weather conditions could impact queue pressure and congestion.",
            {
                "type": "object",
                "properties": {
                    "weather": {"type": "string", "description": "Target weather: sunny, storm, extreme_heat."},
                    "horizon_ticks": _bounded_integer(5, 120, "Projection horizon in ticks (5-120, default 30)."),
                },
                "required": ["weather"],
            },
        ),
        _tool(
            "rebalance_hub_load",
            "Rebalance charging pressure across hubs with bounded pricing and traffic controls.",
            {
                "type": "object",
                "properties": {
                    "strategy": {"type": "string", "description": "rebalance strategy: price, reroute, or hybrid (default)."},
                    "max_actions": _bounded_integer(1, 5, "Max optimization actions for this call (1-5)."),
                    "zone": {"type": "string", "description": "Optional target zone key in 'zx,zy' format for reroute actions."},
                    "aggressiveness": _bounded_number(0.1, 1.0, "Optimization aggressiveness from 0.1 to 1.0."),
                },
            },
        ),
        _tool(
            "optimize_hub_pricing",
            "Apply dynamic hub price optimization with hard safety bounds.",
            {
                "type": "object",
                "properties": {
                    "objective": {"type": "string", "description": "Optimization objective: balanced, queue_reduction, max_throughput, fairness."},
                    "floor": _scalar_prop("number", "Optional minimum allowed price during optimization."),
                    "ceiling": _scalar_prop("number", "Optional maximum allowed price during optimization."),
                    "max_delta": _bounded_number(0.005, 0.05, "Maximum per-hub price delta for this call (bounded internally)."),
                    "fairness_weight": _bounded_number(0.0, 1.0, "Fairness bias between 0.0 and 1.0."),
                },
            },
        ),
        _tool(
            "simulate_scenario",
            "Run a safe what-if simulation on copied city state and compare baseline vs scenario outcomes.",
            {
                "type": "object",
                "properties": {
                    "scenario_actions": {
                        "type": "array",
                        "description": (
                            "List of scenario action objects. Each action must include a 'type'. Supported shapes: "
                            "{type:'set_weather', weather:'sunny|storm|extreme_heat'}; "
                            "{type:'add_city_hub', count:int}; "
                            "{type:'add_city_resident', count:int}; "
                            "{type:'add_city_traffic', count:int}; "
                            "{type:'set_hub_price', hub_id:str, price:number}; "
                            "{type:'set_hub_active_state', hub_id:str, active:boolean}; "
                            "{type:'reroute_traffic', zone:'zx,zy'}; "
                            "{type:'set_signal_timing', zone:'zx,zy', multiplier:number}; "
                            "{type:'optimize_hub_pricing', objective:'balanced|queue_reduction|max_throughput|fairness', floor?:number, ceiling?:number, max_delta?:number, fairness_weight?:number}; "
                            "{type:'rebalance_hub_load', strategy:'price|reroute|hybrid', max_actions?:int, zone?:str, aggressiveness?:number}. Do not include unknown fields."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Action discriminator.", "enum": action_enum},
                                "weather": {"type": "string", "enum": weather_enum},
                                "count": _bounded_integer(1, 20),
                                "hub_id": {"type": "string"},
                                "price": _scalar_prop("number"),
                                "active": _scalar_prop("boolean"),
                                "zone": {"type": "string", "description": "Zone key formatted like '0,2' or '3,1'."},
                                "multiplier": _bounded_number(0.4, 1.0),
                                "objective": {"type": "string", "enum": ["balanced", "queue_reduction", "max_throughput", "fairness"]},
                                "floor": _scalar_prop("number"),
                                "ceiling": _scalar_prop("number"),
                                "max_delta": _bounded_number(0.005, 0.05),
                                "fairness_weight": _bounded_number(0.0, 1.0),
                                "strategy": {"type": "string", "enum": ["price", "reroute", "hybrid"]},
                                "max_actions": _bounded_integer(1, 5),
                                "aggressiveness": _bounded_number(0.1, 1.0),
                            },
                            "required": ["type"],
                        },
                    },
                    "horizon_ticks": _bounded_integer(5, 120, "Projection horizon in ticks (5-120)."),
                    "runs": _bounded_integer(1, 10, "Monte Carlo run count (1-10)."),
                },
                "required": ["scenario_actions"],
            },
        ),
    ]
