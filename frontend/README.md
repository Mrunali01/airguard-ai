# AirGuard AI Frontend

This is the Next.js command-centre dashboard for AirGuard AI.

It connects to the FastAPI backend through:

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## Run Locally

```powershell
cd D:\airguard-ai\frontend
npm install
Copy-Item .env.example .env.local
npm run dev -- --hostname 127.0.0.1
```

Open:

```text
http://127.0.0.1:3000
```

## Scripts

```powershell
npm run dev
npm run lint
npm run build
npm run start
```

## Deployment

Deploy this folder as a Next.js app.

Recommended Vercel settings:

```text
Root directory: frontend
Framework preset: Next.js
Install command: npm install
Build command: npm run build
```

Set the deployed backend URL:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-backend-domain.example.com
```

The frontend expects the backend route:

```text
GET /api/airguard/demo-output
```

It also calls the backend workflow command endpoints for intervention approvals, dispatch, advisory actions, and memo export.

## Notes

- The map uses Leaflet and online Esri satellite imagery.
- The dashboard includes loading and error states for API failures.
- Do not commit `.env.local`; use `.env.example` for shared configuration.
