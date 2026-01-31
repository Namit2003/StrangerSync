# Signaling Service

Handles all the real-time WebSocket stuff and WebRTC signaling between peers.

## Port: 8001

## What it does

- Manages WebSocket connections for each user
- Coordinates with Matching Service to pair users
- Relays WebRTC signals (offer, answer, ICE candidates) between matched peers
- Forwards chat messages between matched users

## WebSocket Endpoint

Connect at: `ws://localhost:8001/ws?token={user_id}`

If you dont provide a token it generates one for you.

## Messages between client and server

**Client sends:**
```json
{"action": "find_match"}           // start looking for someone
{"action": "leave_match"}          // disconnect from current match
{"action": "chat", "msg": "hi!"}   // send chat message to peer
{"action": "signal", "signal_type": "offer", "signal_data": {...}}  // WebRTC signaling
```

**Server sends:**
```json
{"status": "identity", "user_id": "..."}                    // your assigned id
{"status": "waiting", "msg": "Looking for someone..."}      // in queue
{"status": "matched", "peer_id": "...", "match_id": "..."}  // found a match!
{"status": "chat", "msg": "...", "sender": "peer"}          // incoming chat
{"status": "signal", "signal_type": "...", "signal_data": {...}}  // WebRTC from peer
{"status": "peer_left"}                                      // partner disconnected
```

## How it works with other services

```
Client ←──WebSocket──→ Signaling Service ──HTTP──→ Matching Service
                              │
                              └──HTTP──→ User Service (on connect/disconnect)
```

The signaling service is like the "hub" for real-time communication. It talks to:
- **User Service** - to register when someone connects/disconnects
- **Matching Service** - to request matches and handle leave

## WebRTC SIgnaling Flow

When two users are matched:
1. Both get notified they're matched (one is "initiator")
2. Initiator creates WebRTC offer, sends via this service
3. Service relays offer to the other peer
4. Other peer creates answer, sends back
5. ICE candidates get exchanged same way
6. Direct peer-to-peer video connection established!

This service doesnt touch the actual video data - thats all peer-to-peer once signaling is done.
