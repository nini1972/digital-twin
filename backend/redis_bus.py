"""Redis pub/sub event bus for the digital twin.

Falls back gracefully to an in-process asyncio.Queue when Redis is unavailable
(e.g. local dev without a Redis server).  All other modules import from here
so they never hard-couple to Redis being present.
"""

import asyncio
import json
import os
from typing import Optional

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Channel names
CHANNEL_SIM_TICK = "simulation.tick"
CHANNEL_AGENT_ACTION = "agent.action"
CHANNEL_ORACLE_DECISION = "oracle.decision"
CHANNEL_PREDICTION_LOG = "prediction.log"
CHANNEL_SCOUT_EV = "scout.ev"
CHANNEL_SCOUT_TRAFFIC = "scout.traffic"
CHANNEL_ANALYZER_DEMAND = "analyzer.demand"
CHANNEL_ANALYZER_CONGESTION = "analyzer.congestion"


class RedisBus:
    """Thin wrapper around Redis pub/sub with in-process asyncio.Queue fallback."""

    def __init__(self):
        self._redis: Optional[object] = None
        self._available = False
        # channel_name -> list[asyncio.Queue]
        self._local_queues: dict[str, list[asyncio.Queue]] = {}

    async def connect(self):
        if not _REDIS_AVAILABLE:
            print("[RedisBus] redis-py not installed — using in-process fallback.")
            return
        try:
            self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)
            await self._redis.ping()
            self._available = True
            print(f"[RedisBus] Connected: {REDIS_URL}")
        except Exception as e:
            print(f"[RedisBus] Unavailable ({e}) — using in-process fallback.")
            self._redis = None
            self._available = False

    async def publish(self, channel: str, data: dict):
        if self._available and self._redis:
            try:
                await self._redis.publish(channel, json.dumps(data))
                return
            except Exception as e:
                print(f"[RedisBus] publish error: {e}")
        # In-process fallback delivery
        for q in self._local_queues.get(channel, []):
            await q.put((channel, data))

    def subscribe_local(self, channel: str) -> asyncio.Queue:
        """Return an asyncio.Queue that receives (channel, data) tuples."""
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._local_queues.setdefault(channel, []).append(q)
        return q

    async def close(self):
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass


bus = RedisBus()
