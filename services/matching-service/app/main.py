"""
Matching Service - Microservice for user queue management and pairing
Port: 8002
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import sys
import os
import uuid
import redis
import asyncio

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.database import MatchLog, get_db_session, init_db
from shared.utils import get_service_config

app = FastAPI(title="Matching Service", version="1.0.0")

# Configuration
config = get_service_config()

# Redis connection with in-memory fallback
redis_client = None
try:
    redis_client = redis.Redis(
        host=config["redis_host"],
        port=int(config["redis_port"]),
        decode_responses=True
    )
    redis_client.ping()
    print("✅ Connected to Redis for distributed queue")
except:
    print("⚠️ Redis unavailable - using in-memory queue")
    redis_client = None

# In-memory fallback queue
memory_queue = []
memory_matches = {}  # user_token -> peer_token

# Request models
class MatchRequest(BaseModel):
    user_token: str

class LeaveRequest(BaseModel):
    user_token: str

# Initialize service
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Matching Service started on port 8002")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "matching",
        "queue_backend": "redis" if redis_client else "memory"
    }

# Find match
@app.post("/match/find")
async def find_match(request: MatchRequest):
    user_token = request.user_token
    
    if redis_client:
        return await _find_match_redis(user_token)
    else:
        return await _find_match_memory(user_token)

async def _find_match_redis(user_token: str):
    """Redis-based matching"""
    try:
        # Check if already in a match
        existing_match = redis_client.get(f"user_match:{user_token}")
        if existing_match:
            return {
                "status": "already_matched",
                "peer_token": existing_match
            }
        
        # Try to pop someone from queue
        peer_token = redis_client.lpop("waiting_queue")
        
        if peer_token and peer_token != user_token:
            # Create match
            match_id = str(uuid.uuid4())
            
            # Store match in Redis
            redis_client.set(f"user_match:{user_token}", peer_token, ex=3600)
            redis_client.set(f"user_match:{peer_token}", user_token, ex=3600)
            redis_client.incr("active_matches")
            
            # Store in database
            db = get_db_session()
            try:
                match_log = MatchLog(
                    match_id=match_id,
                    user_a=user_token,
                    user_b=peer_token,
                    started_at=datetime.utcnow()
                )
                db.add(match_log)
                db.commit()
            finally:
                db.close()
            
            # Publish event
            try:
                redis_client.publish("match_events", f"match_created:{match_id}:{user_token}:{peer_token}")
            except:
                pass
            
            return {
                "status": "matched",
                "peer_token": peer_token,
                "match_id": match_id
            }
        else:
            # Add to queue
            redis_client.rpush("waiting_queue", user_token)
            return {"status": "waiting", "queue_position": redis_client.llen("waiting_queue")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _find_match_memory(user_token: str):
    """In-memory matching fallback"""
    # Check if already matched
    if user_token in memory_matches:
        return {
            "status": "already_matched",
            "peer_token": memory_matches[user_token]
        }
    
    # Try to match with someone in queue
    if memory_queue and memory_queue[0] != user_token:
        peer_token = memory_queue.pop(0)
        match_id = str(uuid.uuid4())
        
        # Store match
        memory_matches[user_token] = peer_token
        memory_matches[peer_token] = user_token
        
        # Store in database
        db = get_db_session()
        try:
            match_log = MatchLog(
                match_id=match_id,
                user_a=user_token,
                user_b=peer_token,
                started_at=datetime.utcnow()
            )
            db.add(match_log)
            db.commit()
        finally:
            db.close()
        
        return {
            "status": "matched",
            "peer_token": peer_token,
            "match_id": match_id
        }
    else:
        # Add to queue if not already there
        if user_token not in memory_queue:
            memory_queue.append(user_token)
        return {"status": "waiting", "queue_position": len(memory_queue)}

# Leave match
@app.post("/match/leave")
async def leave_match(request: LeaveRequest):
    user_token = request.user_token
    
    if redis_client:
        return await _leave_match_redis(user_token)
    else:
        return await _leave_match_memory(user_token)

async def _leave_match_redis(user_token: str):
    """Redis-based leave match"""
    try:
        peer_token = redis_client.get(f"user_match:{user_token}")
        
        if peer_token:
            # Remove match
            redis_client.delete(f"user_match:{user_token}")
            redis_client.delete(f"user_match:{peer_token}")
            redis_client.decr("active_matches")
            
            # Update database
            db = get_db_session()
            try:
                match = db.query(MatchLog).filter(
                    ((MatchLog.user_a == user_token) & (MatchLog.user_b == peer_token)) |
                    ((MatchLog.user_a == peer_token) & (MatchLog.user_b == user_token)),
                    MatchLog.ended_at == None
                ).first()
                
                if match:
                    match.ended_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
            
            # Publish event
            try:
                redis_client.publish("match_events", f"match_ended:{user_token}:{peer_token}")
            except:
                pass
            
            return {"status": "left", "peer_token": peer_token}
        else:
            # Remove from queue if present
            redis_client.lrem("waiting_queue", 0, user_token)
            return {"status": "removed_from_queue"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _leave_match_memory(user_token: str):
    """In-memory leave match"""
    if user_token in memory_matches:
        peer_token = memory_matches[user_token]
        
        # Remove match
        del memory_matches[user_token]
        if peer_token in memory_matches:
            del memory_matches[peer_token]
        
        # Update database
        db = get_db_session()
        try:
            match = db.query(MatchLog).filter(
                ((MatchLog.user_a == user_token) & (MatchLog.user_b == peer_token)) |
                ((MatchLog.user_a == peer_token) & (MatchLog.user_b == user_token)),
                MatchLog.ended_at == None
            ).first()
            
            if match:
                match.ended_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        
        return {"status": "left", "peer_token": peer_token}
    else:
        # Remove from queue
        if user_token in memory_queue:
            memory_queue.remove(user_token)
        return {"status": "removed_from_queue"}

# Match status
@app.get("/match/status/{user_token}")
async def get_match_status(user_token: str):
    if redis_client:
        peer = redis_client.get(f"user_match:{user_token}")
        in_queue = redis_client.lpos("waiting_queue", user_token) is not None
    else:
        peer = memory_matches.get(user_token)
        in_queue = user_token in memory_queue
    
    return {
        "user_token": user_token,
        "matched": peer is not None,
        "peer_token": peer,
        "in_queue": in_queue
    }

# Match statistics
@app.get("/match/stats")
async def get_match_stats():
    if redis_client:
        try:
            queue_size = redis_client.llen("waiting_queue")
            active_matches = int(redis_client.get("active_matches") or 0)
        except:
            queue_size = 0
            active_matches = 0
        source = "redis"
    else:
        queue_size = len(memory_queue)
        active_matches = len(memory_matches) // 2
        source = "memory"
    
    # Get total matches from database
    db = get_db_session()
    try:
        total_matches = db.query(MatchLog).count()
    finally:
        db.close()
    
    return {
        "queue_size": queue_size,
        "active_matches": active_matches,
        "total_matches": total_matches,
        "source": source
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
