from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import pathlib
from dotenv import load_dotenv
from typing import Optional, List, Dict
import json
import uuid
import time
import copy
import random
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from openai import OpenAI
from context import prompt
from simulation import engine
from city_simulation import city_engine
from city_context import city_prompt
from redis_bus import bus
from memory.chroma import vector_memory
from agents.scout import EVScoutAgent, TrafficScoutAgent
from agents.analyzer import DemandAnalyzerAgent, CongestionAnalyzerAgent
from agents.chief import ChiefOracleAgent
# Load environment variables from the root .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)
from contextlib import asynccontextmanager

from database import init_db, load_conversation_history, save_messages, save_telemetry, save_market_event, load_telemetry
import city_tools
import city_chat_tools
from city_scenario_schema import build_city_scenario_schema


def _parse_cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
    if raw_origins:
        origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
        if origins:
            return origins
    return [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database (creates tables incl. new city ones)
    init_db()
    # Initialize vector memory (ChromaDB)
    vector_memory.init()
    # Connect event bus (Redis or in-process fallback)
    await bus.connect()
    # --- Personal twin simulation ---
    task = asyncio.create_task(engine.run())
    # --- City twin multi-agent setup ---
    ev_scout = EVScoutAgent()
    traffic_scout = TrafficScoutAgent()
    demand_analyzer = DemandAnalyzerAgent()
    congestion_analyzer = CongestionAnalyzerAgent()
    chief = ChiefOracleAgent(
        demand_analyzer=demand_analyzer,
        congestion_analyzer=congestion_analyzer,
    )
    # Register Scout agents as city engine tick subscribers
    city_engine.agent_subscribers.append(ev_scout.on_tick)
    city_engine.agent_subscribers.append(traffic_scout.on_tick)
    city_engine.agent_subscribers.append(chief.on_tick)
    # Start city engine and analyzer background tasks
    city_task = asyncio.create_task(city_engine.run())
    demand_task = asyncio.create_task(demand_analyzer.run())
    congestion_task = asyncio.create_task(congestion_analyzer.run())
    # Expose chief globally so city chat endpoint can use it
    app.state.chief = chief
    yield
    # Shutdown
    engine.running = False
    city_engine.running = False
    task.cancel()
    city_task.cancel()
    demand_task.cancel()
    congestion_task.cancel()
    await bus.close()

app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_parse_cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Secrets Manager client — created once at module level so it is reused across
# requests (Lambda warm starts) without repeated client-construction overhead.
# Only created when OPENAI_API_KEY_SECRET_ARN is present (Lambda production).
_OPENAI_API_KEY_SECRET_ARN = os.getenv("OPENAI_API_KEY_SECRET_ARN")
_sm_client = (
    boto3.client(
        "secretsmanager",
        region_name=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
    )
    if _OPENAI_API_KEY_SECRET_ARN
    else None
)


def _resolve_openai_api_key() -> Optional[str]:
    """Return the OpenAI API key.

    Checks the OPENAI_API_KEY environment variable first (local dev / explicit
    injection).  Falls back to fetching the value from AWS Secrets Manager when
    OPENAI_API_KEY_SECRET_ARN is set (Lambda production), so the raw key is
    never embedded in the Lambda environment or Terraform state.

    Returns:
        Optional[str]: The OpenAI API key if found via env var or Secrets Manager,
            or None if no source is configured or retrieval fails.
    """
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    if _OPENAI_API_KEY_SECRET_ARN and _sm_client is not None:
        try:
            resp = _sm_client.get_secret_value(SecretId=_OPENAI_API_KEY_SECRET_ARN)
            return resp["SecretString"]
        except ClientError as e:
            print(
                f"Warning: Could not retrieve OpenAI key from Secrets Manager: {e}. "
                "Verify that the secret exists, that the Lambda execution role has "
                "secretsmanager:GetSecretValue permission, and that "
                "OPENAI_API_KEY_SECRET_ARN points to the correct secret. "
                "The /chat endpoint will be unavailable until this is resolved."
            )
    return None


# Initialize OpenAI client
try:
    openai_client = OpenAI(api_key=_resolve_openai_api_key())
except Exception as e:
    print(f"Warning: Failed to initialize OpenAI client: {e}")
    openai_client = None


LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "gpt-4o-mini")
ALLOW_CODE_EXECUTION = os.getenv("ALLOW_CODE_EXECUTION", "false").lower() == "true"

# Safety constraints for optimization tools (hard limits)
MIN_ACTIVE_HUBS_FOR_OPTIMIZATION = city_tools.MIN_ACTIVE_HUBS_FOR_OPTIMIZATION
MAX_TOOL_ACTIONS = city_tools.MAX_TOOL_ACTIONS
MAX_PRICE_DELTA_PER_CALL = city_tools.MAX_PRICE_DELTA_PER_CALL
MIN_PRICE_DELTA_PER_CALL = city_tools.MIN_PRICE_DELTA_PER_CALL
MAX_PRICE_SPREAD = city_tools.MAX_PRICE_SPREAD
MIN_SIGNAL_MULTIPLIER = city_tools.MIN_SIGNAL_MULTIPLIER
TOOL_COOLDOWN_SECONDS = city_tools.TOOL_COOLDOWN_SECONDS
MAX_TRAFFIC_REROUTE_PER_CALL = city_tools.MAX_TRAFFIC_REROUTE_PER_CALL
_TOOL_LAST_EXECUTED_AT: dict[str, float] = {}

# Memory storage configuration
USE_S3 = os.getenv("USE_S3", "false").lower() == "true"
S3_BUCKET = os.getenv("S3_BUCKET", "")
MEMORY_DIR = os.getenv("MEMORY_DIR", "../memory")

# Initialize S3 client if needed
if USE_S3:
    s3_client = boto3.client("s3")


# Request/Response models
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str


class ScenarioRunRequest(BaseModel):
    scenario_actions: List[Dict]
    horizon_ticks: int = 30
    runs: int = 3


class Message(BaseModel):
    role: str
    content: str
    timestamp: str


# Memory management functions
def get_memory_path(session_id: str) -> str:
    return f"{session_id}.json"

def load_conversation(session_id: str) -> List[Dict]:
    """Load conversation history from SQLite database"""
    if USE_S3:
        try:
            response = s3_client.get_object(Bucket=S3_BUCKET, Key=get_memory_path(session_id))
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return []
            raise
    else:
        return load_conversation_history(session_id)

def save_conversation(session_id: str, messages: List[Dict]):
    """Save conversation history to SQLite database"""
    if USE_S3:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=get_memory_path(session_id),
            Body=json.dumps(messages, indent=2),
            ContentType="application/json",
        )
    else:
        save_messages(session_id, messages)


def _forecast_city_load(horizon_ticks: int = 30) -> dict:
    return city_tools.forecast_city_load(city_engine, horizon_ticks=horizon_ticks)


def _top_congestion_hotspots(limit: int = 3) -> list[dict]:
    hotspots = sorted(
        city_engine.zone_congestion.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:limit]
    return [{"zone": zone, "congestion": round(level, 3)} for zone, level in hotspots]


def _forecast_recommendations(
    *,
    projected_queue: float,
    active_hubs: int,
    projected_price: float,
    current_price: float,
    weather: str,
) -> list[str]:
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


def _analyze_resident_segments() -> dict:
    return city_tools.analyze_resident_segments(city_engine)


def _evaluate_weather_impact(target_weather: str, horizon_ticks: int = 30) -> dict:
    return city_tools.evaluate_weather_impact(city_engine, target_weather, horizon_ticks=horizon_ticks)


def _check_tool_cooldown(tool_name: str) -> Optional[str]:
    now = time.time()
    last = _TOOL_LAST_EXECUTED_AT.get(tool_name, 0.0)
    wait = TOOL_COOLDOWN_SECONDS - (now - last)
    if wait > 0:
        return f"Tool '{tool_name}' cooling down. Retry in {wait:.1f}s."
    _TOOL_LAST_EXECUTED_AT[tool_name] = now
    return None


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _active_hubs() -> list:
    return [h for h in city_engine.hubs if getattr(h, "active", False)]


def _zone_population(zone_key: str) -> int:
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
        for t in getattr(city_engine, "traffic_agents", [])
        if x_min <= getattr(t, "x", 0.0) < x_max and y_min <= getattr(t, "y", 0.0) < y_max
    )


def optimize_hub_pricing(
    objective: str = "balanced",
    floor: Optional[float] = None,
    ceiling: Optional[float] = None,
    max_delta: float = 0.02,
    fairness_weight: float = 0.5,
) -> dict:
    return city_tools.optimize_hub_pricing(
        city_engine,
        _TOOL_LAST_EXECUTED_AT,
        objective=objective,
        floor=floor,
        ceiling=ceiling,
        max_delta=max_delta,
        fairness_weight=fairness_weight,
    )


def rebalance_hub_load(
    strategy: str = "hybrid",
    max_actions: int = 3,
    zone: Optional[str] = None,
    aggressiveness: float = 0.5,
) -> dict:
    return city_tools.rebalance_hub_load(
        city_engine,
        _TOOL_LAST_EXECUTED_AT,
        strategy=strategy,
        max_actions=max_actions,
        zone=zone,
        aggressiveness=aggressiveness,
    )


def _state_avg_congestion(state: dict) -> float:
    values = list((state.get("zone_congestion") or {}).values())
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _state_metrics(state: dict) -> dict:
    hubs = state.get("hubs", [])
    residents = state.get("residents", [])
    traffic = state.get("traffic", [])
    active_hubs = [h for h in hubs if h.get("active", True)]
    total_queue = float(sum(float(h.get("queue", 0.0)) for h in active_hubs))
    avg_price = (
        float(sum(float(h.get("price", 0.2)) for h in active_hubs) / len(active_hubs))
        if active_hubs
        else 0.0
    )
    seeking_count = sum(1 for r in residents if str(r.get("state", "")) == "seeking")
    charging_count = sum(1 for r in residents if str(r.get("state", "")) == "charging")
    waiting_count = sum(1 for r in residents if str(r.get("state", "")) == "waiting")
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


_SCENARIO_ACTION_ALLOWED_FIELDS: dict[str, set[str]] = {
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


def _normalize_scenario_action(raw: dict, index: int) -> tuple[Optional[dict], Optional[str]]:
    if not isinstance(raw, dict):
        return None, f"scenario_actions[{index}] must be an object"

    action_type = str(raw.get("type", "")).strip().lower()
    if action_type not in _SCENARIO_ACTION_ALLOWED_FIELDS:
        allowed = ", ".join(sorted(_SCENARIO_ACTION_ALLOWED_FIELDS.keys()))
        return None, f"scenario_actions[{index}].type '{action_type}' is unsupported. Allowed: {allowed}"

    allowed_fields = _SCENARIO_ACTION_ALLOWED_FIELDS[action_type]
    normalized = {"type": action_type}

    if action_type == "set_weather":
        weather = str(raw.get("weather", "sunny")).strip().lower()
        if weather not in {"sunny", "storm", "extreme_heat"}:
            return None, f"scenario_actions[{index}].weather must be sunny, storm, or extreme_heat"
        normalized["weather"] = weather
    elif action_type in {"add_city_hub", "add_city_resident", "add_city_traffic"}:
        normalized["count"] = int(_clamp(float(raw.get("count", 1)), 1, 20))
    elif action_type == "set_hub_price":
        hub_id = str(raw.get("hub_id", "")).strip()
        if not hub_id:
            return None, f"scenario_actions[{index}].hub_id is required"
        min_price = getattr(city_engine, "MIN_PRICE", 0.10)
        max_price = getattr(city_engine, "MAX_PRICE", 0.80)
        normalized["hub_id"] = hub_id
        normalized["price"] = _clamp(float(raw.get("price", 0.2)), min_price, max_price)
    elif action_type == "set_hub_active_state":
        hub_id = str(raw.get("hub_id", "")).strip()
        if not hub_id:
            return None, f"scenario_actions[{index}].hub_id is required"
        normalized["hub_id"] = hub_id
        normalized["active"] = _parse_bool(raw.get("active", True), default=True)
    elif action_type == "set_signal_timing":
        zone = str(raw.get("zone", "")).strip()
        if not zone:
            return None, f"scenario_actions[{index}].zone is required"
        normalized["zone"] = zone
        normalized["multiplier"] = _clamp(float(raw.get("multiplier", 1.0)), MIN_SIGNAL_MULTIPLIER, 1.0)
    elif action_type == "reroute_traffic":
        zone = str(raw.get("zone", "")).strip()
        if not zone:
            return None, f"scenario_actions[{index}].zone is required"
        normalized["zone"] = zone
    elif action_type == "optimize_hub_pricing":
        normalized["objective"] = str(raw.get("objective", "balanced"))
        if "floor" in raw:
            normalized["floor"] = float(raw.get("floor"))
        if "ceiling" in raw:
            normalized["ceiling"] = float(raw.get("ceiling"))
        normalized["max_delta"] = float(raw.get("max_delta", 0.02))
        normalized["fairness_weight"] = float(raw.get("fairness_weight", 0.5))
    elif action_type == "rebalance_hub_load":
        normalized["strategy"] = str(raw.get("strategy", "hybrid"))
        normalized["max_actions"] = int(_clamp(float(raw.get("max_actions", 3)), 1, MAX_TOOL_ACTIONS))
        zone = str(raw.get("zone", "")).strip()
        if zone:
            normalized["zone"] = zone
        normalized["aggressiveness"] = _clamp(float(raw.get("aggressiveness", 0.5)), 0.1, 1.0)

    # Drop unknown fields by only copying normalized values
    _ = allowed_fields
    return normalized, None


def _normalize_scenario_actions(actions: list[dict]) -> tuple[list[dict], list[str]]:
    normalized: list[dict] = []
    errors: list[str] = []
    for index, raw in enumerate(actions[:MAX_TOOL_ACTIONS]):
        item, error = _normalize_scenario_action(raw, index)
        if error:
            errors.append(error)
        elif item is not None:
            normalized.append(item)
    return normalized, errors


def _scenario_zone_population(state: dict, zone_key: str) -> int:
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
        for t in state.get("traffic", [])
        if x_min <= float(t.get("x", 0.0)) < x_max and y_min <= float(t.get("y", 0.0)) < y_max
    )


def _scenario_optimize_hub_pricing(
    state: dict,
    objective: str = "balanced",
    floor: Optional[float] = None,
    ceiling: Optional[float] = None,
    max_delta: float = 0.02,
    fairness_weight: float = 0.5,
) -> dict:
    hubs = [h for h in state.get("hubs", []) if h.get("active", True)]
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {
            "status": "skipped",
            "reason": f"need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs",
        }

    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    floor = _clamp(float(floor if floor is not None else min_price), min_price, max_price)
    ceiling = _clamp(float(ceiling if ceiling is not None else max_price), floor, max_price)
    max_delta = _clamp(float(max_delta), MIN_PRICE_DELTA_PER_CALL, MAX_PRICE_DELTA_PER_CALL)
    fairness_weight = _clamp(float(fairness_weight), 0.0, 1.0)
    objective = str(objective or "balanced").strip().lower()

    avg_queue = sum(float(h.get("queue", 0.0)) for h in hubs) / len(hubs)
    avg_price = sum(float(h.get("price", 0.20)) for h in hubs) / len(hubs)
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
        updates.append(
            {
                "hub_id": hub.get("id", "unknown"),
                "old_price": round(price, 3),
                "new_price": round(new_price, 3),
                "delta": round(new_price - price, 3),
            }
        )

    prices = [float(h.get("price", 0.20)) for h in hubs]
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
        "constraints": {
            "floor": round(floor, 3),
            "ceiling": round(ceiling, 3),
            "max_delta": round(max_delta, 3),
            "max_spread": MAX_PRICE_SPREAD,
        },
    }


def _scenario_rebalance_hub_load(
    state: dict,
    strategy: str = "hybrid",
    max_actions: int = 3,
    zone: Optional[str] = None,
    aggressiveness: float = 0.5,
) -> dict:
    hubs = [h for h in state.get("hubs", []) if h.get("active", True)]
    if len(hubs) < MIN_ACTIVE_HUBS_FOR_OPTIMIZATION:
        return {
            "status": "skipped",
            "reason": f"need at least {MIN_ACTIVE_HUBS_FOR_OPTIMIZATION} active hubs",
        }

    strategy = str(strategy or "hybrid").strip().lower()
    if strategy not in {"reroute", "price", "hybrid"}:
        strategy = "hybrid"
    max_actions = int(_clamp(float(max_actions), 1, MAX_TOOL_ACTIONS))
    aggressiveness = _clamp(float(aggressiveness), 0.1, 1.0)

    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    zone_congestion = state.setdefault("zone_congestion", {})
    zone_speed_limits = state.setdefault("zone_speed_limits", {})
    actions = []

    avg_queue = sum(float(h.get("queue", 0.0)) for h in hubs) / len(hubs)
    overloaded = [h for h in hubs if float(h.get("queue", 0.0)) >= max(float(h.get("capacity", 4)), avg_queue + 1)]
    underused = [h for h in hubs if float(h.get("queue", 0.0)) <= max(0.0, avg_queue - 1)]

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
            zone_population = _scenario_zone_population(state, zone_target)
            if zone_population <= MAX_TRAFFIC_REROUTE_PER_CALL:
                if zone_target in zone_congestion:
                    zone_congestion[zone_target] = _clamp(float(zone_congestion[zone_target]) * 0.75, 0.0, 1.0)
                actions.append({"type": "reroute", "zone": zone_target, "rerouted": zone_population})
                if len(actions) < max_actions:
                    throttle = _clamp(1.0 - 0.4 * aggressiveness, MIN_SIGNAL_MULTIPLIER, 1.0)
                    zone_speed_limits[zone_target] = throttle
                    actions.append({"type": "signal_timing", "zone": zone_target, "multiplier": round(throttle, 2)})
            else:
                actions.append(
                    {
                        "type": "reroute_skipped",
                        "zone": zone_target,
                        "reason": f"zone population {zone_population} exceeds safety cap {MAX_TRAFFIC_REROUTE_PER_CALL}",
                    }
                )

    return {
        "status": "success",
        "strategy": strategy,
        "applied_actions": actions[:max_actions],
        "safety": {
            "max_actions": max_actions,
            "max_price_delta": MAX_PRICE_DELTA_PER_CALL,
            "max_reroute_agents": MAX_TRAFFIC_REROUTE_PER_CALL,
        },
    }


def _apply_scenario_actions(state: dict, actions: list[dict]) -> list[dict]:
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
            if weather in {"sunny", "storm", "extreme_heat"}:
                state["weather"] = weather
                applied.append({"type": "set_weather", "weather": weather})
        elif action_type == "add_city_hub":
            count = int(_clamp(float(raw.get("count", 1)), 1, 5))
            base_idx = len(hubs)
            for i in range(count):
                hubs.append(
                    {
                        "id": f"sim_hub_{base_idx + i}",
                        "x": 50.0,
                        "y": 50.0,
                        "price": 0.20,
                        "queue": 0,
                        "queue_total": 0,
                        "waiting": 0,
                        "charging": 0,
                        "slots_used": 0,
                        "capacity": 4,
                        "active": True,
                    }
                )
            applied.append({"type": "add_city_hub", "count": count})
        elif action_type == "add_city_resident":
            count = int(_clamp(float(raw.get("count", 1)), 1, 20))
            base_idx = len(residents)
            for i in range(count):
                residents.append(
                    {
                        "id": f"sim_res_{base_idx + i}",
                        "x": 50.0,
                        "y": 50.0,
                        "battery": 55.0,
                        "charging": False,
                        "state": "driving",
                    }
                )
            applied.append({"type": "add_city_resident", "count": count})
        elif action_type == "add_city_traffic":
            count = int(_clamp(float(raw.get("count", 1)), 1, 20))
            base_idx = len(traffic)
            for i in range(count):
                traffic.append({"id": f"sim_traffic_{base_idx + i}", "x": 50.0, "y": 50.0})
            applied.append({"type": "add_city_traffic", "count": count})
        elif action_type == "set_hub_price":
            hub_id = str(raw.get("hub_id", ""))
            price = _clamp(float(raw.get("price", 0.2)), min_price, max_price)
            hub = next((h for h in hubs if str(h.get("id")) == hub_id), None)
            if hub:
                hub["price"] = price
                applied.append({"type": "set_hub_price", "hub_id": hub_id, "price": round(price, 3)})
        elif action_type == "set_hub_active_state":
            hub_id = str(raw.get("hub_id", ""))
            active = bool(raw.get("active", True))
            hub = next((h for h in hubs if str(h.get("id")) == hub_id), None)
            if hub:
                hub["active"] = active
                applied.append({"type": "set_hub_active_state", "hub_id": hub_id, "active": active})
        elif action_type == "set_signal_timing":
            zone = str(raw.get("zone", ""))
            if zone:
                multiplier = _clamp(float(raw.get("multiplier", 1.0)), MIN_SIGNAL_MULTIPLIER, 1.0)
                zone_speed_limits[zone] = multiplier
                if zone in zone_congestion:
                    zone_congestion[zone] = _clamp(float(zone_congestion[zone]) * multiplier, 0.0, 1.0)
                applied.append({"type": "set_signal_timing", "zone": zone, "multiplier": round(multiplier, 2)})
        elif action_type == "reroute_traffic":
            zone = str(raw.get("zone", ""))
            if zone and zone in zone_congestion:
                zone_congestion[zone] = _clamp(float(zone_congestion[zone]) * 0.75, 0.0, 1.0)
                applied.append({"type": "reroute_traffic", "zone": zone})
        elif action_type == "optimize_hub_pricing":
            outcome = _scenario_optimize_hub_pricing(
                state,
                objective=str(raw.get("objective", "balanced")),
                floor=raw.get("floor"),
                ceiling=raw.get("ceiling"),
                max_delta=float(raw.get("max_delta", 0.02)),
                fairness_weight=float(raw.get("fairness_weight", 0.5)),
            )
            applied.append({"type": "optimize_hub_pricing", "outcome": outcome})
        elif action_type == "rebalance_hub_load":
            outcome = _scenario_rebalance_hub_load(
                state,
                strategy=str(raw.get("strategy", "hybrid")),
                max_actions=int(raw.get("max_actions", 3)),
                zone=raw.get("zone"),
                aggressiveness=float(raw.get("aggressiveness", 0.5)),
            )
            applied.append({"type": "rebalance_hub_load", "outcome": outcome})

    return applied


def _run_projection(state: dict, horizon_ticks: int, runs: int) -> dict:
    min_price = getattr(city_engine, "MIN_PRICE", 0.10)
    max_price = getattr(city_engine, "MAX_PRICE", 0.80)
    outcomes = []

    for _ in range(runs):
        sim = copy.deepcopy(state)
        hubs = sim.get("hubs", [])
        residents = sim.get("residents", [])
        traffic = sim.get("traffic", [])
        weather = str(sim.get("weather", "sunny"))

        weather_multiplier = {"sunny": 1.0, "storm": 1.3, "extreme_heat": 1.45}.get(weather, 1.0)

        for _tick in range(horizon_ticks):
            active_hubs = [h for h in hubs if h.get("active", True)]
            if not active_hubs:
                break
            avg_congestion = _state_avg_congestion(sim)
            seeking = sum(1 for r in residents if str(r.get("state", "")) == "seeking")
            waiting = sum(1 for r in residents if str(r.get("state", "")) == "waiting")
            demand_pressure = (seeking + 0.7 * waiting + 0.02 * len(traffic)) * weather_multiplier
            service_capacity = len(active_hubs) * (0.85 - 0.25 * avg_congestion)
            stochastic = random.uniform(-0.35, 0.35)
            delta_queue = max(-2.0, demand_pressure - service_capacity + stochastic)

            per_hub_delta = delta_queue / max(1, len(active_hubs))
            for hub in active_hubs:
                queue = float(hub.get("queue", 0.0))
                queue = max(0.0, queue + per_hub_delta)
                hub["queue"] = round(queue, 3)
                hub["queue_total"] = round(queue, 3)

                pressure = queue / max(1.0, float(hub.get("capacity", 4)))
                p = float(hub.get("price", 0.2)) + 0.008 * pressure - 0.003 * (1.0 - pressure)
                hub["price"] = _clamp(p, min_price, max_price)

        outcomes.append(_state_metrics(sim))

    avg = {
        "total_queue": round(sum(o["total_queue"] for o in outcomes) / len(outcomes), 3),
        "avg_price": round(sum(o["avg_price"] for o in outcomes) / len(outcomes), 3),
        "avg_congestion": round(sum(o["avg_congestion"] for o in outcomes) / len(outcomes), 3),
        "active_hubs": round(sum(o["active_hubs"] for o in outcomes) / len(outcomes), 3),
    }
    return avg


def simulate_scenario(
    scenario_actions: list[dict],
    horizon_ticks: int = 30,
    runs: int = 3,
) -> dict:
    return city_tools.simulate_scenario(
        city_engine,
        scenario_actions,
        horizon_ticks=horizon_ticks,
        runs=runs,
    )


def call_llm(conversation: List[Dict], user_message: str) -> str:
    """Call LLM API with conversation history and tool calling"""
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client is not initialized")

    messages = []

    sim_state = engine.get_state() if 'engine' in globals() else None
    messages.append({
        "role": "system",
        "content": prompt(sim_state)
    })

    for msg in conversation[-20:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    messages.append({
        "role": "user",
        "content": user_message
    })

    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_resident_agents",
                "description": "Add a specified number of resident EV agents to the city simulation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "The number of resident agents to add. Default is 1."
                        }
                    },
                    "required": ["count"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_charging_hubs",
                "description": "Add a specified number of charging hubs to the city simulation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "The number of charging hubs to add. Default is 1."
                        }
                    },
                    "required": ["count"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "trigger_surge_event",
                "description": "Trigger a traffic or power surge event by instantly dropping the battery of a random subset of residents to a critical level (<20%).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "percentage": {
                            "type": "integer",
                            "description": "Percentage of residents affected (1 to 100). Default is 25."
                        }
                    },
                    "required": ["percentage"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_global_parameters",
                "description": "Update global simulation parameters like charging speed, battery drain rate, and hub-selection weights.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "charging_speed": {
                            "type": "number",
                            "description": "The amount of battery % a hub restores per tick. Default is 5.0."
                        },
                        "battery_drain": {
                            "type": "number",
                            "description": "The amount of battery % a resident drains per tick while driving. Default is 0.2."
                        },
                        "distance_weight": {
                            "type": "number",
                            "description": "Weight applied to distance-squared when residents score hubs. Higher = residents prioritise proximity. Default is 1.0."
                        },
                        "price_weight": {
                            "type": "number",
                            "description": "Weight applied to hub price when residents score hubs. Higher = residents prioritise cheaper hubs. Default is 50.0."
                        }
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_weather",
                "description": "Change the simulation weather, which affects EV battery drain and charging speed. Options: 'sunny' (normal), 'storm' (high drain, slow charge), 'extreme_heat' (max drain).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "condition": {
                            "type": "string",
                            "enum": ["sunny", "storm", "extreme_heat"],
                            "description": "The weather condition to apply."
                        }
                    },
                    "required": ["condition"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "trigger_maintenance",
                "description": "Simulate a hardware failure or maintenance event by randomly disabling one active charging hub.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_hub_price",
                "description": "Manually set the electricity price for a specific charging hub.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hub_id": {
                            "type": "string",
                            "description": "The ID of the hub, e.g., 'hub_0'"
                        },
                        "price": {
                            "type": "number",
                            "description": "The new price per kWh"
                        }
                    },
                    "required": ["hub_id", "price"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Execute a python snippet to perform custom calculations based on simulation data. The 'engine' variable is available in the local scope.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "The python code to execute. Print the final result so it can be captured in stdout."
                        }
                    },
                    "required": ["code"]
                }
            }
        }
    ]

    try:
        response = openai_client.chat.completions.create(
            model=LLM_MODEL_ID,
            messages=messages,
            tools=tools,
            temperature=0.7,
            max_tokens=2000,
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            messages.append(response_message)

            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except Exception:
                    function_args = {}

                if function_name == "add_resident_agents":
                    count = function_args.get("count", 1)
                    from simulation import ResidentAgent
                    for _ in range(count):
                        new_res = ResidentAgent(f"res_{len(engine.residents)}")
                        engine.residents.append(new_res)
                    result_body = {"status": "success", "message": f"Added {count} residents."}
                    print(f"Oracle executed tool: Added {count} residents.")
                elif function_name == "add_charging_hubs":
                    count = function_args.get("count", 1)
                    from simulation import ChargingHubAgent
                    for _ in range(count):
                        new_hub = ChargingHubAgent(f"hub_{len(engine.hubs)}")
                        engine.hubs.append(new_hub)
                    result_body = {"status": "success", "message": f"Added {count} hubs."}
                    print(f"Oracle executed tool: Added {count} hubs.")
                elif function_name == "trigger_surge_event":
                    percentage = function_args.get("percentage", 25)
                    affected_count = max(1, int(len(engine.residents) * (percentage / 100)))
                    affected_agents = random.sample(engine.residents, min(affected_count, len(engine.residents)))
                    for res in affected_agents:
                        res.battery = random.uniform(5, 20)
                    result_body = {"status": "success", "message": f"Triggered surge event affecting {len(affected_agents)} residents."}
                    print(f"Oracle executed tool: Triggered surge event ({percentage}%).")
                elif function_name == "set_global_parameters":
                    if "charging_speed" in function_args:
                        engine.global_charging_speed = float(function_args["charging_speed"])
                    if "battery_drain" in function_args:
                        engine.global_battery_drain = float(function_args["battery_drain"])
                    if "distance_weight" in function_args:
                        engine.distance_weight = float(function_args["distance_weight"])
                    if "price_weight" in function_args:
                        engine.price_weight = float(function_args["price_weight"])
                    result_body = {"status": "success", "message": f"Updated parameters: charging_speed={engine.global_charging_speed}, battery_drain={engine.global_battery_drain}, distance_weight={engine.distance_weight}, price_weight={engine.price_weight}"}
                    print("Oracle executed tool: Set global parameters.")
                elif function_name == "set_weather":
                    condition = function_args.get("condition", "sunny")
                    engine.weather = condition
                    if condition == "sunny":
                        engine.global_battery_drain = 0.2
                        engine.global_charging_speed = 5.0
                    elif condition == "storm":
                        engine.global_battery_drain = 0.5
                        engine.global_charging_speed = 2.0
                    elif condition == "extreme_heat":
                        engine.global_battery_drain = 0.8
                        engine.global_charging_speed = 4.0
                    result_body = {"status": "success", "message": f"Weather set to {condition}. Parameters updated accordingly."}
                    print(f"Oracle executed tool: Set weather to {condition}.")
                elif function_name == "trigger_maintenance":
                    active_hubs = [hub for hub in engine.hubs if hub.active]
                    if active_hubs:
                        hub_to_disable = random.choice(active_hubs)
                        hub_to_disable.active = False
                        result_body = {"status": "success", "message": f"Disabled hub {hub_to_disable.id} for maintenance."}
                    else:
                        result_body = {"status": "error", "message": "No active hubs to disable."}
                    print("Oracle executed tool: Triggered maintenance.")
                elif function_name == "set_hub_price":
                    hub_id = function_args.get("hub_id")
                    price = function_args.get("price")
                    hub = next((hub for hub in engine.hubs if hub.id == hub_id), None)
                    if hub:
                        hub.price = float(price)
                        result_body = {"status": "success", "message": f"Set {hub_id} price to {price}."}
                    else:
                        result_body = {"status": "error", "message": f"Hub {hub_id} not found."}
                    print("Oracle executed tool: Set hub price.")
                elif function_name == "execute_python":
                    if not ALLOW_CODE_EXECUTION:
                        result_body = {
                            "status": "disabled",
                            "message": "Python code execution is disabled on this server. Set ALLOW_CODE_EXECUTION=true to enable it."
                        }
                        print("Oracle execute_python skipped: ALLOW_CODE_EXECUTION is disabled.")
                    else:
                        code = function_args.get("code", "")
                        import io
                        import sqlite3
                        old_stdout = sys.stdout
                        redirected_output = sys.stdout = io.StringIO()
                        try:
                            db_path = os.path.join(os.path.dirname(__file__), 'data', 'simulation.db')
                            local_vars = {
                                "engine": engine,
                                "sqlite3": sqlite3,
                                "os": os,
                                "DB_PATH": db_path,
                            }
                            exec(code, {}, local_vars)
                            output = redirected_output.getvalue()
                            result_body = {"status": "success", "output": output}
                        except Exception as e:
                            result_body = {"status": "error", "message": str(e)}
                        finally:
                            sys.stdout = old_stdout
                        print("Oracle executed python code.")
                else:
                    result_body = {"status": "error", "message": "Unknown tool."}

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(result_body),
                })

            second_response = openai_client.chat.completions.create(
                model=LLM_MODEL_ID,
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            return second_response.choices[0].message.content or ""

        return response_message.content or ""

    except Exception as e:
        print(f"LLM error: {e}")
        raise HTTPException(status_code=500, detail=f"LLM error: {str(e)}")


@app.get("/")
async def root():
    return {
        "message": "AI Digital Twin API (Powered by OpenAI)",
        "memory_enabled": True,
        "storage": "S3" if USE_S3 else "local",
        "ai_model": LLM_MODEL_ID
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "use_s3": USE_S3,
        "bedrock_model": LLM_MODEL_ID
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Generate session ID if not provided
        session_id = request.session_id or str(uuid.uuid4())

        # Load conversation history
        conversation = load_conversation(session_id)

        # Call LLM for response
        assistant_response = call_llm(conversation, request.message)

        # Update conversation history
        conversation.append(
            {"role": "user", "content": request.message, "timestamp": datetime.now().isoformat()}
        )
        conversation.append(
            {
                "role": "assistant",
                "content": assistant_response,
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Save conversation
        save_conversation(session_id, conversation)

        return ChatResponse(response=assistant_response, session_id=session_id)

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """Retrieve conversation history"""
    try:
        conversation = load_conversation(session_id)
        return {"session_id": session_id, "messages": conversation}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/telemetry")
async def get_telemetry(limit: int = Query(default=50, ge=1, le=200)):
    """Return historical telemetry and market events for sparkline charts."""
    try:
        return load_telemetry(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Removed legacy startup event in favor of lifespan context manager

@app.websocket("/ws/simulation")
async def simulation_websocket(websocket: WebSocket):
    await websocket.accept()
    
    async def send_state(state):
        try:
            await websocket.send_json(state)
        except Exception:
            pass

    engine.subscribers.append(send_state)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle real-time commands from the frontend
            if data == "add_hub":
                from simulation import ChargingHubAgent
                new_hub = ChargingHubAgent(f"hub_{len(engine.hubs)}")
                engine.hubs.append(new_hub)
                print(f"Added new hub: {new_hub.id}")
            elif data == "add_resident":
                from simulation import ResidentAgent
                new_res = ResidentAgent(f"res_{len(engine.residents)}")
                engine.residents.append(new_res)
    except WebSocketDisconnect:
        if send_state in engine.subscribers:
            engine.subscribers.remove(send_state)


# ---------------------------------------------------------------------------
# City Digital Twin endpoints
# ---------------------------------------------------------------------------

@app.post("/city/chat", response_model=ChatResponse)
async def city_chat(request: ChatRequest):
    """City Oracle chat — separate conversation history from personal twin."""
    try:
        session_id = request.session_id or str(uuid.uuid4())
        conversation = load_conversation(f"city_{session_id}")
        if not openai_client:
            raise HTTPException(status_code=500, detail="OpenAI client is not initialized")
        # Build city-aware messages
        sim_state = city_engine.get_state()
        system_msg = city_prompt(sim_state)
        messages = [{"role": "system", "content": system_msg}]
        for msg in conversation[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": request.message})
        city_tools = city_chat_tools.build_city_chat_tools()

        response = openai_client.chat.completions.create(
            model=LLM_MODEL_ID,
            messages=messages,
            tools=city_tools,
            max_tokens=1024,
        )

        response_message = response.choices[0].message
        tool_calls = response_message.tool_calls

        if tool_calls:
            messages.append(response_message)

            for tool_call in tool_calls:
                function_name = getattr(getattr(tool_call, "function", None), "name", "")
                try:
                    function_args = json.loads(getattr(tool_call.function, "arguments", "{}"))
                except Exception:
                    function_args = {}

                result_body = city_chat_tools.execute_city_tool_call(
                    function_name=function_name,
                    function_args=function_args,
                    city_engine=city_engine,
                    helpers={
                        "forecast_city_load": _forecast_city_load,
                        "analyze_resident_segments": _analyze_resident_segments,
                        "evaluate_weather_impact": _evaluate_weather_impact,
                        "rebalance_hub_load": rebalance_hub_load,
                        "optimize_hub_pricing": optimize_hub_pricing,
                        "simulate_scenario": simulate_scenario,
                    },
                    runner_path=str(pathlib.Path(__file__).parent / "agents" / "code_runner.py"),
                    python_executable=sys.executable,
                )

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(result_body),
                })

            follow_up = openai_client.chat.completions.create(
                model=LLM_MODEL_ID,
                messages=messages,
                max_tokens=1024,
            )
            assistant_message = follow_up.choices[0].message.content
        else:
            assistant_message = response_message.content

        assistant_message = assistant_message or "I could not generate a response."
        timestamp = datetime.now().isoformat()
        conversation.append({"role": "user", "content": request.message, "timestamp": timestamp})
        conversation.append({"role": "assistant", "content": assistant_message, "timestamp": timestamp})
        save_conversation(f"city_{session_id}", conversation)
        return ChatResponse(response=assistant_message, session_id=session_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/city/decisions")
async def city_decisions(limit: int = Query(default=10, ge=1, le=50)):
    """Return the most recent Chief Oracle actuation decisions."""
    try:
        from database import load_recent_decisions
        raw = load_recent_decisions(limit=limit * 3)
        seen: set[tuple[str, str]] = set()
        deduped_latest_first = []
        for item in reversed(raw):
            key = (item.get("type", ""), item.get("description", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped_latest_first.append(item)
            if len(deduped_latest_first) >= limit:
                break
        return {"decisions": list(reversed(deduped_latest_first))}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/city/decisions")
async def city_decisions_clear():
    """Clear all stored Chief Oracle decisions for a clean slate."""
    try:
        from database import clear_agent_decisions
        deleted = clear_agent_decisions()
        return {"deleted": deleted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/city/memory")
async def city_memory_query(q: str = Query(default="charging demand", min_length=1, max_length=200)):
    """Semantic search against the city twin vector memory."""
    try:
        results = vector_memory.query(q, n_results=5)
        return {"query": q, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/city/agents/flow")
async def city_agents_flow():
    """Describe city multi-agent roles and the executable tools available to City Oracle chat."""
    return {
        "tiers": [
            {
                "tier": "Scout",
                "agents": [
                    {
                        "name": "EVScoutAgent",
                        "tasks": [
                            "Monitor hub saturation",
                            "Detect price spikes",
                            "Detect demand bursts",
                        ],
                        "outputs": ["CHANNEL_SCOUT_EV"],
                    },
                    {
                        "name": "TrafficScoutAgent",
                        "tasks": ["Monitor zone congestion", "Detect persistent hotspots"],
                        "outputs": ["CHANNEL_SCOUT_TRAFFIC"],
                    },
                ],
            },
            {
                "tier": "Analyzer",
                "agents": [
                    {
                        "name": "DemandAnalyzerAgent",
                        "tasks": [
                            "Aggregate EV scout events in rolling window",
                            "Emit saturation and demand-burst findings",
                            "Store findings in vector memory",
                        ],
                        "inputs": ["CHANNEL_SCOUT_EV"],
                    },
                    {
                        "name": "CongestionAnalyzerAgent",
                        "tasks": [
                            "Aggregate traffic hotspot events",
                            "Emit persistent hotspot findings",
                            "Store findings in vector memory",
                        ],
                        "inputs": ["CHANNEL_SCOUT_TRAFFIC"],
                    },
                ],
            },
            {
                "tier": "Chief",
                "agents": [
                    {
                        "name": "ChiefOracleAgent",
                        "tasks": [
                            "Synthesize analyzer findings every 30 ticks",
                            "Write decisions to agent_decisions",
                            "Avoid duplicate decisions with cooldown",
                        ],
                    }
                ],
            },
        ],
        "city_oracle_chat_tools": [
            "set_hub_active_state",
            "trigger_hub_maintenance",
            "set_hub_price",
            "add_city_resident",
            "add_city_hub",
            "add_city_traffic",
            "reroute_traffic",
            "set_signal_timing",
            "run_python",
            "forecast_city_load",
            "analyze_resident_segments",
            "evaluate_weather_impact",
            "rebalance_hub_load",
            "optimize_hub_pricing",
            "simulate_scenario",
        ],
        "notes": [
            "City Oracle now has executable control tools in /city/chat.",
            "set_hub_active_state supports ACTIVE/NON_ACTIVE transitions per hub id.",
            "reroute_traffic forces agents in a congested zone to pick new destinations.",
            "set_signal_timing applies a per-zone speed multiplier (0.1=heavy throttle, 1.0=clear).",
            "run_python executes Oracle-authored Python in a sandboxed subprocess with live state+metrics injected.",
            "simulate_scenario runs on copied state only and never mutates the live city engine.",
        ],
    }


@app.get("/city/scenario/schema")
async def city_scenario_schema():
    """Return the supported scenario action catalog used by simulate_scenario."""
    return {
        "endpoint": "/city/scenario/schema",
        "purpose": "Catalog of supported scenario action shapes for safe what-if simulation payloads.",
        "simulate_scenario": {
            "horizon_ticks": {"type": "integer", "min": 5, "max": 120, "default": 30},
            "runs": {"type": "integer", "min": 1, "max": 10, "default": 3},
            "max_actions": MAX_TOOL_ACTIONS,
            "supported_action_types": list(sorted(_SCENARIO_ACTION_ALLOWED_FIELDS.keys())),
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
                "constraints": {"price": {"min": getattr(city_engine, 'MIN_PRICE', 0.10), "max": getattr(city_engine, 'MAX_PRICE', 0.80)}},
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
                "constraints": {"multiplier": {"min": MIN_SIGNAL_MULTIPLIER, "max": 1.0, "default": 1.0}},
                "example": {"type": "set_signal_timing", "zone": "1,2", "multiplier": 0.6},
            },
            "optimize_hub_pricing": {
                "required": ["type"],
                "optional": ["objective", "floor", "ceiling", "max_delta", "fairness_weight"],
                "constraints": {
                    "objective": ["balanced", "queue_reduction", "max_throughput", "fairness"],
                    "max_delta": {"min": MIN_PRICE_DELTA_PER_CALL, "max": MAX_PRICE_DELTA_PER_CALL, "default": 0.02},
                    "fairness_weight": {"min": 0.0, "max": 1.0, "default": 0.5},
                },
                "example": {"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03},
            },
            "rebalance_hub_load": {
                "required": ["type"],
                "optional": ["strategy", "max_actions", "zone", "aggressiveness"],
                "constraints": {
                    "strategy": ["price", "reroute", "hybrid"],
                    "max_actions": {"min": 1, "max": MAX_TOOL_ACTIONS, "default": 3},
                    "aggressiveness": {"min": 0.1, "max": 1.0, "default": 0.5},
                },
                "example": {"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7},
            },
        },
        "payload_example": {
            "scenario_actions": [
                {"type": "set_weather", "weather": "storm"},
                {"type": "optimize_hub_pricing", "objective": "queue_reduction", "max_delta": 0.03},
                {"type": "rebalance_hub_load", "strategy": "hybrid", "max_actions": 3, "aggressiveness": 0.7},
            ],
            "horizon_ticks": 30,
            "runs": 3,
        },
    }


@app.post("/city/scenario/run")
async def city_scenario_run(request: ScenarioRunRequest):
    """Execute a copy-only scenario projection without routing through City Oracle chat."""
    return simulate_scenario(
        scenario_actions=request.scenario_actions,
        horizon_ticks=request.horizon_ticks,
        runs=request.runs,
    )


@app.websocket("/ws/city")
async def city_websocket(websocket: WebSocket):
    """Streams city simulation state including traffic agents and zone congestion."""
    await websocket.accept()

    async def send_city_state(state):
        try:
            await websocket.send_json(state)
        except Exception:
            pass

    city_engine.subscribers.append(send_city_state)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "add_hub":
                from simulation import ChargingHubAgent
                new_hub = ChargingHubAgent(f"hub_{len(city_engine.hubs)}")
                city_engine.hubs.append(new_hub)
            elif data == "add_resident":
                from simulation import ResidentAgent
                new_res = ResidentAgent(f"res_{len(city_engine.residents)}")
                city_engine.residents.append(new_res)
            elif data == "add_traffic":
                from city_simulation import TrafficFlowAgent
                new_t = TrafficFlowAgent(f"traffic_{len(city_engine.traffic_agents)}")
                city_engine.traffic_agents.append(new_t)
    except WebSocketDisconnect:
        if send_city_state in city_engine.subscribers:
            city_engine.subscribers.remove(send_city_state)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)