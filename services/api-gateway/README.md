# API Gateway

This is the main entry point for everything in StrangerSync. All client requests hit this first and then get routed to the right microservice.

## Port: 8000

## What it does

- Routes incoming requests to the appropriate service (user, matching, signaling, admin)
- Serves the static frontend files (html, css, js)
- Health monitoring - checks if other services are alive
- Aggregates stats from all services into one response

## Routes it handles

**Admin stuff:**
- `/admin` → proxied to Admin Service
- `/admin/dashboard` → proxied to Admin Service  
- `/api/stats` → proxied to Admin Service

**User stuff:**
- `POST /api/users` → creates user via User Service
- `GET /api/users/{token}` → gets user info
- `GET /api/users/active/list` → list of online users

**Matching:**  
- `POST /api/match/find` → find a match via Matching Service
- `POST /api/match/leave` → leave current match
- `GET /api/match/stats` → matching stats

**Other:**
- `GET /health` → health status of gateway + all services
- `GET /api/system/stats` → aggregated stats from everything
- `WS /ws` → WebSocket endpoint (redirects to signaling service)

## How routing works

The gateway uses httpx to make async http calls to other services. Service URLs come from environment variables so easy to configure.

```
Client Request → API Gateway → [Admin/User/Matching/Signaling] Service
                     ↓
               Response back
```

basically acts as a reverse proxy that knows where to send stuff.
