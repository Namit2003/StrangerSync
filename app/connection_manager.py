from fastapi import WebSocket
from typing import Dict, List
from app.database import SessionLocal, SessionLog, MatchLog
from sqlalchemy import or_
from datetime import datetime
import uuid

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.waiting_queue: List[str] = []
        # [CRITICAL] This dictionary remembers who is talking to whom
        self.active_matches: Dict[str, str] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        
        # DB: Log Session
        db = SessionLocal()
        new_session = SessionLog(user_token=client_id, ip_address="127.0.0.1")
        db.add(new_session)
        db.commit()
        db.close()
        print(f"Client {client_id} connected.")

    async def disconnect(self, client_id: str):
        # If user closes tab, we treat it same as leaving a match
        await self.handle_leave_match(client_id)
        
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.waiting_queue:
            self.waiting_queue.remove(client_id)
        
        # DB: End Session
        db = SessionLocal()
        session = db.query(SessionLog).filter(
            SessionLog.user_token == client_id, 
            SessionLog.disconnected_at == None
        ).order_by(SessionLog.id.desc()).first()
        if session:
            session.disconnected_at = datetime.utcnow()
            db.commit()
        db.close()
        print(f"Client {client_id} disconnected.")

    # [CRITICAL] This function notifies the partner when you click "Next"
    async def handle_leave_match(self, client_id: str):
        if client_id in self.active_matches:
            partner_id = self.active_matches[client_id]
            
            # Clean up memory
            if partner_id in self.active_matches:
                del self.active_matches[partner_id]
            del self.active_matches[client_id]

            # Notify the partner so they unfreeze and auto-search
            await self.send_personal_message({
                "status": "peer_left", 
                "msg": "Stranger skipped you."
            }, partner_id)

            # DB: Close Match
            db = SessionLocal()
            active_match = db.query(MatchLog).filter(
                or_(MatchLog.user_a == client_id, MatchLog.user_b == client_id),
                MatchLog.ended_at == None
            ).first()
            if active_match:
                active_match.ended_at = datetime.utcnow()
                db.commit()
            db.close()

    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except:
                pass

    async def find_match(self, client_id: str):
        # [CRITICAL] If I am already in a match (clicked Next), end it first!
        await self.handle_leave_match(client_id)

        if client_id in self.waiting_queue:
            return

        if len(self.waiting_queue) == 0:
            self.waiting_queue.append(client_id)
            await self.send_personal_message({"status": "waiting", "msg": "Looking for someone..."}, client_id)
            return

        peer_id = self.waiting_queue.pop(0)
        
        if peer_id not in self.active_connections:
            await self.find_match(client_id)
            return

        # [CRITICAL] Save the match to memory so 'handle_leave_match' works later
        self.active_matches[client_id] = peer_id
        self.active_matches[peer_id] = client_id

        # DB: Create Match
        match_uuid = str(uuid.uuid4())
        db = SessionLocal()
        new_match = MatchLog(match_id=match_uuid, user_a=client_id, user_b=peer_id)
        db.add(new_match)
        db.commit()
        db.close()

        await self.send_personal_message({
            "status": "matched", "peer_id": peer_id, "initiator": True
        }, client_id)
        
        await self.send_personal_message({
            "status": "matched", "peer_id": client_id, "initiator": False
        }, peer_id)

manager = ConnectionManager()