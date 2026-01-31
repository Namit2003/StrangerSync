"""
API Gateway - Central entry point for all microservices
Port: 8000
"""
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx
import os

app = FastAPI(title="StrangerSync API Gateway", version="1.0.0")

# Mount static files
static_path = os.path.join(os.path.dirname(__file__), '../../..', 'static')
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

# Service URLs
ADMIN_SERVICE = os.getenv("ADMIN_SERVICE_URL", "http://localhost:8003")
MATCHING_SERVICE = os.getenv("MATCHING_SERVICE_URL", "http://localhost:8002")
USER_SERVICE = os.getenv("USER_SERVICE_URL", "http://localhost:8004")
SIGNALING_SERVICE = os.getenv("SIGNALING_SERVICE_URL", "http://localhost:8001")

# Health check
@app.get("/health")
async def health_check():
    """Gateway health check"""
    services_status = {}
    
    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in [
            ("admin", ADMIN_SERVICE),
            ("matching", MATCHING_SERVICE),
            ("user", USER_SERVICE),
            ("signaling", SIGNALING_SERVICE)
        ]:
            try:
                resp = await client.get(f"{url}/health")
                services_status[name] = "healthy" if resp.status_code == 200 else "unhealthy"
            except:
                services_status[name] = "unreachable"
    
    return {
        "status": "healthy",
        "service": "api-gateway",
        "services": services_status
    }

# Serve main page
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application page"""
    index_path = os.path.join(os.path.dirname(__file__), '../../..', 'static', 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>StrangerSync API Gateway</h1><p>Microservices are running!</p>")

@app.get("/favicon.ico")
async def favicon():
    """Serve favicon"""
    favicon_path = os.path.join(os.path.dirname(__file__), '../../..', 'static', 'favicon.svg')
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    return JSONResponse({"status": "not found"}, status_code=404)

# ==================== ADMIN ROUTES ====================

@app.get("/admin")
@app.get("/admin/dashboard")
async def admin_routes(request: Request):
    """Proxy admin routes"""
    async with httpx.AsyncClient() as client:
        headers = dict(request.headers)
        response = await client.get(
            f"{ADMIN_SERVICE}{request.url.path}",
            headers=headers,
            cookies=request.cookies
        )
        return HTMLResponse(response.text, status_code=response.status_code)

@app.post("/admin/login")
async def admin_login(request: Request):
    """Proxy admin login"""
    async with httpx.AsyncClient() as client:
        form_data = await request.form()
        response = await client.post(
            f"{ADMIN_SERVICE}/admin/login",
            data=form_data
        )
        
        # Create response with cookies
        resp = JSONResponse(
            {"status": "success"} if response.status_code == 302 else {"status": "error"},
            status_code=response.status_code
        )
        
        # Copy cookies from service response
        for cookie_name, cookie_value in response.cookies.items():
            resp.set_cookie(key=cookie_name, value=cookie_value)
        
        return resp

@app.get("/api/stats")
async def admin_stats(request: Request):
    """Proxy admin stats"""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{ADMIN_SERVICE}/api/stats",
            cookies=request.cookies
        )
        return JSONResponse(response.json(), status_code=response.status_code)

# ==================== USER SERVICE ROUTES ====================

@app.post("/api/users")
async def create_user(request: Request):
    """Create user session"""
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{USER_SERVICE}/users", json=body)
        return JSONResponse(response.json(), status_code=response.status_code)

@app.get("/api/users/{user_token}")
async def get_user(user_token: str):
    """Get user info"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{USER_SERVICE}/users/{user_token}")
        return JSONResponse(response.json(), status_code=response.status_code)

@app.get("/api/users/active/list")
async def get_active_users():
    """Get active users"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{USER_SERVICE}/users/active/list")
        return JSONResponse(response.json(), status_code=response.status_code)

# ==================== MATCHING SERVICE ROUTES ====================

@app.post("/api/match/find")
async def find_match(request: Request):
    """Find a match"""
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{MATCHING_SERVICE}/match/find", json=body)
        return JSONResponse(response.json(), status_code=response.status_code)

@app.post("/api/match/leave")
async def leave_match(request: Request):
    """Leave match"""
    async with httpx.AsyncClient() as client:
        body = await request.json()
        response = await client.post(f"{MATCHING_SERVICE}/match/leave", json=body)
        return JSONResponse(response.json(), status_code=response.status_code)

@app.get("/api/match/stats")
async def match_stats():
    """Get matching stats"""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{MATCHING_SERVICE}/match/stats")
        return JSONResponse(response.json(), status_code=response.status_code)

# ==================== WEBSOCKET PROXY ====================

@app.websocket("/ws")
async def websocket_proxy(websocket: WebSocket, token: str = None):
    """WebSocket redirect info"""
    await websocket.accept()
    await websocket.send_json({
        "status": "redirect",
        "message": "Please connect to ws://localhost:8001/ws for real-time features",
        "signaling_url": "ws://localhost:8001/ws"
    })
    await websocket.close()

# System stats aggregation
@app.get("/api/system/stats")
async def system_stats():
    """Aggregate stats from all services"""
    stats = {}
    
    async with httpx.AsyncClient(timeout=2.0) as client:
        # User stats
        try:
            resp = await client.get(f"{USER_SERVICE}/users/count")
            stats["users"] = resp.json()
        except:
            stats["users"] = {"error": "unavailable"}
        
        # Match stats
        try:
            resp = await client.get(f"{MATCHING_SERVICE}/match/stats")
            stats["matching"] = resp.json()
        except:
            stats["matching"] = {"error": "unavailable"}
        
        # Signaling stats
        try:
            resp = await client.get(f"{SIGNALING_SERVICE}/stats")
            stats["signaling"] = resp.json()
        except:
            stats["signaling"] = {"error": "unavailable"}
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
