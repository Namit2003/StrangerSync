"""
Admin Service - Microservice for administration and monitoring
Port: 8003
"""
from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import sys
import os

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.database import SessionLog, MatchLog, get_db_session, init_db
from shared.utils import get_admin_credentials
from sqlalchemy import text
from datetime import datetime

app = FastAPI(title="Admin Service", version="1.0.0")

# Templates (if needed, otherwise use simple HTML responses)
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
if not os.path.exists(templates_dir):
    os.makedirs(templates_dir)
templates = Jinja2Templates(directory=templates_dir)

# Admin credentials
admin_creds = get_admin_credentials()

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()
    print("✅ Admin Service started on port 8003")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "admin"}

# Admin login page
@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page():
    return """
    <html>
        <head><title>Admin Login</title></head>
        <body style="font-family: Arial; max-width: 400px; margin: 100px auto; padding: 20px;">
            <h2>Admin Login</h2>
            <form method="post" action="/admin/login">
                <div style="margin: 10px 0;">
                    <input type="text" name="username" placeholder="Username" style="width: 100%; padding: 10px;" required>
                </div>
                <div style="margin: 10px 0;">
                    <input type="password" name="password" placeholder="Password" style="width: 100%; padding: 10px;" required>
                </div>
                <button type="submit" style="width: 100%; padding: 10px; background: #007bff; color: white; border: none; cursor: pointer;">Login</button>
            </form>
        </body>
    </html>
    """

# Admin login handler
@app.post("/admin/login")
async def admin_login(username: str = Form(...), password: str = Form(...)):
    if username == admin_creds["username"] and password == admin_creds["password"]:
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(key="admin_session", value="authenticated")
        return response
    raise HTTPException(status_code=401, detail="Invalid credentials")

# Admin dashboard
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    # Check auth
    if request.cookies.get("admin_session") != "authenticated":
        return RedirectResponse(url="/admin")
    
    db = get_db_session()
    try:
        sessions_count = db.query(SessionLog).count()
        matches_count = db.query(MatchLog).count()
        active_sessions = db.query(SessionLog).filter(SessionLog.disconnected_at == None).count()
        
        return f"""
        <html>
            <head><title>Admin Dashboard</title></head>
            <body style="font-family: Arial; max-width: 1200px; margin: 20px auto; padding: 20px;">
                <h1>Admin Dashboard</h1>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin: 20px 0;">
                    <div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
                        <h3>Total Sessions</h3>
                        <p style="font-size: 2em; margin: 0;">{sessions_count}</p>
                    </div>
                    <div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
                        <h3>Total Matches</h3>
                        <p style="font-size: 2em; margin: 0;">{matches_count}</p>
                    </div>
                    <div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
                        <h3>Active Sessions</h3>
                        <p style="font-size: 2em; margin: 0;">{active_sessions}</p>
                    </div>
                </div>
                <h2>Actions</h2>
                <a href="/admin/sessions" style="padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px;">View Sessions</a>
                <a href="/admin/matches" style="padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; display: inline-block; margin: 5px;">View Matches</a>
            </body>
        </html>
        """
    finally:
        db.close()

# API stats endpoint
@app.get("/api/stats")
async def get_stats(request: Request):
    if request.cookies.get("admin_session") != "authenticated":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db_session()
    try:
        return {
            "total_sessions": db.query(SessionLog).count(),
            "total_matches": db.query(MatchLog).count(),
            "active_sessions": db.query(SessionLog).filter(SessionLog.disconnected_at == None).count()
        }
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
