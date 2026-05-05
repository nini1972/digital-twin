import sqlite3
import json
import os
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
    conn.commit()
    conn.close()

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
