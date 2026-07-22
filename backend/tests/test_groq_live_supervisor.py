import json
import unittest

from backend.app.agents.groq_supervisor_agent import GroqSupervisorAgent


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeCompletion:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, payload):
        self.payload = payload

    def create(self, **kwargs):
        return FakeCompletion(json.dumps(self.payload))


class FakeChat:
    def __init__(self, payload):
        self.completions = FakeCompletions(payload)


class FakeGroqClient:
    def __init__(self, payload):
        self.chat = FakeChat(payload)


class GroqLiveSupervisorTests(unittest.TestCase):
    def analyzed_payload(self):
        action = {
            "action": "Verify congestion and idling near the major-road corridor",
            "priority": "medium",
            "why": ["Verified deterministic evidence"],
            "required_evidence_before_enforcement": ["traffic observation"],
            "human_review_required": True,
        }
        return {
            "station_location_id": 2586,
            "refresh_metadata": {
                "source_status": "live",
                "source_timestamp": "2026-07-22T09:00:00Z",
            },
            "analysis_metadata": {
                "analysis_id": "LIVE-TEST",
                "uses_live_station_data": True,
                "forecast_recomputed": False,
            },
            "executive_summary": {
                "headline": "Medium-priority preventive action recommended",
                "monitoring_priority": "medium",
                "intervention_required_now": False,
                "cpcb_aqi": 112.65,
                "cpcb_aqi_category": "Moderately Polluted",
                "dominant_pollutant": "co",
                "selected_forecast_method": "random_forest",
            },
            "evidence_stack": {
                "ground_sensor": {
                    "pollutants": {"pm25": 26.67, "pm10": 66.44, "co": 3.03},
                    "weather": {"wind_speed": 3.59},
                    "dispersion": {"dispersion_risk": "low"},
                },
                "geospatial_context": {"major_road_density_km_per_km2": 4.57},
                "remote_sensing": {"relative_no2_signal": "moderate_relative_no2"},
                "source_hypotheses": [
                    {
                        "source": "traffic corridor exposure",
                        "confidence": "medium",
                        "evidence": ["Live dominant pollutant is CO"],
                    }
                ],
            },
            "recommended_actions": [action],
            "safe_claims": ["Latest screening AQI is 112.65."],
            "claims_to_avoid": ["Do not claim causal proof."],
            "limitations": ["Forecast was not recomputed live."],
            "agent_outputs": {
                "groq_supervisor_decision": {
                    "reasoning_summary": "Deterministic live reasoning.",
                    "selected_forecast_method": (
                        "random_forest (historical benchmark context; not recomputed live)"
                    ),
                    "key_evidence_used": ["Screening AQI: 112.65"],
                }
            },
        }

    def test_deterministic_fields_and_actions_override_unsafe_model_output(self):
        model_payload = {
            "intervention_required_now": True,
            "monitoring_priority": "high",
            "decision_headline": "Industrial unit is the confirmed source",
            "reasoning_summary": "Pollution was caused by a nearby factory.",
            "selected_forecast_method": "live random forest forecast",
            "key_evidence_used": ["A factory is responsible for the pollution."],
            "recommended_actions": [
                {
                    "action": "Shut down the factory",
                    "priority": "high",
                    "why": ["Invented action"],
                    "human_review_required": False,
                },
                {
                    "action": "Verify congestion and idling near the major-road corridor",
                    "priority": "medium",
                    "why": ["Grounded ranking"],
                    "human_review_required": True,
                },
            ],
            "safe_claims": ["The factory caused the pollution."],
            "claims_to_avoid": [],
            "human_review_required": False,
            "limitations": [],
        }
        agent = GroqSupervisorAgent.__new__(GroqSupervisorAgent)
        agent.client = FakeGroqClient(model_payload)
        agent.model = "test-model"

        result = agent.run_from_live_payload(self.analyzed_payload())
        decision = result["decision"]
        action_names = [item["action"] for item in decision["recommended_actions"]]

        self.assertEqual(decision["monitoring_priority"], "medium")
        self.assertFalse(decision["intervention_required_now"])
        self.assertTrue(decision["human_review_required"])
        self.assertNotIn("Shut down the factory", action_names)
        self.assertEqual(decision["safe_claims"], ["Latest screening AQI is 112.65."])
        self.assertEqual(decision["reasoning_summary"], "Deterministic live reasoning.")
        self.assertIn(
            "monitoring_priority_restored_from_deterministic_analysis",
            result["guardrail"]["repairs_applied"],
        )
        self.assertIn(
            "unverified_or_duplicate_action_removed",
            result["guardrail"]["repairs_applied"],
        )


if __name__ == "__main__":
    unittest.main()

