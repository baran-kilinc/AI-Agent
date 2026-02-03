# AI-Chatbot-Prototyp

Dies ist eine minimale, produktionsnahe Web-App für einen AI-Chatbot. Sie stellt eine statische HTML-Oberfläche bereit und spricht mit der BMW LLM API.

## Voraussetzungen

- Python 3.10+
- (Optional) Docker + Docker Compose

## Setup (lokal, ohne Docker)

1. Virtuelle Umgebung erstellen und aktivieren:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

3. Environment-Template kopieren und deine BMW-Zugangsdaten eintragen:

```bash
cp .env.example .env
```

4. Environment-Variablen laden (oder im Shell-Profil setzen):

```bash
set -a
source .env
set +a
```

5. App starten:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8080 --reload
```

6. UI im Browser öffnen:

```
http://localhost:8080
```

## Setup (Docker)

1. Environment-Template kopieren und deine BMW-Zugangsdaten eintragen:

```bash
cp .env.example .env
```

2. App starten:

```bash
docker compose up --build
```

3. UI im Browser öffnen:

```
http://localhost:8080
```

## Umgebungsvariablen

| Variable | Beschreibung |
| --- | --- |
| `BMW_API_URL` | BMW LLM API URL (Standard: `https://api.gcp.cloud.bmw/llmapi/v1/chat/completions`) |
| `BMW_API_TOKEN` | BMW API Token |
| `BMW_CLIENT_ID` | BMW Client ID (als `x-apikey` genutzt) |
| `BMW_MODEL` | Modellname (Standard: `openai/gpt-4o`) |
| `BMW_CERT_FILE` | Pfad zu BMW Trusted Certificates PEM (Standard: `BMW_Trusted_Certificates_Latest.pem`) |
| `SYSTEM_PROMPT` | Optionales Override für den System-Prompt |
| `SYSTEM_PROMPT_PATH` | Optionaler Pfad zu einer Prompt-Datei (Standard: `system_prompt.txt`) |
| `SESSION_TTL_SECONDS` | Session-TTL in Sekunden (Standard: 1800) |
| `MAX_MESSAGES` | Maximale Anzahl Chat-History Nachrichten (Standard: 20) |
| `MAX_BODY_BYTES` | Request-Body-Limit (Standard: 1048576) |
| `CORS_ORIGINS` | Komma-separierte Liste erlaubter Origins |

## Projektstruktur

```
/app
  backend/
    main.py
    bmw_client.py
    session_store.py
  static/
    index.html
    (images)
  system_prompt.txt
  Dockerfile
  docker-compose.yml
  .env.example
```
