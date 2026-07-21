# AI-Powered Urban Air Quality Intelligence for Smart City Intervention

## Theme

Smart Cities / Environmental Intelligence / Geospatial Analytics / Public Health

## AirGuard AI Alignment

AirGuard AI addresses the challenge by turning fragmented air-quality signals into an operational command-centre workflow for Chennai. The system combines station measurements, CPCB AQI calculation, forecast validation, Sentinel-5P NO2 evidence, weather and wind-sector context, geospatial exposure, source hypotheses, intervention recommendations, citizen advisories, and municipal decision memo support.

## Challenge Capabilities Covered

### Geospatial Pollution Source Attribution

AirGuard AI presents source hypotheses rather than unsupported causal claims. For the Chennai pilot station, the system evaluates:

- PM10-heavy pollution pattern.
- PM10/PM2.5 ratio.
- road density and nearby major roads.
- industrial POI count.
- wind-sector screening.
- Sentinel-5P NO2 regional combustion context.

The dashboard explicitly separates plausible hypotheses from causal proof.

### Hyperlocal Predictive AQI Forecasting

The backend includes forecast validation outputs for station-level AQI and CPCB-window AQI. The frontend displays:

- best overall method.
- best learned model.
- RMSE evidence.
- forecast caveats and validation warning.

### Enforcement and Intervention Intelligence

The intervention queue converts evidence into a human-approved municipal workflow:

```text
Proposed -> Under verification -> Approved -> Dispatched -> In progress -> Completed -> Outcome recorded
```

The backend owns workflow state and blocks approval until required verification checks are complete.

### Multi-Layer City Intelligence Dashboard

The frontend provides:

- Leaflet satellite command map.
- station drawer.
- hotspot intelligence drilldown.
- source hypotheses.
- geospatial exposure evidence.
- intervention queue.
- agent analysis trace.
- citizen advisory editor and phone preview.
- decision memo screen.
- data-source and guardrail screen.

### Citizen Health Risk Advisory

AirGuard AI generates and displays public-safe advisories, including English and Hindi text from the demo payload. The UI requires approval before publishing and preserves claims-to-avoid guardrails.

## Demo Pilot

- City: Chennai.
- Station: OpenAQ station 2586.
- Data mode: Real station pilot.
- Key pollutant: PM10.
- Current CPCB AQI in sample payload: Satisfactory.
- Evidence stance: decision support, not automatic enforcement.
