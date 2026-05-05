from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
import asyncio
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
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
# Load environment variables from the root .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path)
from contextlib import asynccontextmanager

from database import init_db, load_conversation_history, save_messages, save_telemetry, save_market_event, load_telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize SQLite database
    init_db()
    # Start the background simulation loop
    task = asyncio.create_task(engine.run())
    yield
    # Shutdown
    engine.running = False
    task.cancel()

app = FastAPI(lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize OpenAI client
try:
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
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
                    print(f"Oracle executed python code.")
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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)