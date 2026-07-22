from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


HIGH_AQI_CATEGORIES = {"Poor", "Very Poor", "Severe"}
PRIORITY_ORDER = {"high": 3, "medium": 2, "low-medium": 1.5, "low": 1}


def as_float(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def rounded(value: Any, digits: int = 2) -> Any:
    number = as_float(value)
    return round(number, digits) if number is not None else "unavailable"


def build_source_hypotheses(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    evidence_stack = payload.get("evidence_stack", {})
    ground = evidence_stack.get("ground_sensor", {})
    pollutants = ground.get("pollutants", {})
    dispersion = ground.get("dispersion", {})
    geo = evidence_stack.get("geospatial_context", {})
    remote = evidence_stack.get("remote_sensing", {})

    pm_ratio = as_float(dispersion.get("pm10_pm25_ratio"))
    road_density = as_float(geo.get("road_density_km_per_km2"))
    major_road_density = as_float(geo.get("major_road_density_km_per_km2"))
    nearest_major_road = as_float(geo.get("nearest_major_road_m"))
    industrial_count = as_float(geo.get("industrial_poi_count"))
    co = as_float(pollutants.get("co"))
    no2 = as_float(pollutants.get("no2"))
    dominant = payload.get("executive_summary", {}).get("dominant_pollutant")
    dispersion_risk = dispersion.get("dispersion_risk")
    satellite_signal = remote.get("relative_no2_signal")

    hypotheses: List[Dict[str, Any]] = []

    if pm_ratio is not None and road_density is not None and pm_ratio >= 2.0:
        confidence = "medium" if pm_ratio >= 2.5 and road_density >= 15 else "low-medium"
        hypotheses.append(
            {
                "source": "road dust / resuspension",
                "confidence": confidence,
                "evidence": [
                    f"Live PM10/PM2.5 ratio is {pm_ratio:.2f}",
                    f"Cached OSM road density is {road_density:.2f} km/km²",
                ],
                "evidence_scope": "live pollutant pattern + cached geospatial context",
            }
        )

    traffic_evidence = []
    if major_road_density is not None:
        traffic_evidence.append(
            f"Cached OSM major-road density is {major_road_density:.2f} km/km²"
        )
    if nearest_major_road is not None:
        traffic_evidence.append(f"Nearest mapped major road is {nearest_major_road:.0f} m away")
    if dominant in {"co", "no2"}:
        traffic_evidence.append(f"Live dominant pollutant is {str(dominant).upper()}")
    elif co is not None or no2 is not None:
        traffic_evidence.append(f"Live CO is {rounded(co)} mg/m³ and NO2 is {rounded(no2)} µg/m³")
    if traffic_evidence and (major_road_density or 0) >= 2:
        hypotheses.append(
            {
                "source": "traffic corridor exposure",
                "confidence": "medium" if dominant in {"co", "no2"} else "low-medium",
                "evidence": traffic_evidence,
                "evidence_scope": "live combustion indicators + cached road context",
            }
        )

    if industrial_count is not None and industrial_count > 0:
        industrial_evidence = [
            f"{int(industrial_count)} industrial-tagged OSM features are mapped within the screening radius"
        ]
        if satellite_signal:
            industrial_evidence.append(
                f"Cached Sentinel-5P context is {str(satellite_signal).replace('_', ' ')}"
            )
        hypotheses.append(
            {
                "source": "industrial influence screening",
                "confidence": "low",
                "evidence": industrial_evidence,
                "evidence_scope": "screening only; facility emissions are not verified",
            }
        )

    if dispersion_risk in {"medium", "high"}:
        hypotheses.append(
            {
                "source": "meteorological trapping / poor dispersion",
                "confidence": "medium",
                "evidence": [
                    f"Live dispersion risk is {dispersion_risk}",
                    f"Live wind speed is {rounded(ground.get('weather', {}).get('wind_speed'))} m/s",
                ],
                "evidence_scope": "live meteorological context",
            }
        )

    return hypotheses


def build_interventions(
    payload: Dict[str, Any],
    hypotheses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    evidence_stack = payload.get("evidence_stack", {})
    geo = evidence_stack.get("geospatial_context", {})
    summary = payload.get("executive_summary", {})
    category = summary.get("cpcb_aqi_category")
    hypothesis_sources = {item.get("source") for item in hypotheses}
    vulnerability_count = int(as_float(geo.get("vulnerability_poi_count")) or 0)

    actions: List[Dict[str, Any]] = []

    if category in HIGH_AQI_CATEGORIES:
        actions.append(
            {
                "action": "Escalate hotspot for immediate field verification",
                "priority": "high",
                "why": [f"Live screening AQI category is {category}"],
                "required_evidence_before_enforcement": [
                    "official station validation",
                    "field inspection",
                    "authorized pollution-control review",
                ],
                "human_review_required": True,
            }
        )

    if "road dust / resuspension" in hypothesis_sources:
        actions.append(
            {
                "action": "Inspect priority road corridors for dust and resuspension",
                "priority": "medium",
                "why": [
                    "Live particulate ratio and mapped road density support a road-dust hypothesis"
                ],
                "required_evidence_before_enforcement": [
                    "field inspection photos",
                    "road-dust accumulation confirmation",
                    "ward engineer review",
                ],
                "human_review_required": True,
            }
        )

    if "traffic corridor exposure" in hypothesis_sources:
        actions.append(
            {
                "action": "Verify congestion and idling near the major-road corridor",
                "priority": "medium",
                "why": [
                    "Live combustion indicators align with cached major-road exposure context"
                ],
                "required_evidence_before_enforcement": [
                    "peak-hour traffic observation",
                    "traffic police confirmation",
                    "repeat CO/NO2 measurements",
                ],
                "human_review_required": True,
            }
        )

    if "industrial influence screening" in hypothesis_sources:
        actions.append(
            {
                "action": "Cross-check nearby industrial units against official compliance records",
                "priority": "low-medium",
                "why": ["Mapped industrial proximity warrants screening, not attribution"],
                "required_evidence_before_enforcement": [
                    "official industry inventory",
                    "wind-to-source geometry",
                    "permit and stack-emission records",
                ],
                "human_review_required": True,
            }
        )

    if vulnerability_count > 0:
        actions.append(
            {
                "action": "Prepare a targeted advisory for nearby sensitive receptors",
                "priority": "medium" if category not in {"Good", "Satisfactory"} else "low",
                "why": [
                    f"{vulnerability_count} cached school/hospital POIs are mapped within the screening radius",
                    f"Live screening AQI category is {category or 'unavailable'}",
                ],
                "required_evidence_before_enforcement": [
                    "validate receptor list",
                    "public-health officer approval",
                ],
                "human_review_required": True,
            }
        )

    if not actions:
        actions.append(
            {
                "action": "Continue monitoring until additional evidence is available",
                "priority": "low",
                "why": ["Current evidence does not support a stronger operational recommendation"],
                "required_evidence_before_enforcement": [],
                "human_review_required": True,
            }
        )

    return sorted(
        actions,
        key=lambda item: PRIORITY_ORDER.get(str(item.get("priority")), 0),
        reverse=True,
    )


def build_live_advisory(aqi: Any, category: Optional[str]) -> Dict[str, Any]:
    if category in {"Good", "Satisfactory"}:
        level = "low"
        english = (
            f"The latest screening AQI near the station is {rounded(aqi)} ({category}). "
            "Most people can continue normal activities. Sensitive individuals should remain aware "
            "of symptoms near dusty or congested roads."
        )
        hindi = (
            f"स्टेशन के पास नवीनतम स्क्रीनिंग AQI {rounded(aqi)} ({category}) है। "
            "अधिकांश लोग सामान्य गतिविधियां जारी रख सकते हैं। संवेदनशील लोग धूल या अधिक यातायात "
            "वाले क्षेत्रों में लक्षणों पर ध्यान दें।"
        )
    elif category == "Moderately Polluted":
        level = "moderate"
        english = (
            f"The latest screening AQI near the station is {rounded(aqi)} (Moderately Polluted). "
            "Children, older adults, people with asthma or heart conditions, and outdoor workers "
            "should reduce prolonged exposure near dusty or congested roads if they experience discomfort."
        )
        hindi = (
            f"स्टेशन के पास नवीनतम स्क्रीनिंग AQI {rounded(aqi)} (मध्यम रूप से प्रदूषित) है। "
            "बच्चे, बुजुर्ग, अस्थमा या हृदय रोग वाले लोग और बाहर काम करने वाले लोग असुविधा होने पर "
            "धूल या अधिक यातायात वाले क्षेत्रों में लंबे समय तक रहने से बचें।"
        )
    else:
        level = "high"
        english = (
            f"The latest screening AQI near the station is {rounded(aqi)} ({category or 'elevated'}). "
            "Sensitive groups should limit prolonged outdoor exertion and follow local public-health guidance. "
            "This screening result requires official confirmation."
        )
        hindi = (
            f"स्टेशन के पास नवीनतम स्क्रीनिंग AQI {rounded(aqi)} ({category or 'बढ़ा हुआ'}) है। "
            "संवेदनशील समूह लंबे समय तक बाहर कठिन गतिविधि सीमित करें और स्थानीय स्वास्थ्य सलाह का पालन करें। "
            "इस स्क्रीनिंग परिणाम की आधिकारिक पुष्टि आवश्यक है।"
        )

    return {
        "advisory_level": level,
        "panic_level": "none",
        "english_advisory": english,
        "hindi_advisory": hindi,
        "who_should_take_care": [
            "children",
            "older adults",
            "people with asthma, breathing difficulty, or heart conditions",
            "outdoor workers",
        ],
        "recommended_precautions": [
            "Check the latest local advisory before prolonged outdoor activity.",
            "Reduce exposure near visibly dusty or heavily congested roads if symptoms occur.",
            "Seek medical advice for persistent breathing difficulty or chest discomfort.",
        ],
        "data_limitations": [
            "Generated from the latest available station screening AQI, not a final regulatory AQI.",
            "Advice is general public-health information and not an individual medical diagnosis.",
        ],
    }


def analyze_live_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(payload)
    metadata = result.get("refresh_metadata", {})
    summary = result.get("executive_summary", {})
    ground = result.get("evidence_stack", {}).get("ground_sensor", {})
    geo = result.get("evidence_stack", {}).get("geospatial_context", {})

    hypotheses = build_source_hypotheses(result)
    interventions = build_interventions(result, hypotheses)
    result.setdefault("evidence_stack", {})["source_hypotheses"] = hypotheses
    result["recommended_actions"] = interventions

    aqi = summary.get("cpcb_aqi")
    category = summary.get("cpcb_aqi_category")
    dominant = summary.get("dominant_pollutant")
    wind_speed = ground.get("weather", {}).get("wind_speed")
    dispersion_risk = ground.get("dispersion", {}).get("dispersion_risk")
    vulnerability_count = geo.get("vulnerability_poi_count")
    is_live = metadata.get("source_status") == "live"

    safe_claims = [
        f"Latest available station screening AQI is {rounded(aqi)} ({category or 'unavailable'}).",
        f"The dominant pollutant in the latest available readings is {str(dominant).upper() if dominant else 'unavailable'}.",
        f"Current weather indicates {dispersion_risk or 'unknown'} dispersion risk with wind speed {rounded(wind_speed)} m/s.",
    ]
    claims_to_avoid = [
        "Do not describe source hypotheses as causal proof.",
        "Do not identify a specific road or industrial unit as responsible without field and directional evidence.",
        "Do not describe the latest-reading breakpoint calculation as final regulatory AQI.",
        "Do not describe the historical forecast benchmark as a newly recomputed live 24-hour forecast.",
    ]
    limitations = [
        "The analysis uses the latest available OpenAQ measurements, not guaranteed second-by-second readings.",
        "OSM vulnerability and source context is cached and may be incomplete.",
        "Sentinel-5P is regional satellite context and is not refreshed with every station reading.",
        "The 24-hour model shown in the dashboard is historical validation context; live forecast inference is not recomputed by this analysis.",
    ]
    if not is_live:
        limitations.insert(0, "Live upstream data was unavailable; this analysis uses cached fallback evidence.")

    key_evidence = [
        f"Source reading: {metadata.get('source_timestamp') or 'unavailable'}",
        f"Screening AQI: {rounded(aqi)} ({category or 'unavailable'}); dominant pollutant: {str(dominant).upper() if dominant else 'unavailable'}",
        f"Wind speed: {rounded(wind_speed)} m/s; dispersion risk: {dispersion_risk or 'unknown'}",
        f"Sensitive receptors in cached OSM context: {vulnerability_count if vulnerability_count is not None else 'unavailable'}",
    ]

    reasoning = (
        f"The latest available station evidence indicates AQI {rounded(aqi)} "
        f"({category or 'unavailable'}), dominated by "
        f"{str(dominant).upper() if dominant else 'an unavailable pollutant signal'}. "
        f"Live weather gives {dispersion_risk or 'unknown'} dispersion risk. "
        f"The system generated {len(hypotheses)} evidence-backed source hypotheses and "
        f"{len(interventions)} candidate actions; all require human verification."
    )

    supervisor = {
        "decision_headline": summary.get("headline"),
        "reasoning_summary": reasoning,
        "selected_forecast_method": (
            f"{summary.get('selected_forecast_method') or 'unavailable'} "
            "(historical benchmark context; not recomputed live)"
        ),
        "key_evidence_used": key_evidence,
        "recommended_actions": interventions,
        "safe_claims": safe_claims,
        "claims_to_avoid": claims_to_avoid,
        "human_review_required": True,
        "limitations": limitations,
    }
    result.setdefault("agent_outputs", {})["groq_supervisor_decision"] = supervisor
    result["agent_outputs"]["citizen_advisory"] = build_live_advisory(aqi, category)
    summary["citizen_advisory_level"] = result["agent_outputs"]["citizen_advisory"][
        "advisory_level"
    ]
    result["safe_claims"] = safe_claims
    result["claims_to_avoid"] = claims_to_avoid
    result["limitations"] = limitations
    result["analysis_metadata"] = {
        "analysis_id": f"LIVE-{uuid4().hex[:10].upper()}",
        "analysis_type": "deterministic_live_current_condition_screening",
        "analyzed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "uses_live_station_data": is_live,
        "source_timestamp": metadata.get("source_timestamp"),
        "weather_timestamp": metadata.get("weather_timestamp"),
        "forecast_recomputed": False,
        "source_attribution_mode": "evidence_backed_hypotheses_not_causal_proof",
        "human_review_required": True,
    }
    return result
