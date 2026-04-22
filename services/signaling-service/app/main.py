"""
Signaling Service - WebSocket connections, WebRTC signaling, and user matching
Port: 8001
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from datetime import datetime
from typing import Dict, List, Optional
import sys
import os
import uuid
import redis

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.database import SessionLog, MatchLog, get_db_session, init_db
from shared.utils import get_service_config

app = FastAPI(title="Signaling Service", version="2.0.0")

config = get_service_config()

# Redis with in-memory fallback
redis_client = None
try:
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        redis_client = redis.from_url(redis_url, decode_responses=True)
    else:
        redis_client = redis.Redis(
            host=config["redis_host"],
            port=int(config["redis_port"]),
            decode_responses=True
        )
    redis_client.ping()
    print("✅ Connected to Redis for distributed queue")
except Exception:
    print("⚠️ Redis unavailable - using in-memory queue")
    redis_client = None

# In-memory fallback state
memory_queue: List[str] = []
memory_matches: Dict[str, str] = {}  # user_token -> peer_token


# --- Matching helpers (inline, no HTTP calls) ---

def _queue_find_match(user_token: str) -> dict:
    """Find or queue a match. Returns {status, peer_token?, match_id?}"""
    if redis_client:
        # Already matched?
        existing = redis_client.get(f"user_match:{user_token}")
        if existing:
            return {"status": "already_matched", "peer_token": existing}

        peer_token = redis_client.lpop("waiting_queue")
        if peer_token and peer_token != user_token:
            match_id = str(uuid.uuid4())
            redis_client.set(f"user_match:{user_token}", peer_token, ex=3600)
            redis_client.set(f"user_match:{peer_token}", user_token, ex=3600)
            _write_match_log(match_id, user_token, peer_token)
            return {"status": "matched", "peer_token": peer_token, "match_id": match_id}
        else:
            redis_client.rpush("waiting_queue", user_token)
            return {"status": "waiting"}
    else:
        if user_token in memory_matches:
            return {"status": "already_matched", "peer_token": memory_matches[user_token]}

        if memory_queue and memory_queue[0] != user_token:
            peer_token = memory_queue.pop(0)
            match_id = str(uuid.uuid4())
            memory_matches[user_token] = peer_token
            memory_matches[peer_token] = user_token
            _write_match_log(match_id, user_token, peer_token)
            return {"status": "matched", "peer_token": peer_token, "match_id": match_id}
        else:
            if user_token not in memory_queue:
                memory_queue.append(user_token)
            return {"status": "waiting"}


def _queue_leave_match(user_token: str) -> Optional[str]:
    """Clean up match/queue state. Returns peer_token if was in a match."""
    if redis_client:
        peer_token = redis_client.get(f"user_match:{user_token}")
        if peer_token:
            redis_client.delete(f"user_match:{user_token}")
            redis_client.delete(f"user_match:{peer_token}")
            _end_match_log(user_token, peer_token)
            return peer_token
        redis_client.lrem("waiting_queue", 0, user_token)
    else:
        peer_token = memory_matches.pop(user_token, None)
        if peer_token:
            memory_matches.pop(peer_token, None)
            _end_match_log(user_token, peer_token)
            return peer_token
        if user_token in memory_queue:
            memory_queue.remove(user_token)
    return None


def _write_match_log(match_id: str, user_a: str, user_b: str):
    db = get_db_session()
    try:
        db.add(MatchLog(match_id=match_id, user_a=user_a, user_b=user_b, started_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _end_match_log(user_a: str, user_b: str):
    db = get_db_session()
    try:
        match = db.query(MatchLog).filter(
            ((MatchLog.user_a == user_a) & (MatchLog.user_b == user_b)) |
            ((MatchLog.user_a == user_b) & (MatchLog.user_b == user_a)),
            MatchLog.ended_at == None
        ).first()
        if match:
            match.ended_at = datetime.utcnow()
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _log_session_connect(user_token: str):
    db = get_db_session()
    try:
        db.add(SessionLog(user_token=user_token, ip_address="ws_client", connected_at=datetime.utcnow()))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _log_session_disconnect(user_token: str):
    db = get_db_session()
    try:
        sessions = db.query(SessionLog).filter(
            SessionLog.user_token == user_token,
            SessionLog.disconnected_at == None
        ).all()
        for s in sessions:
            s.disconnected_at = datetime.utcnow()
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# --- Connection manager ---

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_matches: Dict[str, str] = {}  # ws-level match map (user_id -> peer_id)

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        _log_session_connect(user_id)
        print(f"✅ {user_id} connected. Total: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        self.user_matches.pop(user_id, None)
        _log_session_disconnect(user_id)
        print(f"❌ {user_id} disconnected. Remaining: {len(self.active_connections)}")

    async def send(self, message: dict, user_id: str):
        ws = self.active_connections.get(user_id)
        if ws:
            await ws.send_json(message)

    async def find_match(self, user_id: str):
        # Leave any existing match first
        await self._do_leave(user_id)

        result = _queue_find_match(user_id)

        if result["status"] == "matched":
            peer_id = result["peer_token"]
            match_id = result["match_id"]
            self.user_matches[user_id] = peer_id
            self.user_matches[peer_id] = user_id

            await self.send({"status": "matched", "peer_id": peer_id, "match_id": match_id, "initiator": True}, user_id)
            await self.send({"status": "matched", "peer_id": user_id, "match_id": match_id, "initiator": False}, peer_id)
        else:
            await self.send({"status": "waiting", "msg": "Looking for someone..."}, user_id)

    async def _do_leave(self, user_id: str):
        """Internal: clean up match state and notify peer."""
        peer_id = self.user_matches.pop(user_id, None)
        if peer_id:
            self.user_matches.pop(peer_id, None)
            _queue_leave_match(user_id)
            await self.send({"status": "peer_left", "msg": "Your partner has disconnected"}, peer_id)


manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Signaling Service started on port 8001")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "signaling",
        "connections": len(manager.active_connections),
        "queue_backend": "redis" if redis_client else "memory"
    }


@app.get("/stats")
async def get_stats():
    return {
        "active_connections": len(manager.active_connections),
        "active_matches": len(manager.user_matches) // 2,
        "users_online": list(manager.active_connections.keys())
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    user_id = token if token else f"user_{str(uuid.uuid4())[:8]}"

    await manager.connect(websocket, user_id)
    await manager.send({"status": "identity", "user_id": user_id}, user_id)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "find_match":
                await manager.find_match(user_id)

            elif action == "chat":
                peer_id = manager.user_matches.get(user_id)
                if peer_id:
                    msg = data.get("msg")
                    await manager.send({"status": "chat", "msg": msg, "sender": "peer"}, peer_id)
                    await manager.send({"status": "chat", "msg": msg, "sender": "me"}, user_id)

            elif action == "signal":
                peer_id = manager.user_matches.get(user_id)
                if peer_id:
                    await manager.send({
                        "status": "signal",
                        "sender": user_id,
                        "payload": data.get("payload")
                    }, peer_id)

    except WebSocketDisconnect:
        await manager._do_leave(user_id)
        manager.disconnect(user_id)
    except Exception as e:
        print(f"❌ WebSocket error for {user_id}: {e}")
        await manager._do_leave(user_id)
        manager.disconnect(user_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
