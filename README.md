# StrangerSync 🎥

A random video chat application (like Omegle) built using **microservices architecture**.

This project was made as a **Final Assignment** for my undergraduate course **"Microservice Architecture and Programming"** at university.

## Live Demo

Deployed on Fly.io: [StrangerSync](https://strangersync-core.fly.dev)

## what is this?

So basically its a peer-to-peer video chat app where you can connect with random strangers. The whole point was to learn microservices so I broke down this app into multiple services that talk to each other.

## Architecture Overview

Here's how everything connects together:

```
Browser
  │
  ▼
Fly.io Proxy (HTTPS/WSS)
  │
  ├── /ws  ──────────────────▶ signaling-service  (WebSocket + Matching)
  └── /*   ──────────────────▶ core-service        (Static files + User API)
                                      │
                               ┌──────▼──────┐
                               │  PostgreSQL  │
                               │  (Fly.io)    │
                               └─────────────┘
```

## The Services

Ended up with 2 main services after merging some stuff together:

### 1. Signaling Service
The most important one. Handles all WebSocket connections, WebRTC signaling (offer/answer/ICE candidates) AND the matching queue. When someone clicks find match it puts them in a queue and pairs them with the next person who also clicks it. All in memory with a single machine so the queue stays consistent.

### 2. Core Service
Serves the frontend (HTML/CSS/JS) and handles user session tracking in the database. Also has a `/config.js` endpoint that tells the frontend where the signaling service is so the WebSocket connects to the right place.

## Tech Stack

- **FastAPI** - Python web framework for both services
- **PostgreSQL** - Database for session and match logs
- **WebSockets** - Real-time communication
- **WebRTC** - Peer to peer video/audio
- **Fly.io** - Deployment (2 machines, fits in free tier)

## Microservice Patterns I Used

These are the patterns I learned in class and implemented here:

- **Service Decomposition** - split by business capability (real-time vs HTTP)
- **Shared Database** - both services share same postgres db (easier for learning)
- **API Gateway Pattern** - core service acts as the HTTP entry point
- **Config as a Service** - `/config.js` endpoint for dynamic frontend config

## Project Structure

```
StrangerSync/
├── services/
│   ├── shared/                  # Shared DB models between services
│   │   ├── database.py          # DB models & connection
│   │   └── utils.py             # Helper functions
│   ├── signaling-service/       # WebSocket + WebRTC + Matching
│   └── core-service/            # Static files + User session API
├── static/                      # Frontend (HTML, CSS, JS)
├── fly-signaling.toml           # Fly.io config for signaling
├── fly-core.toml                # Fly.io config for core
└── README.md
```

## How It Works

1. User opens the app → core service serves the HTML
2. Browser loads `/config.js` → gets the signaling service WebSocket URL
3. Browser connects WebSocket to signaling service
4. User clicks "Find Match" → signaling service puts them in queue
5. Next person who also clicks gets paired with them
6. Both users get notified, WebRTC signaling happens through the same WebSocket connection
7. Direct peer-to-peer video connection established!

## Features

- Random stranger matching
- Video and audio chat (peer to peer)
- Text chat
- Camera flip (front/back)
- Mute/unmute

## Deploying

Two separate Fly.io apps. Deploy signaling first since core needs its URL:

```bash
fly deploy --config fly-signaling.toml
fly secrets set SIGNALING_WS_URL=wss://strangersync-signaling.fly.dev/ws --app strangersync-core
fly deploy --config fly-core.toml
```

---

Made for my Microservices class project 🎓
