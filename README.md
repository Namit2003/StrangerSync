# StrangerSync 🎥

A random video chat application (like Omegle) built using **microservices architecture**.

This project was made as a **Final Assignment** for my undergraduate course **"Microservice Architecture and Programming"** at university.

## Live Demo

Deployed app: [StrangerSync](https://strangersync-production.up.railway.app/)

## what is this?

So basically its a peer-to-peer video chat app where you can connect with random strangers. The whole point was to learn microservices so I broke down this app into multiple services that talk to each other.

## Architecture Overview

Here's how everything connects together:

```
                    ┌─────────────────────┐
                    │   API Gateway       │
                    │      :8000          │
                    └──────────┬──────────┘
                               │
        ┌──────────────────────┼─────────────────────┐
        │                      │                     │
   ┌────▼────┐          ┌──────▼──────┐      ┌──────▼──────┐
   │ Admin   │          │  Signaling  │      │  Matching   │
   │  :8003  │          │    :8001    │      │    :8002    │
   └────┬────┘          └──────┬──────┘      └──────┬──────┘
        │                      │                     │
        └──────────────────────┼─────────────────────┘
                               │
                        ┌──────▼──────┐
                        │    User     │
                        │   :8004     │
                        └──────┬──────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         │                     │                     │
    ┌────▼─────┐         ┌─────▼─────┐       ┌──────▼──────┐
    │PostgreSQL│         │   Redis   │       │   Static    │
    │  :5432   │         │   :6379   │       │   Files     │
    └──────────┘         └───────────┘       └─────────────┘
```

## The Microservices

So we have 5 main microservices:

### 1. API Gateway (Port 8000)
The main entry point for everything. All requests go through here first and then it routes them to the right service. Also does health checks on other services and aggregates stats from everywhere.

### 2. User Service (Port 8004)
Handles anything related to user sessions - creating users, tracking who's online, who disconnected etc. Uses Redis for caching active users so its fast.

### 3. Matching Service (Port 8002)  
This is where the magic happens for pairing random users together. Has a waiting queue in Redis and a matching algorithm. When 2 people are looking for a match, it pairs them up.

### 4. Signaling Service (Port 8001)
Manages all the WebSocket connections for real-time stuff. Also handles WebRTC signaling - basically relays the offer/answer/ICE candidates between peers so they can establish a video connection.

### 5. Admin Service (Port 8003)
A simple admin dashboard to see whats going on - how many sessions, how many matches, etc. Has login authentication too.

## Tech Stack

- **FastAPI** - Python web framework for all the services
- **PostgreSQL** - Database (using shared database pattern for simplicity)
- **Redis** - For caching and pub/sub messaging between services  
- **WebSockets** - Real-time communication
- **WebRTC** - Peer to peer video/audio
- **Docker & Docker Compose** - Containerization

## Microservice Patterns I Used

These are the patterns I learned in class and implemented here:

- **API Gateway Pattern** - single entry point that routes to services
- **Event-Driven Architecture** - services communicate via Redis pub/sub
- **Shared Database** - all services share same postgres db (easier for learning)
- **Service Discovery** - services find each other via environment variables

## Project Structure

```
StrangerSync/
├── services/
│   ├── shared/              # Shared code between services
│   │   ├── database.py      # DB models & connection
│   │   └── utils.py         # Helper functions
│   ├── api-gateway/         # Port 8000
│   ├── admin-service/       # Port 8003
│   ├── matching-service/    # Port 8002
│   ├── signaling-service/   # Port 8001
│   └── user-service/        # Port 8004
├── app/                     # Frontend application
│   ├── templates/           # HTML templates
│   └── main.py              
├── static/                  # CSS, JS files
├── docker-compose.yml       # All services containerized
└── README.md
```

## How It Works

1. User opens the app → goes through API Gateway
2. API Gateway creates a user session via User Service
3. User clicks "Find Match" → Signaling Service talks to Matching Service
4. Matching Service puts them in queue, finds another waiting user, pairs them up
5. Both users get notified through WebSocket
6. WebRTC signaling happens through Signaling Service
7. Direct peer-to-peer video connection established!

## Features

- Random stranger matching
- Video and audio chat (peer to peer)
- Text chat too
- Camera flip (front/back)
- Mute/unmute
- Admin dashboard with stats
- Health monitoring for all services

---

Made for my Microservices class project 🎓
