# AI-Powered Airport Weather Crisis Management System

Airport Operations Control Center (AOCC) dashboard for monitoring airport weather, classifying operational crisis levels, and receiving AI operational recommendations.

This is **not** a consumer weather app. It is a single FastAPI application that serves both the APIs and the dashboard UI.

## Quick start

```bash
# From the project root
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
# source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open **http://localhost:8000**

API docs:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health: http://localhost:8000/health

## Project structure

```
weather-crisis-management/
├── backend/
│   ├── main.py              # FastAPI app (static + templates + APIs)
│   ├── config.py            # Settings from .env
│   ├── weather.py           # Weather providers (mock / Tomorrow.io stub)
│   ├── severity.py          # Operational severity engine
│   ├── rag.py               # RAG placeholders only
│   ├── schemas.py           # API envelopes & request models
│   ├── models.py            # Domain models
│   ├── routes/              # HTTP routers
│   └── services/            # Business orchestration
├── frontend/
│   ├── templates/index.html
│   └── static/{css,js,images}
├── documents/               # Future SOP corpus
├── uploads/                 # Uploaded docs (not indexed yet)
├── vectorstore/             # Future FAISS index
├── .env
├── requirements.txt
└── README.md
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | AOCC dashboard |
| GET | `/health` | Health check |
| GET | `/api/weather` | Current airport weather (mock) |
| GET | `/api/severity` | Operational severity Level 1–3 |
| POST | `/api/chat` | AOCC AI assistant (mock) |
| POST | `/api/upload` | Store document for future RAG |

Every API response uses:

```json
{
  "success": true,
  "message": "Success",
  "data": {}
}
```

## Configuration (`.env`)

| Variable | Purpose |
|----------|---------|
| `HOST` | Bind host (default `0.0.0.0`) |
| `PORT` | Bind port (default `8000`) |
| `DEBUG` | Debug / reload friendly mode |
| `WEATHER_API_KEY` | Reserved for Tomorrow.io |
| `GEMINI_API_KEY` | Reserved for Google Gemini |
| `WEATHER_PROVIDER` | `mock` (default) |
| `CHAT_PROVIDER` | `mock` (default) |

## Phase 1 scope

- Mock weather for **Delhi IGI Airport (VIDP)**
- Severity engine Levels **1 / 2 / 3**
- Mock AOCC chatbot
- RAG folders + interfaces only (no embeddings / FAISS / LLM)

## Future integration points

1. **Tomorrow.io** — implement `TomorrowIOWeatherProvider` in `backend/weather.py` and set `WEATHER_PROVIDER=tomorrow_io`. Frontend unchanged.
2. **Gemini + LangChain** — replace `MockChatProvider` in `backend/services/rag_service.py` and set `CHAT_PROVIDER=gemini`.
3. **RAG** — implement ingest/search in `backend/rag.py` using Sentence Transformers + FAISS under `vectorstore/`.

## Airport defaults

- **ICAO:** VIDP  
- **IATA:** DEL  
- **Name:** Indira Gandhi International Airport  
- **Location:** New Delhi, India  

## License

Prototype for educational / operational demonstration use.
