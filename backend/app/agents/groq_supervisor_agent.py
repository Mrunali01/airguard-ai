import copy
import json
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional
from backend.app.tools.remote_sensing_evidence_tool import RemoteSensingEvidenceTool
from pydantic import BaseModel, Field, ValidationError

from backend.app.llm.groq_client import get_groq_client, get_groq_model
from backend.app.tools.forecast_validation_tool import ForecastValidationTool
from backend.app.tools.evidence_guardrail_tool import EvidenceGuardrailTool
from backend.app.tools.intervention_ranking_tool import InterventionRankingTool
from ml.config import PROJECT_ROOT
from backend.app.tools.wind_sector_evidence_tool import WindSectorEvidenceTool
from backend.app.tools.cpcb_aqi_tool import CpcbAqiTool

OUTPUT_PATH = PROJECT_ROOT / "backend" / "data" / "sample" / "groq_supervisor_agent_output.json"


class GroqSupervisorDecision(BaseModel):
    intervention_required_now: bool
    monitoring_priority: Literal["low", "medium", "high", "data_quality_review"]
    decision_headline: str
    reasoning_summary: str
    selected_forecast_method: str
    key_evidence_used: list[str]
    recommended_actions: list[dict]
    safe_claims: list[str]
    claims_to_avoid: list[str]
    human_review_required: bool
    limitations: list[str]


class GroqSupervisorAgent:
    """
    Groq-powered supervisor agent.

    This is an actual LLM reasoning layer over deterministic evidence tools.
    Tools calculate. Groq reasons and synthesizes.
    """

    def __init__(self, model: Optional[str] = None) -> None:
        self.client = get_groq_client()
        self.model = model or get_groq_model()

    def collect_tool_outputs(self) -> Dict[str, Any]:
        forecast = ForecastValidationTool().run()
        evidence = EvidenceGuardrailTool().run()
        interventions = InterventionRankingTool().run()
        remote_sensing = RemoteSensingEvidenceTool().run()
        cpcb_aqi = CpcbAqiTool().run()
        wind_sector = WindSectorEvidenceTool().run()

        return {
            "forecast_validation_tool": forecast,
            "evidence_guardrail_tool": evidence,
            "intervention_ranking_tool": interventions,
            "remote_sensing_evidence_tool": remote_sensing,
            "cpcb_aqi": cpcb_aqi,
            "wind_sector": wind_sector,
        }

    def _build_prompt(self, tool_outputs: Dict[str, Any]) -> list[dict]:
        system_prompt = """
You are AirGuard AI's Groq-powered Supervisor Agent for urban air-quality intervention.

You must only use the provided tool outputs.
You must not invent station readings, model metrics, sources, or enforcement facts.
You must distinguish evidence-backed hypotheses from causal proof.
You must not claim that the learned ML model is best if the forecast validation tool says a baseline is best.
You must recommend human review before enforcement.

You must not describe nearby industrial POIs as confirmed pollution sources.
You may only say industrial influence is a low-confidence hypothesis requiring verification.
For source attribution, use the phrase "plausible hypothesis" unless causal proof exists.
Do not put industrial influence in safe_claims unless it includes a verification caveat.

Use satellite NO2 only as regional combustion context.
Do not claim satellite NO2 proves ground-level AQI or exact source attribution.
If remote sensing is unavailable, continue using ground/geospatial evidence and mention the limitation. In key_evidence_used, do not use generic labels like "geospatial evidence" or "satellite context".
Always include concrete values from the tools where available, such as AQI value, category, RMSE improvement, road density, PM10/PM2.5 ratio, Sentinel-5P image count, and relative NO2 signal.
Recommended actions must preserve the evidence values from the intervention tool where available.
Use clean professional writing with proper spacing.
Do not concatenate words.
When referencing remote sensing, include the Sentinel-5P image count if available.
Use the exact satellite signal label from the tool, for example "moderate_relative_no2".
Recommended actions must preserve concrete evidence values where available.
When describing forecast method selection, always qualify it as "in the current one-station real-data benchmark" unless broader validation exists.
Use wind-sector evidence when available.

If wind-sector evidence says wind speed class is low, mention low-wind / poor-dispersion / local accumulation risk when relevant.

If wind-sector evidence increases confidence for road dust or traffic corridor exposure, include that in reasoning_summary and key_evidence_used.

Do not claim exact upwind source attribution unless exact source-coordinate geometry exists. Phrase it as "wind-sector screening supports" or "meteorological conditions strengthen the hypothesis."
Prefer "medium-priority preventive action" over "medium-term interventions" for the current scenario.

Safe claims must not sound globally true unless the tool evidence validates them globally.
Return ONLY valid JSON matching this schema:
...


{
  "intervention_required_now": boolean,
  "monitoring_priority": "low" | "medium" | "high" | "data_quality_review",
  "decision_headline": string,
  "reasoning_summary": string,
  "selected_forecast_method": string,
  "key_evidence_used": [
  "Current estimated AQI: 76.275 (Satisfactory)",
  "Forecast method: rolling_mean_24h; RMSE improvement vs persistence: 24.48%",
  "PM10/PM2.5 ratio: 3.92; road density: 26.05 km/km²",
  "Sentinel-5P NO2 signal: moderate_relative_no2 from 269 images"
  key_evidence_used should include concrete values where available:
- CPCB AQI and dominant pollutant
- estimated/model AQI
- forecast RMSE improvement
- PM10/PM2.5 ratio and road density
- Sentinel-5P NO2 signal and image count
- wind direction sector and wind speed class
]
  "recommended_actions": [
    {
      "action": string,
      "priority": string,
      "why": [string],
      "human_review_required": boolean
    }
  ],
  "safe_claims": [string],
  "claims_to_avoid": [string],
  "human_review_required": boolean,
  "limitations": [string]
}
"""

        user_prompt = f"""
Goal:
Assess whether the current Chennai station context requires intervention,
what actions should be recommended, and what should be communicated safely.

Tool outputs:
{json.dumps(tool_outputs, indent=2)}

Make a smart-city command-center decision.
Return only JSON.
"""

        return [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

    def _compact_live_context(self, live_analysis: Dict[str, Any]) -> Dict[str, Any]:
        evidence = live_analysis.get("evidence_stack", {})
        ground = evidence.get("ground_sensor", {})
        summary = live_analysis.get("executive_summary", {})
        geo = evidence.get("geospatial_context", {})
        remote = evidence.get("remote_sensing", {})
        analysis_metadata = live_analysis.get("analysis_metadata", {})

        return {
            "data_provenance": {
                "refresh": live_analysis.get("refresh_metadata", {}),
                "analysis": analysis_metadata,
            },
            "current_station_evidence": {
                "station_location_id": live_analysis.get("station_location_id"),
                "screening_aqi": summary.get("cpcb_aqi"),
                "aqi_category": summary.get("cpcb_aqi_category"),
                "dominant_pollutant": summary.get("dominant_pollutant"),
                "pollutants": ground.get("pollutants", {}),
                "weather": ground.get("weather", {}),
                "dispersion": ground.get("dispersion", {}),
            },
            "cached_context": {
                "road_density_km_per_km2": geo.get("road_density_km_per_km2"),
                "major_road_density_km_per_km2": geo.get(
                    "major_road_density_km_per_km2"
                ),
                "nearest_major_road_m": geo.get("nearest_major_road_m"),
                "industrial_poi_count": geo.get("industrial_poi_count"),
                "vulnerability_poi_count": geo.get("vulnerability_poi_count"),
                "satellite_signal": remote.get("relative_no2_signal"),
                "satellite_image_count": remote.get("collection_image_count"),
            },
            "verified_source_hypotheses": evidence.get("source_hypotheses", []),
            "candidate_interventions": live_analysis.get("recommended_actions", []),
            "deterministic_decision": {
                "headline": summary.get("headline"),
                "monitoring_priority": summary.get("monitoring_priority"),
                "intervention_required_now": summary.get("intervention_required_now"),
            },
            "forecast_context": {
                "selected_method": summary.get("selected_forecast_method"),
                "forecast_recomputed_live": analysis_metadata.get("forecast_recomputed", False),
                "warning": (
                    "This is historical one-station forecast-validation context, not a newly "
                    "recomputed live 24-hour forecast."
                ),
            },
            "safe_claims": live_analysis.get("safe_claims", []),
            "claims_to_avoid": live_analysis.get("claims_to_avoid", []),
            "limitations": live_analysis.get("limitations", []),
        }

    def _build_live_prompt(self, context: Dict[str, Any]) -> list[dict]:
        system_prompt = """
You are AirGuard AI's Groq Supervisor Agent. Synthesize an operational decision from verified live evidence.

Hard rules:
- Use only the supplied JSON context. Never invent readings, timestamps, metrics, sources, locations, or actions.
- AQI, category, monitoring priority, immediate-intervention flag, and candidate actions are deterministic facts. Do not change them.
- Source entries are plausible evidence-backed hypotheses, never causal proof.
- Industrial proximity is screening context only. Never identify a facility as responsible.
- Satellite NO2 is cached regional combustion context, not ground-level AQI or exact attribution.
- The forecast was not recomputed live. Always describe it as historical one-station benchmark context.
- Recommend human verification before intervention, enforcement, or public publishing.
- Rank only candidate action names present in candidate_interventions. Do not create new actions.
- Preserve concrete values exactly as supplied.
- Return only valid JSON matching the required schema.

Required JSON schema:
{
  "intervention_required_now": boolean,
  "monitoring_priority": "low" | "medium" | "high" | "data_quality_review",
  "decision_headline": string,
  "reasoning_summary": string,
  "selected_forecast_method": string,
  "key_evidence_used": [string],
  "recommended_actions": [
    {
      "action": "exact candidate action name",
      "priority": string,
      "why": [string],
      "human_review_required": true
    }
  ],
  "safe_claims": [string],
  "claims_to_avoid": [string],
  "human_review_required": true,
  "limitations": [string]
}
"""
        user_prompt = f"""
Verified live analysis context:
{json.dumps(context, indent=2, ensure_ascii=False)}

Create a concise smart-city operational synthesis. Return only JSON.
"""
        return [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ]

    def _parse_decision(self, content: str) -> GroqSupervisorDecision:
        try:
            raw_decision = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Groq returned invalid JSON: {exc}") from exc

        try:
            return GroqSupervisorDecision(**raw_decision)
        except ValidationError as exc:
            raise RuntimeError(f"Groq JSON did not match expected schema: {exc}") from exc

    def _ground_live_decision(
        self,
        decision: GroqSupervisorDecision,
        live_analysis: Dict[str, Any],
    ) -> tuple[Dict[str, Any], list[str]]:
        grounded = decision.model_dump()
        repairs: list[str] = []
        summary = live_analysis.get("executive_summary", {})
        deterministic_supervisor = (
            live_analysis.get("agent_outputs", {}).get("groq_supervisor_decision", {})
        )

        deterministic_priority = summary.get("monitoring_priority", "data_quality_review")
        deterministic_intervention = bool(summary.get("intervention_required_now", False))
        if grounded["monitoring_priority"] != deterministic_priority:
            grounded["monitoring_priority"] = deterministic_priority
            repairs.append("monitoring_priority_restored_from_deterministic_analysis")
        if grounded["intervention_required_now"] != deterministic_intervention:
            grounded["intervention_required_now"] = deterministic_intervention
            repairs.append("intervention_flag_restored_from_deterministic_analysis")

        grounded["human_review_required"] = True
        grounded["selected_forecast_method"] = deterministic_supervisor.get(
            "selected_forecast_method",
            f"{summary.get('selected_forecast_method', 'unavailable')} "
            "(historical benchmark context; not recomputed live)",
        )

        overclaim_phrases = (
            "confirmed source",
            "caused by",
            "responsible for the pollution",
            "proves that",
            "definitive source",
        )

        def contains_overclaim(value: str) -> bool:
            text = value.lower()
            return any(phrase in text for phrase in overclaim_phrases)

        if contains_overclaim(grounded["decision_headline"]):
            grounded["decision_headline"] = summary.get("headline")
            repairs.append("headline_overclaim_replaced")
        if contains_overclaim(grounded["reasoning_summary"]):
            grounded["reasoning_summary"] = deterministic_supervisor.get(
                "reasoning_summary", summary.get("headline")
            )
            repairs.append("reasoning_overclaim_replaced")

        grounded["key_evidence_used"] = [
            item for item in grounded["key_evidence_used"] if not contains_overclaim(item)
        ]
        if not grounded["key_evidence_used"]:
            grounded["key_evidence_used"] = deterministic_supervisor.get(
                "key_evidence_used", []
            )
            repairs.append("key_evidence_restored_from_deterministic_analysis")

        deterministic_actions = live_analysis.get("recommended_actions", [])
        action_by_name = {
            item.get("action"): item for item in deterministic_actions if item.get("action")
        }
        ordered_actions = []
        seen = set()
        for item in grounded.get("recommended_actions", []):
            name = item.get("action")
            if name not in action_by_name or name in seen:
                repairs.append("unverified_or_duplicate_action_removed")
                continue
            action = copy.deepcopy(action_by_name[name])
            action["groq_synthesis_why"] = item.get("why", [])
            action["human_review_required"] = True
            ordered_actions.append(action)
            seen.add(name)
        for name, action in action_by_name.items():
            if name not in seen:
                ordered_actions.append(copy.deepcopy(action))
        grounded["recommended_actions"] = ordered_actions

        grounded["safe_claims"] = live_analysis.get("safe_claims", [])
        deterministic_avoid = live_analysis.get("claims_to_avoid", [])
        grounded["claims_to_avoid"] = list(
            dict.fromkeys(deterministic_avoid + grounded.get("claims_to_avoid", []))
        )
        grounded["limitations"] = list(
            dict.fromkeys(
                live_analysis.get("limitations", []) + grounded.get("limitations", [])
            )
        )
        return grounded, repairs

    def run_from_live_payload(self, live_analysis: Dict[str, Any]) -> Dict[str, Any]:
        context = self._compact_live_context(live_analysis)
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=self._build_live_prompt(context),
            temperature=0.1,
            max_completion_tokens=1400,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content
        decision = self._parse_decision(content)
        grounded_decision, repairs = self._ground_live_decision(decision, live_analysis)

        return {
            "agent_name": "Groq Live Supervisor Agent",
            "agent_type": "llm_grounded_live_evidence_synthesis_agent",
            "llm_provider": "Groq",
            "model": self.model,
            "synthesized_at": datetime.now(timezone.utc).isoformat().replace(
                "+00:00", "Z"
            ),
            "input_provenance": {
                "analysis_id": live_analysis.get("analysis_metadata", {}).get(
                    "analysis_id"
                ),
                "source_timestamp": live_analysis.get("refresh_metadata", {}).get(
                    "source_timestamp"
                ),
                "uses_live_station_data": live_analysis.get("analysis_metadata", {}).get(
                    "uses_live_station_data", False
                ),
                "forecast_recomputed": False,
            },
            "guardrail": {
                "deterministic_fields_preserved": True,
                "repairs_applied": repairs,
                "human_review_required": True,
            },
            "decision": grounded_decision,
        }

    def run(self) -> Dict[str, Any]:
        tool_outputs = self.collect_tool_outputs()
        messages = self._build_prompt(tool_outputs)

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        content = completion.choices[0].message.content

        try:
            raw_decision = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Groq returned invalid JSON: {exc}\nRaw output:\n{content}"
            )

        try:
            decision = GroqSupervisorDecision(**raw_decision)
        except ValidationError as exc:
            raise RuntimeError(
                f"Groq JSON did not match expected schema: {exc}\nRaw output:\n{content}"
            )

        return {
            "agent_name": "Groq Supervisor Agent",
            "agent_type": "llm_tool_orchestrating_reasoning_agent",
            "llm_provider": "Groq",
            "model": self.model,
            "tool_outputs": tool_outputs,
            "decision": decision.model_dump(),
        }


def main() -> None:
    agent = GroqSupervisorAgent()
    result = agent.run()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(f"Saved Groq supervisor output to: {OUTPUT_PATH}")
    print(json.dumps(result["decision"], indent=2))


if __name__ == "__main__":
    main()
