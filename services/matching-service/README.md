# Matching Service

This is the core service that pairs random users together. When you click "Find Match" this is what handles it.

## Port: 8002

## What it does

- Maintains a waiting queue of users looking for a match
- Random pairing algorithm - picks someone from queue and matches them
- Tracks active matches
- Has fallback to in-memory queue if Redis is down

## Endpoints

- `POST /match/find` - try to find a match for a user
- `POST /match/leave` - leave current match OR waiting queue
- `GET /match/status/{token}` - check if user is matched and with who
- `GET /match/stats` - stats about queue size, active matches etc
- `GET /health` - health check

## How matching works

Pretty simple actually:

1. User A requests a match
2. Check if anyone is already waiting in queue
3. If yes → pair User A with that person, remove from queue
4. If no → add User A to queue, tell them to wait
5. When User B comes along → same thing, but now User A is waiting so they get matched!

```
User A ──find_match──→ Queue empty? ──NO──→ Match with User B!
                              │
                              YES
                              ↓
                      Add to queue, wait...
```

## Redis stuff

Uses Redis LIST for the queue because its distributed. If Redis is down, falls back to a Python list in memory (not great for scaling but works for development).

Also stores active matches in Redis so we can look them up quick.

## Events

Publishes "match_created" and "match_ended" events to Redis pub/sub so other services know when matches happen.
