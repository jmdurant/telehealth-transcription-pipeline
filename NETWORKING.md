# Network Architecture

This document describes the Docker network architecture for the Telehealth Transcription Pipeline and its integration with the broader telehealth ecosystem.

## Overview

The system uses three primary Docker networks to organize container communication:

```
                              INTERNET / BROWSER
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         NPM (Nginx Proxy Manager)                       │
│                           External Gateway                              │
│                              :80 / :443                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   vc.localhost        →  Telesalud Web                                  │
│   notes.localhost     →  OpenEMR                                        │
│   vcbknd.localhost    →  Jitsi Web                                      │
│   realtime.localhost  →  Realtime Assistant (WebSocket)                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                    (routes to containers by domain)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    frontend-official-production                         │
│                    (Internal Service Network)                           │
│                                                                         │
│   Telesalud ←→ Parakeet ←→ Ollama ←→ Pipeline ←→ OpenEMR               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                    (bridge to shared resources)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       official-shared-network                           │
│                       (Jitsi Access Layer)                              │
│                                                                         │
│                    Prosody / JVB / Recorder / etc                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Network Descriptions

### 1. NPM (Nginx Proxy Manager)

**Purpose:** External gateway for browser/internet access

NPM routes external HTTP/HTTPS requests to internal containers based on domain names. It handles SSL termination and provides a single entry point for all web-accessible services.

**Services requiring NPM routes:**
| Domain | Service | Reason |
|--------|---------|--------|
| `vc.localhost` | Telesalud | Users access the telehealth app |
| `notes.localhost` | OpenEMR | Doctors access the EMR |
| `vcbknd.localhost` | Jitsi Web | Video calls in browser |
| `realtime.localhost` | Realtime Assistant | Browser WebSocket connection |

**Services NOT requiring NPM routes:**
| Service | Reason |
|---------|--------|
| Pipeline (Webhook) | Only called internally by Telesalud backend |
| Parakeet ASR | Only called internally by Pipeline/Realtime |
| Ollama LLM | Only called internally by Pipeline |

### 2. frontend-official-production

**Purpose:** Main internal service-to-service communication

This is the primary network where application services communicate with each other. All services that need to talk to each other directly (not through NPM) should be on this network.

**Containers on this network:**
- `official-production-telehealth-web-1` (Telesalud)
- `official-production-telehealth-app-1` (Telesalud App)
- `official-production-telehealth-database-1`
- `official-production-transcription-pipeline`
- `official-production-realtime-assistant`
- `official-production-parakeet-asr-parakeet-asr`
- `official-production-ollama-llm`
- `official-production-openemr-1`
- `official-production-mysql-1`
- `official-production-proxy-proxy-1` (NPM)

### 3. official-shared-network

**Purpose:** Multi-tenant bridge to Jitsi resources

This network allows multiple environments (production, staging, testing) to share a single Jitsi stack. It's the "bar" where different projects can access Jitsi resources.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        official-shared-network                          │
│                         (Jitsi Access Layer)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │  PRODUCTION │    │   STAGING   │    │   TESTING   │                │
│   │  Telesalud  │    │  Telesalud  │    │  Telesalud  │                │
│   │  Pipeline   │    │  Pipeline   │    │  Pipeline   │                │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │
│          │                  │                  │                        │
│          └──────────────────┼──────────────────┘                        │
│                             ▼                                           │
│                    ┌─────────────────┐                                  │
│                    │      JITSI      │                                  │
│                    │  (Single Stack) │                                  │
│                    │  Prosody, JVB,  │                                  │
│                    │  Recorder, etc  │                                  │
│                    └─────────────────┘                                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**Containers on this network:**
- All Jitsi components (prosody, jvb, jicofo, jibri, jigasi, coturn, web, multitrack_recorder)
- `official-production-telehealth-web-1`
- `official-production-telehealth-app-1`
- `official-production-transcription-pipeline`
- `official-production-realtime-assistant`
- `official-production-openemr-1`
- `official-production-proxy-proxy-1`

### 4. jitsi-docker_meet.jitsi

**Purpose:** Internal Jitsi component communication

This is Jitsi's internal network for its components to communicate with each other. External services don't need to be on this network - they access Jitsi through `official-shared-network`.

## Service Communication Matrix

### Pipeline Service

| Destination | Network | Port | Purpose |
|-------------|---------|------|---------|
| Parakeet ASR | frontend-official-production | 8000 | Audio transcription |
| Ollama LLM | frontend-official-production | 11434 | Clinical summarization |
| Telesalud | frontend-official-production | 80 | API callbacks |
| OpenEMR | frontend-official-production | 80 | Send clinical notes |
| Prosody | official-shared-network | 5280 | Event sync, room metadata |
| Multitrack Recorder | official-shared-network | 8989 | Recording triggers |

### Realtime Assistant Service

| Destination | Network | Port | Purpose |
|-------------|---------|------|---------|
| Parakeet ASR | frontend-official-production | 8000 | Live transcription |
| Telesalud | frontend-official-production | 80 | API calls |

### Telesalud Service

| Destination | Network | Port | Purpose |
|-------------|---------|------|---------|
| Pipeline | frontend-official-production | 9091 | Webhook triggers |
| Realtime | frontend-official-production | 9093 | Health checks |
| Prosody | official-shared-network | 5280 | Room management |
| Jitsi Web | official-shared-network | - | Video integration |

## Configuration

### Environment Variables

```bash
# Network names (in .env)
DOCKER_NETWORK=frontend-official-production
SHARED_NETWORK=official-shared-network
```

### docker-compose.yml Network Definition

```yaml
networks:
  frontend:
    name: ${DOCKER_NETWORK:-frontend-official-production}
    external: true
  shared:
    name: ${SHARED_NETWORK:-official-shared-network}
    external: true
```

### Service Network Assignment

```yaml
services:
  transcription-pipeline:
    networks:
      - frontend
      - shared
  
  realtime-assistant:
    networks:
      - frontend
      - shared
```

## Why NPM Doesn't Replace Docker Networks

A common question: "If NPM is on all networks, why can't services just route through it?"

**NPM only handles external HTTP routing by domain.** It doesn't:
- Provide DNS resolution between containers
- Allow direct TCP/WebSocket connections between containers
- Route internal service-to-service traffic

Containers need to be on the **same Docker network** to:
1. Resolve each other's names via Docker DNS
2. Establish direct TCP connections
3. Communicate without going through the proxy

```
# This works (same network):
pipeline → http://official-production-ollama-llm:11434

# This doesn't work (different networks, even with NPM):
pipeline → http://jitsi-docker-prosody-1:5280  ❌ (without shared network)
```

## Troubleshooting

### Check container networks
```bash
docker inspect <container> --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}'
```

### Test connectivity from a container
```bash
docker exec <container> curl -s http://<target>:<port>/
```

### List all containers on a network
```bash
docker network inspect <network> --format '{{range .Containers}}{{.Name}}{{"\n"}}{{end}}'
```

### Connect a container to a network manually
```bash
docker network connect <network> <container>
```

## Port Reference

| Service | Port | Protocol | Access |
|---------|------|----------|--------|
| Pipeline Webhook | 9091 | HTTP | Internal |
| Realtime WebSocket | 9092 | WS | External (via NPM) |
| Realtime Health | 9093 | HTTP | Internal |
| Parakeet ASR | 8000 | HTTP/WS | Internal |
| Ollama LLM | 11434 | HTTP | Internal |
| Prosody | 5280 | HTTP | Internal |
| Multitrack Recorder | 8989 | HTTP | Internal |
| Telesalud | 80 | HTTP | External (via NPM) |
| OpenEMR | 80 | HTTP | External (via NPM) |
| Jitsi Web | 80 | HTTP | External (via NPM) |
