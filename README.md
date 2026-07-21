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

- Leaflet satellite tiles use Esri online imagery, so the browser needs internet access for the satellite base layer.
- Workflow state is in-memory for the hackathon demo. Restarting the backend resets intervention workflow state.
- The system is decision-support only. AI recommendations do not automatically authorize enforcement or public publishing.
