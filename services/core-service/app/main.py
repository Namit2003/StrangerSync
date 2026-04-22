"""
Core Service - Static files, user session API, and system stats
Port: 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime
import httpx
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.database import SessionLog, get_db_session, init_db

app = FastAPI(title="StrangerSync Core Service", version="2.0.0")

SIGNALING_SERVICE = os.getenv("SIGNALING_SERVICE_URL", "http://localhost:8001")

# Mount static files
static_path = os.getenv("STATIC_PATH", "/app/static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Core Service started on port 8000")


@app.get("/health")
async def health_check():
    signaling_status = "unreachable"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{SIGNALING_SERVICE}/health")
            signaling_status = "healthy" if resp.status_code == 200 else "unhealthy"
    except Exception:
        pass
    return {
        "status": "healthy",
        "service": "core",
        "services": {"signaling": signaling_status}
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    index_path = os.path.join(static_path, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>StrangerSync</h1>")


@app.get("/config.js", response_class=PlainTextResponse)
async def config_js():
    signaling_url = os.getenv("SIGNALING_WS_URL", "")
    if signaling_url:
        js = f'window.SIGNALING_URL = "{signaling_url}";'
    else:
        js = "// local mode: WebSocket connects via nginx"
    return PlainTextResponse(js, media_type="application/javascript")


@app.get("/favicon.ico")
async def favicon():
    favicon_path = os.path.join(static_path, "favicon.svg")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse({"status": "not found"}, status_code=404)


# ==================== USER SESSION ROUTES ====================

class UserCreate(BaseModel):
    user_token: str
    ip_address: str


@app.post("/api/users")
async def create_user(user: UserCreate):
    db = get_db_session()
    try:
        session = SessionLog(
            user_token=user.user_token,
            ip_address=user.ip_address,
            connected_at=datetime.utcnow()
        )
        db.add(session)
        db.commit()
        return {"status": "success", "user_token": user.user_token, "session_id": session.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@app.get("/api/users/{user_token}")
async def get_user(user_token: str):
    db = get_db_session()
    try:
        session = db.query(SessionLog).filter(
            SessionLog.user_token == user_token,
            SessionLog.disconnected_at == None
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="User not found")
        return {"user_token": session.user_token, "connected_at": session.connected_at, "active": True}
    finally:
        db.close()


@app.get("/api/users/active/list")
async def get_active_users():
    db = get_db_session()
    try:
        active = db.query(SessionLog).filter(SessionLog.disconnected_at == None).all()
        return {"active_users": [s.user_token for s in active], "count": len(active)}
    finally:
        db.close()


# ==================== SYSTEM STATS ====================

@app.get("/api/system/stats")
async def system_stats():
    db = get_db_session()
    try:
        active_count = db.query(SessionLog).filter(SessionLog.disconnected_at == None).count()
        total_count = db.query(SessionLog).count()
    finally:
        db.close()

    signaling_stats = {}
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{SIGNALING_SERVICE}/stats")
            signaling_stats = resp.json()
    except Exception:
        signaling_stats = {"error": "unavailable"}

    return {
        "users": {"active_count": active_count, "total_sessions": total_count},
        "signaling": signaling_stats
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
