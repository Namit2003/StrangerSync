from fastapi import APIRouter, Depends, HTTPException, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from app.database import SessionLocal
import os

# --- CONFIGURATION ---
ADMIN_USERNAME = "king-god"
ADMIN_PASSWORD = "TumareBasKiBaatNai-07" 
# ---------------------

router = APIRouter(prefix="/hero")
templates = Jinja2Templates(directory="app/templates")

# Dependency: Check if user has the admin cookie
def is_authenticated(request: Request):
    token = request.cookies.get("admin_token")
    if token == "logged_in_secret_value":
        return True
    return False

# 1. Login Page
@router.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})

# 2. Handle Login Submission
@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/hero/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        # Set a simple cookie (In production, use JWT, but this works for simple needs)
        response.set_cookie(key="admin_token", value="logged_in_secret_value")
        return response
    else:
        return templates.TemplateResponse("admin_login.html", {
            "request": request, 
            "error": "Invalid Credentials"
        })

# 3. Logout
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/hero", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("admin_token")
    return response

# 4. Dashboard (View Tables)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_authenticated(request):
        return RedirectResponse(url="/hero")

    db = SessionLocal()
    
    # Fetch Data
    sessions = db.execute(text("SELECT * FROM sessions ORDER BY id DESC LIMIT 50")).fetchall()
    matches = db.execute(text("SELECT * FROM matches ORDER BY id DESC LIMIT 50")).fetchall()
    
    db.close()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "sessions": sessions,
        "matches": matches,
        "query_result": None,
        "last_query": ""
    })

# 5. Run Custom SQL Query
@router.post("/query", response_class=HTMLResponse)
async def run_query(request: Request, sql_query: str = Form(...)):
    if not is_authenticated(request):
        return RedirectResponse(url="/hero")

    db = SessionLocal()
    sessions = db.execute(text("SELECT * FROM sessions ORDER BY id DESC LIMIT 10")).fetchall()
    matches = db.execute(text("SELECT * FROM matches ORDER BY id DESC LIMIT 10")).fetchall()
    
    query_result = None
    error_msg = None
    columns = []

    try:
        # Execute the raw SQL
        result = db.execute(text(sql_query))
        
        # If it's a SELECT statement, fetch results
        if result.returns_rows:
            query_result = result.fetchall()
            columns = result.keys() # Get column names
        else:
            db.commit() # Commit updates/deletes
            error_msg = f"Query executed successfully. Rows affected: {result.rowcount}"

    except Exception as e:
        error_msg = str(e)
    finally:
        db.close()

    return templates.TemplateResponse("admin_dashboard.html", {
        "request": request,
        "sessions": sessions,
        "matches": matches,
        "query_result": query_result,
        "query_columns": columns,
        "query_error": error_msg,
        "last_query": sql_query
    })