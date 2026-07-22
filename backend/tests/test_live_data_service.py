import os
import unittest
from unittest.mock import patch

from backend.app.services.live_data_service import LiveDataService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class LiveDataServiceTests(unittest.TestCase):
    def setUp(self):
        self.calls = []

    def fake_get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if url.endswith("/locations/2586"):
            return FakeResponse(
                {
                    "results": [
                        {
                            "id": 2586,
                            "name": "Test Chennai Station",
                            "coordinates": {"latitude": 13.16, "longitude": 80.26},
                            "sensors": [
                                {
                                    "id": 1,
                                    "parameter": {"name": "pm25", "units": "µg/m³"},
                                },
                                {
                                    "id": 2,
                                    "parameter": {"name": "pm10", "units": "µg/m³"},
                                },
                                {
                                    "id": 3,
                                    "parameter": {"name": "co", "units": "mg/m³"},
                                },
                            ],
                        }
                    ]
                }
            )
        if url.endswith("/locations/2586/latest"):
            return FakeResponse(
                {
                    "results": [
                        {
                            "sensorsId": 1,
                            "value": 25,
                            "datetime": {"utc": "2026-07-22T09:00:00Z"},
                        },
                        {
                            "sensorsId": 2,
                            "value": 80,
                            "datetime": {"utc": "2026-07-22T09:05:00Z"},
                        },
                        {
                            "sensorsId": 3,
                            "value": 0.8,
                            "datetime": {"utc": "2026-07-22T09:03:00Z"},
                        },
                    ]
                }
            )
        if "open-meteo.com" in url:
            return FakeResponse(
                {
                    "current": {
                        "time": "2026-07-22T09:15",
                        "temperature_2m": 33.2,
                        "relative_humidity_2m": 61,
                        "precipitation": 0,
                        "wind_speed_10m": 1.5,
                        "wind_direction_10m": 92,
                    }
                }
            )
        raise AssertionError(f"Unexpected URL: {url}")

    @patch.dict(os.environ, {"OPENAQ_API_KEY": "test-key"})
    def test_refresh_builds_live_payload_and_uses_cache(self):
        service = LiveDataService(http_get=self.fake_get, cache_ttl_seconds=300)

        first = service.refresh()
        second = service.refresh()

        self.assertEqual(first["refresh_metadata"]["source_status"], "live")
        self.assertEqual(first["refresh_metadata"]["source_timestamp"], "2026-07-22T09:05:00Z")
        self.assertEqual(first["executive_summary"]["cpcb_aqi"], 80.0)
        self.assertEqual(first["executive_summary"]["dominant_pollutant"], "pm10")
        self.assertEqual(first["evidence_stack"]["ground_sensor"]["weather"]["wind_speed"], 1.5)
        self.assertEqual(second["refresh_metadata"]["status"], "cached")
        self.assertTrue(second["refresh_metadata"]["served_from_cache"])
        self.assertEqual(len(self.calls), 3)

    @patch.dict(os.environ, {"OPENAQ_API_KEY": "test-key"})
    def test_upstream_failure_returns_labeled_saved_fallback(self):
        def failing_get(*args, **kwargs):
            raise RuntimeError("upstream unavailable")

        service = LiveDataService(http_get=failing_get, cache_ttl_seconds=300)
        result = service.refresh()

        self.assertEqual(result["refresh_metadata"]["status"], "fallback")
        self.assertEqual(result["refresh_metadata"]["source_status"], "cached_fallback")
        self.assertEqual(result["refresh_metadata"]["fallback_type"], "saved_demo_payload")
        self.assertFalse(result["refresh_metadata"]["new_reading_available"])
        self.assertIn("upstream unavailable", result["refresh_metadata"]["error"])


if __name__ == "__main__":
    unittest.main()

