# AirGuard AI

AirGuard AI is an AI-powered urban air quality intelligence platform for smart-city intervention teams. It turns air-quality readings, forecast validation, satellite evidence, geospatial context, source attribution, and human review workflows into a single municipal command-centre dashboard.

The current prototype is focused on Chennai and is designed for hackathon demonstration. The system helps city operators answer:

- What is the current pollution risk around the station?
- Which evidence supports the source hypothesis?
- Which preventive action should be prioritized?
- What must a human verify before dispatch?
- What citizen advisory can be published safely?

AirGuard AI is decision-support software. It does not automatically authorize enforcement, field dispatch, or public advisories without human review.

## Key Features

- FastAPI backend with integrated AirGuard evidence endpoints.
- Next.js App Router frontend built with TypeScript and Tailwind CSS.
- Premium command-centre dashboard with light and dark mode.
- Leaflet satellite map with station, roads, POIs, wind direction, ward boundary, and NO2 context.
- Executive summary, ground sensor snapshot, forecast validation, Sentinel-5P evidence, geospatial evidence, and source hypotheses.
- Groq supervisor decision display with reasoning summary and selected forecast method.
- Backend-owned intervention workflow:
  - Proposed
  - Under verification
  - Approved
  - Dispatched
  - In progress
  - Completed
  - Outcome recorded
  - Rejected

- Verification checklist that blocks approval until required human checks are complete.
- Citizen advisory workflow with English and Hindi advisory previews.
- Guardrails for safe claims, claims to avoid, and known limitations.
- Decision memo and analysis trace views for explainable demo storytelling.
- Backend validation prevents approval until field verification checks are complete.
- Citizen advisory preview and approval workflow.
- Analysis trace screen for explainable tool outputs.
- Decision memo screen for municipal reporting.
- Light/dark UI mode.
- Live OpenAQ pollutant refresh with Open-Meteo weather enrichment.
- Five-minute upstream cache, source-timestamp freshness checks, and labeled stale-data fallback.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Map | Leaflet, React Leaflet, Esri World Imagery tiles |
| Backend | FastAPI, Pydantic, Uvicorn |
| Data and ML support | Python, pandas, scikit-learn, geospatial and remote-sensing utilities |
| LLM support | Groq/OpenAI-compatible agent modules |

## Repository Structure

```text
airguard-ai/
  backend/
    app/
      api/routes_airguard.py       # AirGuard API and workflow commands
      main.py                      # FastAPI app entrypoint
      agents/                      # Supervisor, advisory, and memo agents
      tools/                       # AQI, forecast, evidence, and ranking tools
    data/sample/                   # Demo evidence payloads
  frontend/
    src/app/page.tsx               # Main command-centre dashboard
    src/components/CommandLeafletMap.tsx
    package.json
  ml/                              # ML configuration and support code
  scripts/                         # Utility scripts
  docs/
    architecture.md
    problem_statement.md
  requirements.txt
```

## Environment Variables

Create the frontend environment file:

```powershell
cd D:\airguard-ai\frontend
Copy-Item .env.example .env.local
```

Expected value:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

For deployment, set `NEXT_PUBLIC_API_BASE_URL` to the public URL of the deployed FastAPI backend.

Optional backend LLM variables may be needed if you enable live LLM calls instead of sample outputs:

```env
GROQ_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

## Local Setup

### 1. Clone the repository

```powershell
git clone https://github.com/Mrunali01/airguard-ai.git
cd airguard-ai
```

### 2. Create and activate Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Install frontend dependencies

```powershell
cd D:\airguard-ai\frontend
npm install
```

### 4. Configure frontend API base URL

```powershell
cd D:\airguard-ai\frontend
Copy-Item .env.example .env.local
```

Confirm `frontend/.env.local` contains:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Run Locally

Open two PowerShell terminals.

### Terminal 1: backend

```powershell
cd D:\airguard-ai
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Backend health and docs:

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/docs
```

### Terminal 2: frontend

```powershell
cd D:\airguard-ai\frontend
npm run dev -- --hostname 127.0.0.1
```

Open the dashboard:

```text
http://127.0.0.1:3000
```

## Main API Endpoints

```text
GET  /api/airguard/health
GET  /api/airguard/live
POST /api/airguard/live/refresh
POST /api/airguard/live/analyze
POST /api/airguard/live/agent
GET  /api/airguard/demo-output
GET  /api/airguard/cpcb-aqi
GET  /api/airguard/remote-sensing
GET  /api/airguard/intervention-workflows
POST /api/airguard/intervention-workflows/verification
POST /api/airguard/commands/request-verification
POST /api/airguard/commands/approve-intervention
POST /api/airguard/commands/reject-intervention
POST /api/airguard/commands/dispatch-intervention
POST /api/airguard/commands/start-intervention
POST /api/airguard/commands/complete-intervention
POST /api/airguard/commands/record-outcome
POST /api/airguard/commands/approve-advisory
POST /api/airguard/commands/regenerate-advisory
POST /api/airguard/commands/export-memo
```

## Demo Flow

1. Start the backend and frontend.
2. Open `http://127.0.0.1:3000`.
3. Show the Chennai command-centre header and real station pilot context.
4. Use the satellite command map to explain station, road, vulnerability, wind, and NO2 evidence.
5. Review the executive summary and ground sensor snapshot.
6. Walk through forecast validation and Sentinel-5P evidence.
7. Review source hypotheses and Groq supervisor decision.
8. Open the intervention workflow.
9. Click `Request Verification`.
10. Complete the field inspection, evidence confirmation, and ward engineer approval checks.
11. Click `Approve Intervention`.
12. Continue through `Dispatch`, `Start`, `Complete`, and `Record Outcome`.
13. Open Citizen Advisory and approve or regenerate the advisory.
14. Use the Reports/Memo section for final municipal decision context.

## Verification

Run these before final submission.

### Frontend

```powershell
cd D:\airguard-ai\frontend
npm run lint
npm run build
```

### Backend

```powershell
cd D:\airguard-ai
.\.venv\Scripts\python.exe -m compileall backend ml scripts
.\.venv\Scripts\python.exe -c "import backend.app.main; print('backend ok')"
```

### API smoke checks

Start the backend first, then run:

```powershell
curl.exe -L http://127.0.0.1:8000/api/airguard/health
curl.exe -L http://127.0.0.1:8000/api/airguard/demo-output
curl.exe -L http://127.0.0.1:8000/api/airguard/intervention-workflows
```

## Deployment

The project has two deployable services:

- Backend: FastAPI API
- Frontend: Next.js dashboard

Deploy the backend first so you have a public API URL for the frontend.

### Backend Deployment

You can deploy the FastAPI app on Render, Railway, Fly.io, Azure App Service, AWS, or any platform that supports Python web services.

Recommended service settings:

```text
Root directory: repository root
Runtime: Python
Install command: pip install -r requirements.txt
Start command: uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

If your platform does not provide `$PORT`, use the port value required by that platform.

After deployment, verify:

```text
https://your-backend-domain.example.com/
https://your-backend-domain.example.com/api/airguard/health
https://your-backend-domain.example.com/api/airguard/demo-output
```

### Frontend Deployment

The frontend can be deployed on Vercel, Netlify, or any Node hosting platform that supports Next.js.

Recommended Vercel settings:

```text
Root directory: frontend
Framework preset: Next.js
Install command: npm install
Build command: npm run build
Output: Next.js default
```

Set this environment variable in the frontend hosting platform:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain.example.com
```

Then deploy the frontend and open the generated production URL.

### Production Checklist

- Backend `/api/airguard/health` returns a success response.
- Backend `/api/airguard/demo-output` returns the integrated JSON payload.
- Frontend environment variable points to the deployed backend URL.
- Frontend production page loads without API errors.
- Satellite map loads. Browser internet access is required for Esri imagery tiles.
- Intervention buttons update status in order.
- Approval is blocked until all verification checks are complete.
- Citizen advisory buttons return successful backend responses.

## Known Demo Constraints

- The prototype currently uses Chennai sample evidence.
- Intervention workflow state is stored in memory for the demo. Restarting the backend resets workflow status.
- Satellite tiles are loaded from Esri online imagery.
- Some ML and agent outputs are sample-backed for stable hackathon presentation.
- The dashboard should be used for evidence-based decision support, not automatic enforcement.

## License

- `GET /api/airguard/live` loads live data when the cache is empty and otherwise serves the five-minute cache.
- The dashboard Refresh button calls `POST /api/airguard/live/refresh`. If no newer station measurement exists, the source timestamp and values may remain unchanged.
- `Run AirGuard Analysis` calls `POST /api/airguard/live/analyze` to evaluate current AQI, dispersion, source hypotheses, vulnerable receptors, and candidate interventions.
- `Run Groq Analysis` calls `POST /api/airguard/live/agent`: deterministic tools analyze the data first, then Groq synthesizes the verified evidence into an operational decision.
- Groq cannot override deterministic AQI, monitoring priority, immediate-intervention status, safe claims, or the allowed intervention set. Invalid actions and causal overclaims are repaired or removed.
- If Groq is unavailable or returns invalid JSON, the endpoint returns the deterministic live analysis with explicit fallback metadata.
- Live analysis does not recompute the 24-hour model forecast; the forecast panel remains explicitly labeled as historical benchmark context.
- Set `AIRGUARD_LIVE_CACHE_SECONDS` to change the default 300-second refresh cache. Use `POST /api/airguard/live/refresh?force=true` only for operator/debug use.
- If OpenAQ or Open-Meteo fails, the API returns the last successful live response or saved demo payload with `refresh_metadata.source_status=cached_fallback`.
- Live CPCB breakpoint AQI is a screening calculation from the latest available pollutants; regulatory AQI requires official averaging windows and validation.
- Leaflet satellite tiles use Esri online imagery, so the browser needs internet access for the satellite base layer.
- Workflow state is in-memory for the hackathon demo. Restarting the backend resets intervention workflow state.
- The system is decision-support only. AI recommendations do not automatically authorize enforcement or public publishing.
