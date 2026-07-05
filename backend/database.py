import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'simulation.db')

def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    # Conversations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    # Simulation telemetry history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            weather TEXT,
            active_hubs INTEGER,
            avg_price REAL,
            total_queue INTEGER
        )
    ''')
    # Market events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS market_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            description TEXT
        )
    ''')
    # Predictions table — meta-cognition: Oracle logs predictions, resolved later
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            metric TEXT NOT NULL,
            prediction_text TEXT NOT NULL,
            predicted_value REAL,
            target_tick INTEGER,
            actual_value REAL,
            error_delta REAL,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
    ''')
    # Agent decisions table — Chief Oracle logs actuation decisions
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_name TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            description TEXT NOT NULL,
            confidence REAL DEFAULT 1.0,
            tick INTEGER,
            created_at TEXT NOT NULL
        )
    ''')
    # Resident personas table — dynamic citizen simulation profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resident_personas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            age INTEGER,
            occupation TEXT,
            income_tier TEXT,
            bio TEXT,
            vehicle_type TEXT,
            traits_json TEXT
        )
    ''')
    # Resident thoughts table — logging dynamic citizen thoughts & sentiment
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS resident_thoughts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resident_id TEXT NOT NULL,
            tick INTEGER,
            decision_type TEXT,
            thought TEXT,
            sentiment TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    # Prune existing database tables on startup to resolve current bloat
    prune_old_data()


def save_message(session_id: str, role: str, content: str, timestamp: str = None):
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO conversations (session_id, role, content, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (session_id, role, content, timestamp))
    conn.commit()
    conn.close()

def save_messages(session_id: str, messages: list):
    """Save an entire list of messages, mostly for backward compatibility or batch inserts."""
    conn = get_connection()
    cursor = conn.cursor()
    # clear old messages for this session to avoid duplicates if we save the entire history
    cursor.execute('DELETE FROM conversations WHERE session_id = ?', (session_id,))
    
    for msg in messages:
        timestamp = msg.get("timestamp", datetime.now().isoformat())
        cursor.execute('''
            INSERT INTO conversations (session_id, role, content, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (session_id, msg["role"], msg["content"], timestamp))
    conn.commit()
    conn.close()

def load_conversation_history(session_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content, timestamp 
        FROM conversations 
        WHERE session_id = ? 
        ORDER BY id ASC
    ''', (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]

def save_telemetry(weather: str, active_hubs: int, avg_price: float, total_queue: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO telemetry (timestamp, weather, active_hubs, avg_price, total_queue)
        VALUES (?, ?, ?, ?, ?)
    ''', (datetime.now().isoformat(), weather, active_hubs, avg_price, total_queue))
    conn.commit()
    conn.close()

def save_market_event(event_type: str, description: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO market_events (timestamp, event_type, description)
        VALUES (?, ?, ?)
    ''', (datetime.now().isoformat(), event_type, description))
    conn.commit()
    conn.close()

def load_telemetry(limit: int = 50) -> dict:
    """Return the last `limit` telemetry rows and recent market events."""
    limit = max(1, min(limit, 200))  # clamp to safe range as defense-in-depth
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT timestamp, weather, active_hubs, avg_price, total_queue
        FROM telemetry
        ORDER BY id DESC
        LIMIT ?
    ''', (limit,))
    rows = cursor.fetchall()
    telemetry = [
        {
            "timestamp": row["timestamp"],
            "weather": row["weather"],
            "active_hubs": row["active_hubs"],
            "avg_price": row["avg_price"],
            "total_queue": row["total_queue"],
        }
        for row in reversed(rows)
    ]

    cursor.execute('''
        SELECT timestamp, event_type, description
        FROM market_events
        ORDER BY id DESC
        LIMIT ?
    ''', (min(limit, 20),))
    event_rows = cursor.fetchall()
    events = [
        {
            "timestamp": row["timestamp"],
            "event_type": row["event_type"],
            "description": row["description"],
        }
        for row in reversed(event_rows)
    ]

    conn.close()
    return {"telemetry": telemetry, "events": events}


# ---------------------------------------------------------------------------
# Predictions (meta-cognition)
# ---------------------------------------------------------------------------

def save_prediction(
    metric: str,
    prediction_text: str,
    predicted_value: float,
    target_tick: int,
    session_id: str = None,
) -> int:
    """Log a new Oracle prediction; return its row id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO predictions (session_id, metric, prediction_text, predicted_value, target_tick, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (session_id, metric, prediction_text, predicted_value, target_tick, datetime.now().isoformat()),
    )
    row_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return row_id


def resolve_prediction(prediction_id: int, actual_value: float):
    """Record the actual outcome and compute error delta for a prediction."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT predicted_value FROM predictions WHERE id = ?', (prediction_id,)
    )
    row = cursor.fetchone()
    if row:
        error_delta = actual_value - row["predicted_value"]
        cursor.execute(
            '''
            UPDATE predictions
            SET actual_value = ?, error_delta = ?, resolved_at = ?
            WHERE id = ?
            ''',
            (actual_value, error_delta, datetime.now().isoformat(), prediction_id),
        )
        conn.commit()
    conn.close()


def load_prediction_accuracy(limit: int = 20) -> dict:
    """Return recent resolved predictions and a mean absolute error summary."""
    limit = max(1, min(limit, 100))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT metric, prediction_text, predicted_value, actual_value, error_delta, resolved_at
        FROM predictions
        WHERE resolved_at IS NOT NULL
        ORDER BY id DESC
        LIMIT ?
        ''',
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    resolved = [
        {
            "metric": r["metric"],
            "prediction_text": r["prediction_text"],
            "predicted_value": r["predicted_value"],
            "actual_value": r["actual_value"],
            "error_delta": r["error_delta"],
            "resolved_at": r["resolved_at"],
        }
        for r in rows
    ]
    if resolved:
        mae = sum(abs(r["error_delta"]) for r in resolved) / len(resolved)
    else:
        mae = None
    return {"resolved_predictions": resolved, "mean_absolute_error": mae}


# ---------------------------------------------------------------------------
# Agent decisions (Chief Oracle actuation log)
# ---------------------------------------------------------------------------

def save_agent_decision(
    agent_name: str,
    decision_type: str,
    description: str,
    confidence: float = 1.0,
    tick: int = None,
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO agent_decisions (agent_name, decision_type, description, confidence, tick, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (agent_name, decision_type, description, confidence, tick, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def load_recent_decisions(limit: int = 10) -> list[dict]:
    limit = max(1, min(limit, 50))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT agent_name, decision_type, description, confidence, tick, created_at
        FROM agent_decisions
        ORDER BY id DESC
        LIMIT ?
        ''',
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "agent": r["agent_name"],
            "type": r["decision_type"],
            "description": r["description"],
            "confidence": r["confidence"],
            "tick": r["tick"],
            "at": r["created_at"],
        }
        for r in reversed(rows)
    ]


def clear_agent_decisions() -> int:
    """Delete all decision history rows and return deleted row count."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) AS c FROM agent_decisions')
    row = cursor.fetchone()
    count = int(row['c']) if row else 0
    cursor.execute('DELETE FROM agent_decisions')
    conn.commit()
    conn.close()
    return count


def prune_old_data(max_telemetry: int = 5000, max_events: int = 1000, max_decisions: int = 1000):
    """Keep only the latest rows in telemetry, market_events, and agent_decisions to prevent bloat."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Prune telemetry
        cursor.execute('''
            DELETE FROM telemetry 
            WHERE id NOT IN (
                SELECT id FROM telemetry ORDER BY id DESC LIMIT ?
            )
        ''', (max_telemetry,))
        
        # Prune market_events
        cursor.execute('''
            DELETE FROM market_events 
            WHERE id NOT IN (
                SELECT id FROM market_events ORDER BY id DESC LIMIT ?
            )
        ''', (max_events,))
        
        # Prune agent_decisions
        cursor.execute('''
            DELETE FROM agent_decisions 
            WHERE id NOT IN (
                SELECT id FROM agent_decisions ORDER BY id DESC LIMIT ?
            )
        ''', (max_decisions,))
        
        conn.commit()
    except Exception as e:
        print(f"[Database] Pruning error: {e}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Resident Personas & Thoughts (Dynamic Citizens)
# ---------------------------------------------------------------------------

def save_resident_persona(
    persona_id: str,
    name: str,
    age: int,
    occupation: str,
    income_tier: str,
    bio: str,
    vehicle_type: str,
    traits: dict,
):
    """Save or update a resident persona's profile and behavioral traits."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT OR REPLACE INTO resident_personas (id, name, age, occupation, income_tier, bio, vehicle_type, traits_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (persona_id, name, age, occupation, income_tier, bio, vehicle_type, json.dumps(traits)),
    )
    conn.commit()
    conn.close()


def load_resident_personas() -> dict[str, dict]:
    """Load all resident personas as a dictionary keyed by resident ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT id, name, age, occupation, income_tier, bio, vehicle_type, traits_json
        FROM resident_personas
        '''
    )
    rows = cursor.fetchall()
    conn.close()
    
    personas = {}
    for r in rows:
        try:
            traits = json.loads(r["traits_json"])
        except Exception:
            traits = {}
        personas[r["id"]] = {
            "id": r["id"],
            "name": r["name"],
            "age": r["age"],
            "occupation": r["occupation"],
            "income_tier": r["income_tier"],
            "bio": r["bio"],
            "vehicle_type": r["vehicle_type"],
            "traits": traits,
        }
    return personas


def save_resident_thought(
    resident_id: str,
    tick: int,
    decision_type: str,
    thought: str,
    sentiment: str,
):
    """Save an LLM-generated thought and sentiment log for a resident."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO resident_thoughts (resident_id, tick, decision_type, thought, sentiment, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (resident_id, tick, decision_type, thought, sentiment, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def load_resident_thoughts(resident_id: str, limit: int = 20) -> list[dict]:
    """Retrieve the recent thoughts history for a specific resident."""
    limit = max(1, min(limit, 100))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT tick, decision_type, thought, sentiment, created_at
        FROM resident_thoughts
        WHERE resident_id = ?
        ORDER BY id DESC
        LIMIT ?
        ''',
        (resident_id, limit),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "tick": r["tick"],
            "type": r["decision_type"],
            "thought": r["thought"],
            "sentiment": r["sentiment"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


def load_recent_thoughts_summary(limit: int = 50) -> list[dict]:
    """Retrieve recent thoughts across all residents to compute aggregate sentiments."""
    limit = max(1, min(limit, 200))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT resident_id, tick, decision_type, thought, sentiment, created_at
        FROM resident_thoughts
        ORDER BY id DESC
        LIMIT ?
        ''',
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "resident_id": r["resident_id"],
            "tick": r["tick"],
            "type": r["decision_type"],
            "thought": r["thought"],
            "sentiment": r["sentiment"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

