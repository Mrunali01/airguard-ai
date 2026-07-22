import unittest

from backend.app.services.live_analysis_service import analyze_live_payload


class LiveAnalysisServiceTests(unittest.TestCase):
    def live_payload(self):
        return {
            "station_location_id": 2586,
            "refresh_metadata": {
                "source_status": "live",
                "source_timestamp": "2026-07-22T09:00:00Z",
                "weather_timestamp": "2026-07-22T09:15:00Z",
            },
            "executive_summary": {
                "headline": "Medium-priority preventive action recommended",
                "cpcb_aqi": 112.65,
                "cpcb_aqi_category": "Moderately Polluted",
                "dominant_pollutant": "co",
                "selected_forecast_method": "random_forest",
            },
            "evidence_stack": {
                "ground_sensor": {
                    "pollutants": {
                        "pm25": 26.67,
                        "pm10": 66.44,
                        "no2": 16.86,
                        "co": 3.03,
                    },
                    "weather": {"wind_speed": 1.5},
                    "dispersion": {
                        "pm10_pm25_ratio": 2.49,
                        "dispersion_risk": "medium",
                    },
                },
                "geospatial_context": {
                    "road_density_km_per_km2": 26.05,
                    "major_road_density_km_per_km2": 4.57,
                    "nearest_major_road_m": 22.61,
                    "industrial_poi_count": 15,
                    "vulnerability_poi_count": 6,
                },
                "remote_sensing": {"relative_no2_signal": "moderate_relative_no2"},
            },
        }

    def test_analysis_uses_live_evidence_and_rejects_causal_claims(self):
        result = analyze_live_payload(self.live_payload())

        metadata = result["analysis_metadata"]
        sources = {
            item["source"] for item in result["evidence_stack"]["source_hypotheses"]
        }

        self.assertTrue(metadata["uses_live_station_data"])
        self.assertFalse(metadata["forecast_recomputed"])
        self.assertIn("road dust / resuspension", sources)
        self.assertIn("traffic corridor exposure", sources)
        self.assertIn("industrial influence screening", sources)
        self.assertGreaterEqual(len(result["recommended_actions"]), 3)
        self.assertTrue(
            result["agent_outputs"]["groq_supervisor_decision"]["human_review_required"]
        )
        self.assertEqual(
            result["agent_outputs"]["citizen_advisory"]["advisory_level"],
            "moderate",
        )
        self.assertEqual(result["executive_summary"]["citizen_advisory_level"], "moderate")
        self.assertTrue(any("causal proof" in item for item in result["claims_to_avoid"]))

    def test_cached_fallback_is_disclosed(self):
        payload = self.live_payload()
        payload["refresh_metadata"]["source_status"] = "cached_fallback"

        result = analyze_live_payload(payload)

        self.assertFalse(result["analysis_metadata"]["uses_live_station_data"])
        self.assertIn("cached fallback", result["limitations"][0].lower())


if __name__ == "__main__":
    unittest.main()
