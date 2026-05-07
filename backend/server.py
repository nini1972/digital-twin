from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import sys
import subprocess
import pathlib
from dotenv import load_dotenv
from typing import Optional, List, Dict
import json
import uuid
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
    allow_origins=["*"],
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


def call_llm(conversation: List[Dict], user_message: str) -> str:
    """Call LLM API with conversation history and tool calling"""
    if not openai_client:
        raise HTTPException(status_code=500, detail="OpenAI client is not initialized")
    
    # Build messages in OpenAI format
    messages = []
    
    # Add system prompt
    sim_state = engine.get_state() if 'engine' in globals() else None
    messages.append({
        "role": "system", 
        "content": prompt(sim_state)
    })
    
    # Add conversation history
    for msg in conversation[-20:]:  # Last 20 messages
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })
    
    # Add current user message
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
        
        # Check if the model wants to call functions
        tool_calls = response_message.tool_calls
        
        if tool_calls:
            # We must append the assistant's message with tool_calls
            messages.append(response_message)
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments)
                except:
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
                    import random
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
                    print(f"Oracle executed tool: Set global parameters.")
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
                    import random
                    active_hubs = [h for h in engine.hubs if h.active]
                    if active_hubs:
                        hub_to_disable = random.choice(active_hubs)
                        hub_to_disable.active = False
                        result_body = {"status": "success", "message": f"Disabled hub {hub_to_disable.id} for maintenance."}
                    else:
                        result_body = {"status": "error", "message": "No active hubs to disable."}
                    print(f"Oracle executed tool: Triggered maintenance.")
                elif function_name == "set_hub_price":
                    hub_id = function_args.get("hub_id")
                    price = function_args.get("price")
                    hub = next((h for h in engine.hubs if h.id == hub_id), None)
                    if hub:
                        hub.price = float(price)
                        result_body = {"status": "success", "message": f"Set {hub_id} price to {price}."}
                    else:
                        result_body = {"status": "error", "message": f"Hub {hub_id} not found."}
                    print(f"Oracle executed tool: Set hub price.")
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
                        import sys
                        import sqlite3
                        old_stdout = sys.stdout
                        redirected_output = sys.stdout = io.StringIO()
                        try:
                            db_path = os.path.join(os.path.dirname(__file__), 'data', 'simulation.db')
                            local_vars = {
                                "engine": engine,
                                "sqlite3": sqlite3,
                                "os": os,
                                "DB_PATH": db_path
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
            
            # Second call to OpenAI with tool results
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
        city_tools = [
            {
                "type": "function",
                "function": {
                    "name": "set_hub_active_state",
                    "description": "Set a city charging hub active or non-active state by hub id.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hub_id": {"type": "string", "description": "Hub id, e.g. hub_0"},
                            "active": {"type": "boolean", "description": "true=active, false=non-active"},
                        },
                        "required": ["hub_id", "active"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "trigger_hub_maintenance",
                    "description": "Randomly disable one active city hub to simulate breakdown/maintenance.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_hub_price",
                    "description": "Set city hub price manually.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hub_id": {"type": "string"},
                            "price": {"type": "number"},
                        },
                        "required": ["hub_id", "price"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_city_resident",
                    "description": "Add one EV resident to city simulation.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_city_hub",
                    "description": "Add one charging hub to city simulation.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "add_city_traffic",
                    "description": "Add one traffic agent to city simulation.",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reroute_traffic",
                    "description": "Reroute all traffic agents currently in a congested zone to new destinations outside that zone, immediately reducing congestion there.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "zone": {"type": "string", "description": "Zone key in 'zx,zy' format, e.g. '0,2' or '3,1'."},
                        },
                        "required": ["zone"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "set_signal_timing",
                    "description": "Adjust smart traffic signal timing in a zone by setting a speed multiplier. Lower multiplier throttles traffic flow (simulates red-light phases). 1.0 = normal, 0.3 = heavy throttle. Use to prevent new vehicles from flooding a congested zone.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "zone": {"type": "string", "description": "Zone key in 'zx,zy' format, e.g. '0,2'."},
                            "multiplier": {"type": "number", "description": "Speed multiplier 0.1..1.0. 1.0 clears the restriction."},
                        },
                        "required": ["zone", "multiplier"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_python",
                    "description": (
                        "Execute a Python code snippet to analyse the current live city simulation data. "
                        "Two variables are pre-injected: "
                        "`state` (dict) – full simulation snapshot with keys: residents (list of {id,x,y,state,battery,charging,current_hub}), "
                        "hubs (list of {id,x,y,active,price,capacity,queue,charging_slots}), "
                        "traffic (list of {id,x,y}), zone_congestion (dict), zone_speed_limits (dict), weather (str); "
                        "`metrics` (dict) – aggregated city metrics with keys: residents, traffic_agents, active_hubs, total_queue, avg_price, "
                        "charging_count, seeking_count, avg_congestion, congestion_hotspot, weather. "
                        "Use print() to output results. Allowed imports: json, math, statistics, collections, itertools, datetime. "
                        "Max code length: 4000 chars. Execution timeout: 5 seconds."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {"type": "string", "description": "Python code to execute. Use print() to return analysis results."},
                        },
                        "required": ["code"],
                    },
                },
            },
        ]

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

                result_body = {"status": "error", "message": "Unknown city tool."}

                if function_name == "set_hub_active_state":
                    from simulation import ResidentState

                    hub_id = function_args.get("hub_id")
                    active = bool(function_args.get("active", True))
                    hub = next((h for h in city_engine.hubs if h.id == hub_id), None)
                    if not hub:
                        result_body = {"status": "error", "message": f"Hub {hub_id} not found."}
                    else:
                        hub.active = active
                        impacted = 0
                        if not active:
                            # Stop charging/waiting immediately when hub is disabled.
                            for res in city_engine.residents:
                                if getattr(res, "current_hub", None) is hub:
                                    if getattr(res, "state", None) in (ResidentState.WAITING, ResidentState.CHARGING):
                                        impacted += 1
                                        hub.release(res.id)
                                        res.current_hub = None
                                        res.state = ResidentState.SEEKING
                            hub.waiting_queue.clear()
                            hub.charging_slots.clear()
                        result_body = {
                            "status": "success",
                            "message": f"Hub {hub.id} set to {'ACTIVE' if active else 'NON_ACTIVE'}.",
                            "impacted_residents": impacted,
                        }
                elif function_name == "trigger_hub_maintenance":
                    import random

                    active_hubs = [h for h in city_engine.hubs if h.active]
                    if not active_hubs:
                        result_body = {"status": "error", "message": "No active hubs available for maintenance."}
                    else:
                        selected = random.choice(active_hubs)
                        selected.active = False
                        selected.waiting_queue.clear()
                        selected.charging_slots.clear()
                        result_body = {
                            "status": "success",
                            "message": f"Maintenance triggered: {selected.id} set to NON_ACTIVE.",
                        }
                elif function_name == "set_hub_price":
                    hub_id = function_args.get("hub_id")
                    price = function_args.get("price")
                    hub = next((h for h in city_engine.hubs if h.id == hub_id), None)
                    if not hub:
                        result_body = {"status": "error", "message": f"Hub {hub_id} not found."}
                    else:
                        hub.price = float(price)
                        result_body = {"status": "success", "message": f"Set {hub.id} price to {hub.price:.3f}."}
                elif function_name == "add_city_resident":
                    from simulation import ResidentAgent

                    new_res = ResidentAgent(f"res_{len(city_engine.residents)}")
                    city_engine.residents.append(new_res)
                    result_body = {"status": "success", "message": f"Added resident {new_res.id}."}
                elif function_name == "add_city_hub":
                    from simulation import ChargingHubAgent

                    new_hub = ChargingHubAgent(f"hub_{len(city_engine.hubs)}")
                    city_engine.hubs.append(new_hub)
                    result_body = {"status": "success", "message": f"Added hub {new_hub.id}."}
                elif function_name == "add_city_traffic":
                    from city_simulation import TrafficFlowAgent

                    new_t = TrafficFlowAgent(f"traffic_{len(city_engine.traffic_agents)}")
                    city_engine.traffic_agents.append(new_t)
                    result_body = {"status": "success", "message": f"Added traffic agent {new_t.id}."}
                elif function_name == "reroute_traffic":
                    zone = function_args.get("zone", "")
                    if not zone:
                        result_body = {"status": "error", "message": "zone parameter required."}
                    else:
                        count = city_engine.reroute_traffic_from_zone(zone)
                        result_body = {
                            "status": "success",
                            "message": f"Rerouted {count} traffic agent(s) out of zone {zone}.",
                            "rerouted": count,
                        }
                elif function_name == "set_signal_timing":
                    zone = function_args.get("zone", "")
                    multiplier = float(function_args.get("multiplier", 1.0))
                    if not zone:
                        result_body = {"status": "error", "message": "zone parameter required."}
                    else:
                        city_engine.set_zone_speed_limit(zone, multiplier)
                        action = "cleared" if multiplier >= 1.0 else f"set to {multiplier:.1f}x"
                        result_body = {
                            "status": "success",
                            "message": f"Signal timing for zone {zone} {action}.",
                        }

                elif function_name == "run_python":
                    code = function_args.get("code", "")
                    if not code:
                        result_body = {"status": "error", "message": "code parameter required."}
                    elif len(code) > 4000:
                        result_body = {"status": "error", "message": "Code exceeds 4000 character limit."}
                    else:
                        try:
                            runner_path = str(pathlib.Path(__file__).parent / "agents" / "code_runner.py")
                            sim_state = city_engine.get_state()
                            sim_metrics = city_engine.get_city_metrics()
                            proc = subprocess.run(
                                [sys.executable, runner_path],
                                input=json.dumps({"code": code, "state": sim_state, "metrics": sim_metrics}),
                                capture_output=True,
                                text=True,
                                timeout=5,
                            )
                            runner_result = json.loads(proc.stdout) if proc.stdout.strip() else {"output": "", "error": "No output from runner."}
                            if runner_result.get("error"):
                                result_body = {"status": "error", "message": runner_result["error"], "output": runner_result.get("output", "")}
                            else:
                                result_body = {"status": "success", "output": runner_result.get("output", "")}
                        except subprocess.TimeoutExpired:
                            result_body = {"status": "error", "message": "Code execution timed out after 5 seconds."}
                        except Exception as exc:
                            result_body = {"status": "error", "message": f"Runner error: {exc}"}

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
        ],
        "notes": [
            "City Oracle now has executable control tools in /city/chat.",
            "set_hub_active_state supports ACTIVE/NON_ACTIVE transitions per hub id.",
            "reroute_traffic forces agents in a congested zone to pick new destinations.",
            "set_signal_timing applies a per-zone speed multiplier (0.1=heavy throttle, 1.0=clear).",
            "run_python executes Oracle-authored Python in a sandboxed subprocess with live state+metrics injected.",
        ],
    }


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