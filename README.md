# AI Chatbot Prototype

This is a minimal, production-lean AI chatbot web app that serves a static HTML UI and talks to a GAIA-compatible LLM API.

## Requirements

- Docker + Docker Compose

## Setup

1. Copy the environment template and fill in your GAIA credentials:

```bash
cp .env.example .env
```

2. Start the app:

```bash
docker compose up --build
```

3. Open the UI:

```
http://localhost:8080
```

## Environment Variables

| Variable | Description |
| --- | --- |
| `GAIA_BASE_URL` | Base URL for the GAIA API (e.g. `https://api.example.com`) |
| `GAIA_API_KEY` | API key for GAIA |
| `GAIA_MODEL` | Model name |
| `SYSTEM_PROMPT` | Optional override for the system prompt |
| `SYSTEM_PROMPT_PATH` | Optional path to a prompt file (defaults to `system_prompt.txt`) |
| `SESSION_TTL_SECONDS` | Session TTL in seconds (default 1800) |
| `MAX_MESSAGES` | Max chat history messages (default 20) |
| `MAX_BODY_BYTES` | Request body limit (default 1048576) |
| `CORS_ORIGINS` | Comma-separated list of allowed origins |

## Project Structure

```
/app
  backend/
    main.py
    gaia_client.py
    session_store.py
  static/
    index.html
    (images)
  system_prompt.txt
  Dockerfile
  docker-compose.yml
  .env.example
```
