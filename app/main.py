from fastapi import FastAPI , WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from app.connection_manager import manager
from app.database import init_db
import uuid
import json 
from app.admin import router as admin_router

# Initialize the app
app = FastAPI()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

app.include_router(admin_router)

# 1. Tell FastAPI where the "static" folder is (for CSS/JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Tell FastAPI where the HTML templates are
templates = Jinja2Templates(directory="app/templates")

# 3. Serve the UI on the Homepage
@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# A health check route
@app.get("/health")
@app.head("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.svg")

@app.get("/.well-known/appspecific/com.chrome.devtools.json")
async def chrome_devtools_config():
    return {
        "devtools": {
            "custom_formatters": []
        }
    }

# This is the new Real-Time Endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    
    if token:
        client_id = token
    else:
        client_id = f"user_{str(uuid.uuid4())[:8]}"

    await manager.connect(websocket, client_id)

    await manager.send_personal_message({
        "status": "identity", 
        "user_id": client_id
    }, client_id)
    
    try:
        while True:
            # We expect JSON data now (e.g., { "action": "find_match" })
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "find_match":
                await manager.find_match(client_id)

            elif action == "chat":
                message_text = data.get("msg")
                # Find partner using the active_matches memory map
                partner_id = manager.active_matches.get(client_id)
                
                if partner_id:
                    # Send to Partner
                    await manager.send_personal_message({
                        "status": "chat",
                        "msg": message_text,
                        "sender": "peer"
                    }, partner_id)
                    
                    # Echo back to Sender (so we know it was sent successfully)
                    await manager.send_personal_message({
                        "status": "chat",
                        "msg": message_text,
                        "sender": "me"
                    }, client_id)
            
            elif action == "signal":
                # NEW: Relay WebRTC data to the specific peer
                target_peer_id = data.get("target") # Who is this for?
                payload = data.get("payload")       # The SDP or ICE data
                
                # Send it to the target
                await manager.send_personal_message({
                    "status": "signal",
                    "sender": client_id,
                    "payload": payload
                }, target_peer_id)
            
    except WebSocketDisconnect:
        await manager.disconnect(client_id)