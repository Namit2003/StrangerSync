# User Service

Handles everything related to user sessions - creating them, tracking who's online, disconnections, etc.

## Port: 8004

## What it does

- Creates new user sessions when someone connects
- Tracks active users in Redis (super fast lookups)
- Falls back to database if Redis is down
- Publishes events when users connect/disconnect (event-driven!)

## Endpoints

- `POST /users` - create a new user session (called when someone opens the app)
- `GET /users/{token}` - get info about a specific user
- `POST /users/{token}/disconnect` - mark user as disconnected
- `GET /users/active/list` - get list of all online users
- `GET /users/count` - just the counts (active users, total sessions)
- `GET /health` - health check

## How it works with other services

Signaling Service calls this when someone connects via websocket. Also publishes events to Redis so other services can react to user connects/disconnects.

```
Signaling Service ──connects──→ User Service ──saves──→ PostgreSQL
                                     │
                                     └──caches──→ Redis (active_users set)
```

## Tech used

- PostgreSQL for persistent storage of session logs
- Redis for caching active users (using SET data structure)
- Redis pub/sub for publishing user events

The Redis caching makes it fast to check who's online without hitting the database every time.
