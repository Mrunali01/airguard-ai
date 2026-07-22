# AirGuard AI

AirGuard AI is a smart-city air-quality command centre for Chennai. It combines ground sensor evidence, forecast validation, Sentinel-5P NO2 context, geospatial exposure, source hypotheses, human-reviewed interventions, citizen advisories, and municipal decision memo support.

## What Works

- FastAPI backend with demo evidence APIs.
- Next.js + TypeScript + Tailwind frontend.
- Leaflet satellite command map with station, POI, road, wind, ward, and NO2 overlays.
- Real station pilot status banner for OpenAQ station 2586.
- Intervention workflow with backend-owned state:
  - Proposed
  - Under verification
  - Approved
  - Dispatched
  - In progress
  - Completed
  - Outcome recorded
  - Rejected
- Backend validation prevents approval until field verification checks are complete.
- Citizen advisory preview and approval workflow.
- Analysis trace screen for explainable tool outputs.
- Decision memo screen for municipal reporting.
- Light/dark UI mode.
- Live OpenAQ pollutant refresh with Open-Meteo weather enrichment.
- Five-minute upstream cache, source-timestamp freshness checks, and labeled stale-data fallback.

## Run Locally

Open two PowerShell terminals.

Backend:

```powershell
cd D:\airguard-ai
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd D:\airguard-ai\frontend
npm run dev -- --hostname 127.0.0.1
```

Open:

```text
http://127.0.0.1:3000
```

Backend docs:

```text
http://127.0.0.1:8000/docs
```

## Environment

Frontend environment file:

```text
frontend/.env.local
```

Expected value:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Key API Endpoints

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

1. Open the command centre map.
2. Point out the `REAL STATION PILOT` data-status badge.
3. Click station 2586 on the Leaflet satellite map.
4. Review AQI, dominant pollutant, wind, and dispersion risk.
5. Open the hotspot intelligence screen.
6. Show source hypotheses and guardrails.
7. Go to Interventions.
8. Complete the verification checklist.
9. Approve the intervention.
10. Dispatch, start, complete, and record outcome.
11. Open Citizen Advisory and approve publishing workflow.
12. Open Reports for the municipal memo.

## Verification Commands

Frontend:

```powershell
cd D:\airguard-ai\frontend
npm run lint
npm run build
```

Backend compile/import:

```powershell
cd D:\airguard-ai
.\.venv\Scripts\python.exe -m compileall backend ml scripts
.\.venv\Scripts\python.exe -c "import backend.app.main; print('backend ok')"
```

Quick API check:

```powershell
curl.exe -L http://127.0.0.1:8000/api/airguard/demo-output
curl.exe -L http://127.0.0.1:8000/api/airguard/intervention-workflows
```

## Notes

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
