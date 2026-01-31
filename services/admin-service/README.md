# Admin Service

A simple admin dashboard to monitor whats going on in the system.

## Port: 8003

## What it does

- Login page with username/password auth
- Dashboard showing stats (sessions, matches, active users)
- API endpoint for getting stats as JSON

## Endpoints

- `GET /admin` - login page
- `POST /admin/login` - authenticate
- `GET /admin/dashboard` - the main dashboard with all the numbers
- `GET /api/stats` - JSON stats (needs to be logged in)
- `GET /health` - health check

## Authentication

Super basic cookie-based auth. When you login successfully it sets a cookie `admin_session=authenticated` and checks that on protected routes.

Login creds come from environment variables (ADMIN_USERNAME, ADMIN_PASSWORD).

## Dashboard shows

- Total sessions ever created
- Total matches made
- Currently active sessions

Just queries the PostgreSQL database directly using the shared database models.

## Architecture

```
Admin Dashboard (browser)
        ↓
  Admin Service ──queries──→ PostgreSQL
        │
        └──reads──→ SessionLog, MatchLog tables
```

This service is independent and doesnt need to talk to other microservices - just reads from the shared database.
