# AI-Powered Airport Weather Crisis Management System

Airport Operations Control Center (AOCC) dashboard for monitoring airport weather, classifying operational crisis levels, generating weather alerts, assessing operational impact, and supporting AOCC decision-making.

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
│   ├── main.py                 # FastAPI app (static + templates + APIs)
│   ├── config.py               # Settings from .env
│   ├── weather.py              # Mock + Tomorrow.io providers
│   ├── severity.py             # Operational severity Levels 1–3
│   ├── alert_engine.py         # Phase 4 weather alert evaluation
│   ├── rag.py                  # RAG placeholders
│   ├── schemas.py / models.py
│   ├── routes/                 # HTTP routers
│   └── services/               # weather, severity, alert, impact, notification, rag
├── frontend/
│   ├── templates/index.html
│   └── static/{css,js,images}
├── documents/ uploads/ vectorstore/
├── .env
├── requirements.txt
└── README.md
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | AOCC dashboard |
| GET | `/health` | Health check |
| GET | `/api/weather` | Live airport weather (Tomorrow.io / mock failover) |
| GET | `/api/severity` | Operational severity Level 1–3 |
| GET | `/api/alerts/current` | Current weather alert + checklist + trends |
| GET | `/api/alerts/history` | Runtime alert history (newest first) |
| GET | `/api/operations/impact` | AOCC operational impact assessment |
| GET | `/api/notifications` | Notification timeline (newest first) |
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

## Phase 4 — Weather Alert & Incident Management

### Architecture

```
Live Weather (Tomorrow.io)
        │
        ▼
 AlertService ──► Alert Engine (NORMAL / WATCH / WARNING / CRITICAL)
        │
        ├──► NotificationService (timeline feed)
        ├──► Alert History (in-memory, session runtime)
        └──► ImpactService (arrivals / runway / ground / passengers)
```

### Alert Engine

Evaluates **live** observation fields:

- Visibility, Temperature, Wind Speed, Rainfall, Humidity, Weather Description
- Condition detectors: Fog, Thunderstorm, Heavy Rain, Strong Wind, Heat

Each alert includes: Title, Description, Severity, Affected Operations, Recommended AOCC Action, Checklist, Timestamp, Status (`ACTIVE` / `CLEARED`).

### Operational Impact Logic

Maps the primary alert severity (and refined weather thresholds) to statuses such as:

- Arrival / Departure: `NORMAL` · `MONITOR` · `REDUCED` · `SEVERELY REDUCED`
- Runway: `OPEN` · `LIMITED` · `TEMPORARILY RESTRICTED`
- Taxiway / Ground / Passenger processing impact labels

### Dashboard Phase 4 panels

- Active Weather Alert card (animated, color-coded)
- Operational Impact panel
- Structured AOCC action checklist
- Notification feed
- Weather trend indicators (vs previous observation)
- Alert history table

Weather auto-refresh remains **every 30 minutes** (`WEATHER_REFRESH_INTERVAL`).

## Configuration (`.env`)

| Variable | Purpose |
|----------|---------|
| `HOST` | Bind host |
| `PORT` | Bind port (default `8000`) |
| `DEBUG` | Debug mode |
| `WEATHER_API_KEY` | Tomorrow.io API key |
| `GEMINI_API_KEY` | Reserved for Google Gemini |
| `WEATHER_PROVIDER` | `tomorrow` or `mock` |
| `CHAT_PROVIDER` | `mock` (default) |

## Airport defaults

- **ICAO:** VIDP  
- **IATA:** DEL  
- **Name:** Indira Gandhi International Airport  
- **Location:** New Delhi, India  

## License

Prototype for educational / operational demonstration use.
