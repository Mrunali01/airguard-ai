# AirGuard AI Architecture

## System Overview

```text
OpenAQ station data
        |
        v
Ground sensor + weather snapshot
        |
        +--> CPCB AQI calculation
        +--> Forecast validation
        +--> Wind-sector screening
        +--> Geospatial context
        +--> Sentinel-5P NO2 context
        |
        v
Evidence stack
        |
        v
Groq supervisor + guardrails
        |
        +--> Source hypotheses
        +--> Recommended interventions
        +--> Safe claims / claims to avoid
        +--> Citizen advisory
        |
        v
FastAPI backend
        |
        v
Next.js command centre frontend
```

## Frontend

- Framework: Next.js App Router.
- Language: TypeScript.
- Styling: Tailwind CSS.
- Map: Leaflet with satellite tile base layer and operational overlays.
- Main route: `/`.

Frontend screens:

- Command Centre Overview.
- Hotspot Intelligence.
- Intervention Queue.
- Agent Analysis Trace.
- Citizen Advisory.
- Decision Memo.
- Data Sources and Guardrails.

## Backend

- Framework: FastAPI.
- Main app: `backend.app.main:app`.
- API prefix: `/api/airguard`.
- Demo data source: `backend/data/sample`.

Backend responsibilities:

- Serve integrated AirGuard demo payload.
- Serve CPCB AQI and remote-sensing evidence.
- Run Groq supervisor when configured.
- Own intervention workflow state.
- Validate intervention transitions.
- Maintain in-memory audit log for demo workflow actions.

## Intervention Workflow

Backend-owned state machine:

```text
Proposed
  |
  | request verification
  v
Under verification
  |
  | all checks completed
  v
Approved
  |
  v
Dispatched
  |
  v
In progress
  |
  v
Completed
  |
  v
Outcome recorded
```

Rejection can occur before final outcome recording.

Approval is blocked unless all required checks are true:

- field inspection photo.
- evidence confirmation.
- ward engineer approval.

## Safety Guardrails

- AI recommendations are advisory.
- No automatic enforcement.
- Industrial source responsibility is not claimed as causal proof.
- Satellite NO2 is treated as regional context, not direct ground-level AQI.
- Human approval is required for dispatch and citizen publishing.
