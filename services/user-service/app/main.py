"""
User Service - Microservice for user session management
Port: 8004
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import sys
import os
import redis

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.database import SessionLog, get_db_session, init_db
from shared.utils import get_service_config

app = FastAPI(title="User Service", version="1.0.0")

# Configuration
config = get_service_config()

# Redis connection with fallback — supports REDIS_URL (Railway) or individual host/port vars
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
    print("✅ Connected to Redis")
except:
    print("⚠️ Redis unavailable - using database only mode")
    redis_client = None

# Request models
class UserCreate(BaseModel):
    user_token: str
    ip_address: str

# Initialize service
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ User Service started on port 8004")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "user",
        "redis": "connected" if redis_client else "unavailable"
    }

# Create user session
@app.post("/users")
async def create_user(user: UserCreate):
    db = get_db_session()
    try:
        # Create session log
        session = SessionLog(
            user_token=user.user_token,
            ip_address=user.ip_address,
            connected_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        
        # Add to Redis active users if available
        if redis_client:
            try:
                redis_client.sadd("active_users", user.user_token)
                redis_client.publish("user_events", f"user_connected:{user.user_token}")
            except:
                pass
        
        return {
            "status": "success",
            "user_token": user.user_token,
            "session_id": session.id
        }
    finally:
        db.close()

# Get user info
@app.get("/users/{user_token}")
async def get_user(user_token: str):
    db = get_db_session()
    try:
        session = db.query(SessionLog).filter(
            SessionLog.user_token == user_token,
            SessionLog.disconnected_at == None
        ).first()
        
        if not session:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_token": session.user_token,
            "connected_at": session.connected_at,
            "active": True
        }
    finally:
        db.close()

# Disconnect user
@app.post("/users/{user_token}/disconnect")
async def disconnect_user(user_token: str):
    db = get_db_session()
    try:
        # Update session
        sessions = db.query(SessionLog).filter(
            SessionLog.user_token == user_token,
            SessionLog.disconnected_at == None
        ).all()
        
        for session in sessions:
            session.disconnected_at = datetime.utcnow()
        db.commit()
        
        # Remove from Redis if available
        if redis_client:
            try:
                redis_client.srem("active_users", user_token)
                redis_client.publish("user_events", f"user_disconnected:{user_token}")
            except:
                pass
        
        return {"status": "disconnected", "user_token": user_token}
    finally:
        db.close()

# Get active users list
@app.get("/users/active/list")
async def get_active_users():
    # Try Redis first
    if redis_client:
        try:
            active_users = redis_client.smembers("active_users")
            return {
                "active_users": list(active_users),
                "count": len(active_users),
                "source": "redis"
            }
        except:
            pass
    
    # Fallback to database
    db = get_db_session()
    try:
        active_sessions = db.query(SessionLog).filter(
            SessionLog.disconnected_at == None
        ).all()
        
        return {
            "active_users": [s.user_token for s in active_sessions],
            "count": len(active_sessions),
            "source": "database"
        }
    finally:
        db.close()

# Get user count
@app.get("/users/count")
async def get_user_count():
    db = get_db_session()
    try:
        active_count = db.query(SessionLog).filter(
            SessionLog.disconnected_at == None
        ).count()
        total_count = db.query(SessionLog).count()
        
        return {
            "active_count": active_count,
            "total_sessions": total_count
        }
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
