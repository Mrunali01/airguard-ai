from __future__ import annotations

import copy
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import requests
from dotenv import load_dotenv

from backend.app.tools.wind_sector_evidence_tool import (
    classify_wind_speed,
    compass_sector_from_degrees,
)
from ml.aqi.cpcb_aqi import calculate_cpcb_aqi
from ml.config import PROJECT_ROOT


OPENAQ_BASE_URL = "https://api.openaq.org/v3"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_LOCATION_ID = 2586
DEFAULT_LATITUDE = 13.164544
DEFAULT_LONGITUDE = 80.26285
DEFAULT_CACHE_TTL_SECONDS = 300
POLLUTANTS = ("pm25", "pm10", "no2", "so2", "co", "o3")

DATA_DIR = PROJECT_ROOT / "backend" / "data" / "sample"
DEMO_OUTPUT_PATH = DATA_DIR / "airguard_demo_output.json"

load_dotenv(PROJECT_ROOT / ".env")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_parameter_name(value: Any) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip().lower().replace("₂", "2").replace("₁₀", "10")
    compact = text.replace(".", "").replace("_", "").replace(" ", "")

    aliases = {
        "pm25": "pm25",
        "pm10": "pm10",
        "no2": "no2",
        "so2": "so2",
        "co": "co",
        "o3": "o3",
    }
    return aliases.get(compact)


def normalize_unit(value: Any) -> str:
    if value is None:
        return ""
    return (
        str(value)
        .strip()
        .lower()
        .replace("μ", "u")
        .replace("µ", "u")
        .replace("³", "3")
        .replace(" ", "")
    )


def concentration_for_cpcb(parameter: str, value: Any, unit: Any) -> Optional[float]:
    try:
        concentration = float(value)
    except (TypeError, ValueError):
        return None

    if concentration < 0:
        return None

    normalized_unit = normalize_unit(unit)
    microgram_units = {"ug/m3", "ugm-3", "ugm3"}
    milligram_units = {"mg/m3", "mgm-3", "mgm3"}

    if parameter == "co":
        if normalized_unit in microgram_units:
            return concentration / 1000.0
        if normalized_unit in milligram_units or not normalized_unit:
            return concentration
        return None

    if normalized_unit in milligram_units:
        return concentration * 1000.0
    if normalized_unit in microgram_units or not normalized_unit:
        return concentration
    return None


def parse_timestamp(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def freshness_metadata(source_timestamp: Optional[str], now: datetime) -> Dict[str, Any]:
    measured_at = parse_timestamp(source_timestamp)
    if measured_at is None:
        return {
            "source_age_hours": None,
            "freshness_status": "missing_timestamp",
            "is_fresh": False,
        }

    age_hours = max(0.0, (now - measured_at).total_seconds() / 3600)
    if age_hours <= 6:
        status = "fresh"
    elif age_hours <= 24:
        status = "recent"
    elif age_hours <= 168:
        status = "stale"
    else:
        status = "archival"

    return {
        "source_age_hours": round(age_hours, 2),
        "freshness_status": status,
        "is_fresh": age_hours <= 24,
    }


def dispersion_from_weather(wind_speed: Optional[float]) -> Dict[str, Any]:
    if wind_speed is None:
        return {
            "dispersion_penalty": None,
            "dispersion_risk": "unknown",
        }

    safe_speed = max(float(wind_speed), 0.1)
    if safe_speed <= 1.0:
        risk = "high"
    elif safe_speed <= 2.0:
        risk = "medium"
    else:
        risk = "low"

    return {
        "dispersion_penalty": round(1.0 / (safe_speed + 0.35), 4),
        "dispersion_risk": risk,
    }


def operational_decision(category: Optional[str], dispersion_risk: str) -> Dict[str, Any]:
    if category in {"Poor", "Very Poor", "Severe"}:
        return {
            "monitoring_priority": "high",
            "intervention_required_now": True,
            "headline": f"Current AQI is {category}; immediate human-reviewed intervention assessment recommended",
        }
    if category == "Moderately Polluted" or dispersion_risk in {"medium", "high"}:
        return {
            "monitoring_priority": "medium",
            "intervention_required_now": False,
            "headline": f"Current AQI is {category or 'unavailable'}; medium-priority preventive action recommended",
        }
    return {
        "monitoring_priority": "low",
        "intervention_required_now": False,
        "headline": f"Current AQI is {category or 'unavailable'}; continue routine monitoring",
    }


class LiveDataService:
    """Fetch and cache the latest station evidence for the command centre."""

    def __init__(
        self,
        demo_output_path: Path = DEMO_OUTPUT_PATH,
        http_get: Callable[..., Any] = requests.get,
        cache_ttl_seconds: Optional[int] = None,
    ) -> None:
        self.demo_output_path = demo_output_path
        self.http_get = http_get
        self.cache_ttl_seconds = cache_ttl_seconds or int(
            os.getenv("AIRGUARD_LIVE_CACHE_SECONDS", DEFAULT_CACHE_TTL_SECONDS)
        )
        self.location_id = int(os.getenv("OPENAQ_LOCATION_ID", DEFAULT_LOCATION_ID))
        self._cache: Optional[Dict[str, Any]] = None
        self._cached_at: Optional[datetime] = None
        self._lock = threading.Lock()

    def _load_demo_payload(self) -> Dict[str, Any]:
        with open(self.demo_output_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _request_json(
        self,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        response = self.http_get(url, params=params, headers=headers or {}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Upstream service returned an invalid JSON payload")
        return payload

    def _openaq_headers(self) -> Dict[str, str]:
        api_key = os.getenv("OPENAQ_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAQ_API_KEY is not configured")
        return {"X-API-Key": api_key}

    def _fetch_openaq_station(self) -> Dict[str, Any]:
        headers = self._openaq_headers()
        with ThreadPoolExecutor(max_workers=2) as executor:
            location_future = executor.submit(
                self._request_json,
                f"{OPENAQ_BASE_URL}/locations/{self.location_id}",
                headers=headers,
            )
            latest_future = executor.submit(
                self._request_json,
                f"{OPENAQ_BASE_URL}/locations/{self.location_id}/latest",
                headers=headers,
            )
            location_payload = location_future.result()
            latest_payload = latest_future.result()

        location_results = location_payload.get("results") or []
        if not location_results:
            raise RuntimeError(f"OpenAQ location {self.location_id} was not found")

        location = location_results[0]
        sensor_lookup: Dict[int, Dict[str, Any]] = {}
        for sensor in location.get("sensors") or []:
            sensor_id = sensor.get("id")
            if sensor_id is None:
                continue
            parameter = sensor.get("parameter") or {}
            sensor_lookup[int(sensor_id)] = {
                "parameter": normalize_parameter_name(
                    parameter.get("name")
                    or parameter.get("displayName")
                    or sensor.get("name")
                ),
                "unit": sensor.get("unit") or parameter.get("units"),
            }

        readings: Dict[str, Dict[str, Any]] = {}
        for item in latest_payload.get("results") or []:
            sensor_id = item.get("sensorsId")
            metadata = sensor_lookup.get(int(sensor_id), {}) if sensor_id is not None else {}
            parameter = metadata.get("parameter")
            if parameter not in POLLUTANTS:
                continue

            converted = concentration_for_cpcb(parameter, item.get("value"), metadata.get("unit"))
            if converted is None:
                continue

            timestamp = (item.get("datetime") or {}).get("utc")
            existing = readings.get(parameter)
            if existing and (parse_timestamp(existing.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc)) >= (
                parse_timestamp(timestamp) or datetime.min.replace(tzinfo=timezone.utc)
            ):
                continue

            readings[parameter] = {
                "value": round(converted, 4),
                "timestamp": timestamp,
                "source_unit": metadata.get("unit"),
            }

        if not readings:
            raise RuntimeError("OpenAQ returned no supported pollutant readings")

        timestamps = [parse_timestamp(item.get("timestamp")) for item in readings.values()]
        valid_timestamps = [item for item in timestamps if item is not None]
        source_timestamp = iso_utc(max(valid_timestamps)) if valid_timestamps else None

        coordinates = location.get("coordinates") or {}
        return {
            "location_id": self.location_id,
            "location_name": location.get("name"),
            "latitude": coordinates.get("latitude"),
            "longitude": coordinates.get("longitude"),
            "source_timestamp": source_timestamp,
            "pollutants": {key: readings.get(key, {}).get("value") for key in POLLUTANTS},
            "reading_details": readings,
        }

    def _fetch_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        payload = self._request_json(
            OPEN_METEO_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": (
                    "temperature_2m,relative_humidity_2m,precipitation,"
                    "wind_speed_10m,wind_direction_10m"
                ),
                "wind_speed_unit": "ms",
                "timezone": "UTC",
            },
        )
        current = payload.get("current") or {}
        if not current:
            raise RuntimeError("Open-Meteo returned no current weather")

        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "wind_speed": current.get("wind_speed_10m"),
            "wind_direction": current.get("wind_direction_10m"),
            "source_timestamp": current.get("time"),
        }

    def _build_live_payload(
        self,
        station: Dict[str, Any],
        weather: Dict[str, Any],
        requested_at: datetime,
        previous_source_timestamp: Optional[str],
    ) -> Dict[str, Any]:
        payload = self._load_demo_payload()
        pollutants = station["pollutants"]
        aqi = calculate_cpcb_aqi(pollutants)
        dispersion = dispersion_from_weather(weather.get("wind_speed"))
        pm_ratio = None
        if pollutants.get("pm10") is not None and pollutants.get("pm25") not in {None, 0}:
            pm_ratio = round(float(pollutants["pm10"]) / float(pollutants["pm25"]), 4)
        dispersion["pm10_pm25_ratio"] = pm_ratio

        freshness = freshness_metadata(station.get("source_timestamp"), requested_at)
        decision = operational_decision(aqi.get("category"), dispersion["dispersion_risk"])
        wind_sector = compass_sector_from_degrees(weather.get("wind_direction"))
        wind_speed_class = classify_wind_speed(weather.get("wind_speed"))

        payload["generated_at"] = iso_utc(requested_at)
        payload["station_location_id"] = station["location_id"]
        payload["output_type"] = "live_station_intelligence"
        payload["data_mode"] = "live_station_pilot"
        payload["refresh_metadata"] = {
            "status": "updated",
            "source_status": "live",
            "requested_at": iso_utc(requested_at),
            "source_timestamp": station.get("source_timestamp"),
            "weather_timestamp": weather.get("source_timestamp"),
            "new_reading_available": station.get("source_timestamp") != previous_source_timestamp,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "served_from_cache": False,
            **freshness,
        }

        summary = payload.setdefault("executive_summary", {})
        summary.update(
            {
                "headline": decision["headline"],
                "monitoring_priority": decision["monitoring_priority"],
                "intervention_required_now": decision["intervention_required_now"],
                "current_estimated_aqi": aqi.get("aqi"),
                "current_estimated_aqi_category": aqi.get("category"),
                "cpcb_aqi": aqi.get("aqi"),
                "cpcb_aqi_category": aqi.get("category"),
                "dominant_pollutant": aqi.get("dominant_pollutant"),
                "data_status": freshness["freshness_status"],
                "sensor_age_hours": freshness["source_age_hours"],
                "wind_from_sector": wind_sector,
                "wind_speed_class": wind_speed_class,
            }
        )

        ground_sensor = payload.setdefault("evidence_stack", {}).setdefault("ground_sensor", {})
        ground_sensor.update(
            {
                "latest_datetime_utc": station.get("source_timestamp"),
                "max_age_hours": freshness["source_age_hours"],
                "pollutants": pollutants,
                "pollutant_reading_details": station.get("reading_details"),
                "weather": {key: value for key, value in weather.items() if key != "source_timestamp"},
                "weather_source_timestamp": weather.get("source_timestamp"),
                "aqi_estimate": {
                    "estimated_aqi": aqi.get("aqi"),
                    "estimated_aqi_category": aqi.get("category"),
                    "note": (
                        "CPCB breakpoint screening AQI computed from the latest available readings. "
                        "It is not a regulatory AQI unless required averaging windows are satisfied."
                    ),
                },
                "dispersion": dispersion,
                "cpcb_aqi_calculation": {
                    "tool_name": "CPCB AQI Tool",
                    "tool_type": "live_breakpoint_aqi_screening_tool",
                    "city": payload.get("city", "Chennai"),
                    "stations": [
                        {
                            "location_id": station["location_id"],
                            "latest_datetime_utc": station.get("source_timestamp"),
                            "data_status": freshness["freshness_status"],
                            "cpcb_aqi": aqi,
                            "note": (
                                "Computed from available latest pollutants; missing readings are not fabricated."
                            ),
                        }
                    ],
                },
            }
        )

        limitations = payload.setdefault("limitations", [])
        live_limitation = (
            "Live CPCB breakpoint AQI is a screening value based on latest available OpenAQ readings; "
            "regulatory AQI requires pollutant-specific averaging windows and official validation."
        )
        if live_limitation not in limitations:
            limitations.append(live_limitation)

        return payload

    def _fallback_payload(self, error: Exception, requested_at: datetime) -> Dict[str, Any]:
        if self._cache is not None:
            payload = copy.deepcopy(self._cache)
            fallback_type = "last_successful_live_cache"
        else:
            payload = self._load_demo_payload()
            fallback_type = "saved_demo_payload"

        source_timestamp = (
            payload.get("evidence_stack", {})
            .get("ground_sensor", {})
            .get("latest_datetime_utc")
        )
        payload["refresh_metadata"] = {
            "status": "fallback",
            "source_status": "cached_fallback",
            "fallback_type": fallback_type,
            "requested_at": iso_utc(requested_at),
            "source_timestamp": source_timestamp,
            "new_reading_available": False,
            "served_from_cache": self._cache is not None,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "error": str(error),
            **freshness_metadata(source_timestamp, requested_at),
        }
        return payload

    def refresh(self, force: bool = False) -> Dict[str, Any]:
        with self._lock:
            requested_at = utc_now()
            if (
                not force
                and self._cache is not None
                and self._cached_at is not None
                and (requested_at - self._cached_at).total_seconds() < self.cache_ttl_seconds
            ):
                payload = copy.deepcopy(self._cache)
                metadata = payload.setdefault("refresh_metadata", {})
                metadata.update(
                    {
                        "status": "cached",
                        "requested_at": iso_utc(requested_at),
                        "new_reading_available": False,
                        "served_from_cache": True,
                    }
                )
                return payload

            previous_source_timestamp = None
            if self._cache:
                previous_source_timestamp = self._cache.get("refresh_metadata", {}).get(
                    "source_timestamp"
                )

            try:
                latitude = float(os.getenv("OPENAQ_LATITUDE", DEFAULT_LATITUDE))
                longitude = float(os.getenv("OPENAQ_LONGITUDE", DEFAULT_LONGITUDE))
                with ThreadPoolExecutor(max_workers=2) as executor:
                    station_future = executor.submit(self._fetch_openaq_station)
                    weather_future = executor.submit(self._fetch_weather, latitude, longitude)
                    station = station_future.result()
                    weather = weather_future.result()
                payload = self._build_live_payload(
                    station,
                    weather,
                    requested_at,
                    previous_source_timestamp,
                )
                self._cache = copy.deepcopy(payload)
                self._cached_at = requested_at
                return payload
            except Exception as error:
                return self._fallback_payload(error, requested_at)


live_data_service = LiveDataService()
