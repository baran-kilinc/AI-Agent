# AI-Chatbot-Prototyp

Dies ist eine minimale, produktionsnahe Web-App für einen AI-Chatbot. Sie stellt eine statische HTML-Oberfläche bereit und spricht mit der BMW LLM API.

## Voraussetzungen

- Python 3.10+
- (Optional) Docker + Docker Compose

## Datenbankvorbereitunh
```bash
pip install chromadb sentence-transformers
python prepare_aida_stream.py
python create_vector_db.py
```
ADIAROHDATA.json > prepare_aida_stream.py > AIDADATA.jsonl
AIDADATA.jsonl > create_vector_db.py > my_local_vectordb

## Setup (lokal, ohne Docker)

1. Virtuelle Umgebung erstellen und aktivieren:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
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
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]*?)\s*=\s*(.+?)\s*$') {
        $name = $matches[1]
        $value = $matches[2].Trim('"').Trim("'")
        Set-Item -Path "env:$name" -Value $value
    }
}
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
| `RAG_ENABLED` | Aktiviert ChromaDB-Retrieval (Standard: `true`) |
| `CHROMA_DB_PATH` | Pfad zur persistenten ChromaDB (Standard: `./my_local_vectordb`) |
| `CHROMA_COLLECTION_NAME` | Chroma Collection Name (Standard: `aida_knowledge_base`) |
| `CHROMA_EMBEDDING_MODEL` | Embedding-Modell für Query-Vektoren (Standard: `sentence-transformers/all-MiniLM-L6-v2`) |
| `RAG_TOP_K` | Anzahl abgerufener Dokumente pro Frage (Standard: `4`) |
| `RAG_MAX_CONTEXT_CHARS` | Max. Zeichenanzahl für RAG-Kontext im Prompt (Standard: `5000`) |

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

## RAG mit lokaler ChromaDB

Die API verbindet sich beim Start automatisch mit deiner lokalen ChromaDB, wenn `RAG_ENABLED=true` ist und der Pfad existiert. Für deine Datenbasis sollten diese Werte gesetzt sein:

```bash
export CHROMA_DB_PATH=./my_local_vectordb
export CHROMA_COLLECTION_NAME=aida_knowledge_base
export CHROMA_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

Der Retriever injiziert die Top-Treffer als zusätzlichen System-Context. Antworten werden damit auf den gefundenen Wissenskontext begrenzt; wenn nichts Passendes gefunden wird, soll das Modell transparent auf fehlenden Kontext hinweisen.
