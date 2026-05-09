from typing import Any


def build_city_scenario_schema(
    *,
    city_engine: Any,
    supported_action_types: list[str],
    max_actions: int,
    min_signal_multiplier: float,
    min_price_delta: float,
    max_price_delta: float,
) -> dict:
    return {
        "endpoint": "/city/scenario/schema",
        "purpose": "Catalog of supported scenario action shapes for safe what-if simulation payloads.",
        "simulate_scenario": {
            "horizon_ticks": {"type": "integer", "min": 5, "max": 120, "default": 30},
            "runs": {"type": "integer", "min": 1, "max": 10, "default": 3},
            "max_actions": max_actions,
            "supported_action_types": supported_action_types,
        },
        "actions": {
            "set_weather": {
                "required": ["type", "weather"],
                "optional": [],
                "constraints": {"weather": ["sunny", "storm", "extreme_heat"]},
                "example": {"type": "set_weather", "weather": "storm"},
            },
            "add_city_hub": {
                "required": ["type"],
                "optional": ["count"],
                "constraints": {"count": {"min": 1, "max": 20, "default": 1}},
                "example": {"type": "add_city_hub", "count": 2},
            },
            "add_city_resident": {
                "required": ["type"],
                "optional": ["count"],
                "constraints": {"count": {"min": 1, "max": 20, "default": 1}},
                "example": {"type": "add_city_resident", "count": 8},
            },
            "add_city_traffic": {
                "required": ["type"],
                "optional": ["count"],
                "constraints": {"count": {"min": 1, "max": 20, "default": 1}},
                "example": {"type": "add_city_traffic", "count": 6},
            },
            "set_hub_price": {
                "required": ["type", "hub_id", "price"],
                "optional": [],
                "constraints": {
                    "price": {
                        "min": getattr(city_engine, "MIN_PRICE", 0.10),
                        "max": getattr(city_engine, "MAX_PRICE", 0.80),
                    }
                },
                "example": {"type": "set_hub_price", "hub_id": "hub_0", "price": 0.28},
            },
            "set_hub_active_state": {
                "required": ["type", "hub_id", "active"],
                "optional": [],
                "constraints": {"active": [True, False]},
                "example": {"type": "set_hub_active_state", "hub_id": "hub_1", "active": False},
            },
            "reroute_traffic": {
                "required": ["type", "zone"],
                "optional": [],
                "constraints": {"zone": "string formatted as 'zx,zy'"},
                "example": {"type": "reroute_traffic", "zone": "1,2"},
            },
            "set_signal_timing": {
                "required": ["type", "zone"],
                "optional": ["multiplier"],
                "constraints": {"multiplier": {"min": min_signal_multiplier, "max": 1.0, "default": 1.0}},
                "example": {"type": "set_signal_timing", "zone": "1,2", "multiplier": 0.6},
            },
            "optimize_hub_pricing": {
                "required": ["type"],
                "optional": ["objective", "floor", "ceiling", "max_delta", "fairness_weight"],
                "constraints": {
                    "objective": ["balanced", "queue_reduction", "max_throughput", "fairness"],
                    "max_delta": {"min": min_price_delta, "max": max_price_delta, "default": 0.02},
                    "fairness_weight": {"min": 0.0, "max": 1.0, "default": 0.5},
                },
                "example": {"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03},
            },
            "rebalance_hub_load": {
                "required": ["type"],
                "optional": ["strategy", "max_actions", "zone", "aggressiveness"],
                "constraints": {
                    "strategy": ["price", "reroute", "hybrid"],
                    "max_actions": {"min": 1, "max": max_actions, "default": 3},
                    "aggressiveness": {"min": 0.1, "max": 1.0, "default": 0.5},
                },
                "example": {"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7},
            },
        },
        "examples": [
            [{"type": "set_weather", "weather": "storm"}],
            [{"type": "add_city_hub", "count": 2}, {"type": "add_city_resident", "count": 10}],
            [{"type": "set_hub_price", "hub_id": "hub_0", "price": 0.32}],
            [{"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03}],
            [{"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7}],
        ],
    }