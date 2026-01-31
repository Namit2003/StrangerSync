"""
Signaling Service - Microservice for WebSocket connections and WebRTC signaling
Port: 8001
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import Dict
import sys
import os
import json
import httpx

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.utils import get_service_config

app = FastAPI(title="Signaling Service", version="1.0.0")

# Configuration
config = get_service_config()
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8004")
MATCHING_SERVICE_URL = os.getenv("MATCHING_SERVICE_URL", "http://localhost:8002")

# Connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_matches: Dict[str, str] = {}  # user_id -> peer_id
    
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and store WebSocket connection"""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"✅ Client {user_id} connected. Total: {len(self.active_connections)}")
        
        # Notify User Service
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{USER_SERVICE_URL}/users",
                    json={"user_token": user_id, "ip_address": "ws_client"},
                    timeout=2.0
                )
        except Exception as e:
            print(f"⚠️ User Service unavailable: {e}")
    
    def disconnect(self, user_id: str):
        """Remove connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_matches:
            del self.user_matches[user_id]
        print(f"❌ Client {user_id} disconnected. Remaining: {len(self.active_connections)}")
        
        # Notify User Service
        try:
            httpx.post(
                f"{USER_SERVICE_URL}/users/{user_id}/disconnect",
                timeout=2.0
            )
        except:
            pass
    
    async def send_personal_message(self, message: dict, user_id: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)
    
    async def broadcast(self, message: dict):
        """Broadcast to all connected users"""
        for connection in self.active_connections.values():
            await connection.send_json(message)
    
    async def find_match(self, user_id: str):
        """Request match from Matching Service"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{MATCHING_SERVICE_URL}/match/find",
                    json={"user_token": user_id},
                    timeout=5.0
                )
                match_data = response.json()
                
                if match_data["status"] == "matched":
                    peer_id = match_data["peer_token"]
                    match_id = match_data["match_id"]
                    
                    # Store match
                    self.user_matches[user_id] = peer_id
                    self.user_matches[peer_id] = user_id
                    
                    # Notify both users
                    await self.send_personal_message({
                        "status": "matched",
                        "peer_id": peer_id,
                        "match_id": match_id,
                        "initiator": True
                    }, user_id)
                    
                    await self.send_personal_message({
                        "status": "matched",
                        "peer_id": user_id,
                        "match_id": match_id,
                        "initiator": False
                    }, peer_id)
                else:
                    # Waiting
                    await self.send_personal_message({
                        "status": "waiting",
                        "msg": "Looking for someone..."
                    }, user_id)
        except Exception as e:
            print(f"❌ Matching Service error: {e}")
            await self.send_personal_message({
                "status": "error",
                "msg": "Matching service unavailable"
            }, user_id)
    
    async def leave_match(self, user_id: str):
        """Leave current match"""
        peer_id = self.user_matches.get(user_id)
        
        if peer_id:
            # Notify Matching Service
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{MATCHING_SERVICE_URL}/match/leave",
                        json={"user_token": user_id},
                        timeout=2.0
                    )
            except:
                pass
            
            # Notify peer
            await self.send_personal_message({
                "status": "peer_left",
                "msg": "Your partner has disconnected"
            }, peer_id)
            
            # Cleanup local state
            self.user_matches.pop(user_id, None)
            self.user_matches.pop(peer_id, None)

manager = ConnectionManager()

# Initialize service
@app.on_event("startup")
async def startup_event():
    print("✅ Signaling Service started on port 8001")

# Health check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "signaling",
        "connections": len(manager.active_connections)
    }

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = None):
    """Main WebSocket endpoint for real-time communication"""
    
    # Generate or use provided user ID
    if token:
        user_id = token
    else:
        import uuid
        user_id = f"user_{str(uuid.uuid4())[:8]}"
    
    await manager.connect(websocket, user_id)
    
    # Send identity
    await manager.send_personal_message({
        "status": "identity",
        "user_id": user_id
    }, user_id)
    
    try:
        while True:
            # Receive JSON data
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "find_match":
                await manager.find_match(user_id)
            
            elif action == "leave_match":
                await manager.leave_match(user_id)
            
            elif action == "chat":
                # Forward chat message to peer
                peer_id = manager.user_matches.get(user_id)
                if peer_id:
                    await manager.send_personal_message({
                        "status": "chat",
                        "msg": data.get("msg"),
                        "sender": "peer"
                    }, peer_id)
            
            elif action == "signal":
                # WebRTC signaling (offer, answer, ICE candidates)
                peer_id = manager.user_matches.get(user_id)
                if peer_id:
                    signal_data = {
                        "status": "signal",
                        "signal_type": data.get("signal_type"),
                        "signal_data": data.get("signal_data")
                    }
                    await manager.send_personal_message(signal_data, peer_id)
    
    except WebSocketDisconnect:
        await manager.leave_match(user_id)
        manager.disconnect(user_id)
    except Exception as e:
        print(f"❌ WebSocket error for {user_id}: {e}")
        await manager.leave_match(user_id)
        manager.disconnect(user_id)

# Stats endpoint
@app.get("/stats")
async def get_stats():
    """Get connection statistics"""
    return {
        "active_connections": len(manager.active_connections),
        "active_matches": len(manager.user_matches) // 2,
        "users_online": list(manager.active_connections.keys())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
