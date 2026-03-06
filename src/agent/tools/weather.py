from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib import error, parse, request

from .base import BaseTool


class _OpenWeatherBaseTool(BaseTool):
    """Shared OpenWeatherMap configuration and request helpers."""

    current_url_env = "OPENWEATHERMAP_BASE_URL"
    forecast_url_env = "OPENWEATHERMAP_FORECAST_BASE_URL"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENWEATHERMAP_API_KEY", "").strip()
        self.current_base_url = os.environ.get(
            self.current_url_env,
            "https://api.openweathermap.org/data/2.5/weather",
        ).strip()
        self.forecast_base_url = os.environ.get(
            self.forecast_url_env,
            "https://api.openweathermap.org/data/2.5/forecast",
        ).strip()
        self.timeout_seconds = float(os.environ.get("OPENWEATHERMAP_TIMEOUT_SECONDS", "10"))

    async def _request_json(self, base_url: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {
                "ok": False,
                "error": "OPENWEATHERMAP_API_KEY is not configured.",
            }

        params = dict(params)
        params["appid"] = self.api_key
        url = f"{base_url}?{parse.urlencode(params)}"

        try:
            raw_response = await asyncio.to_thread(self._fetch, url)
            payload = json.loads(raw_response)
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            return {
                "ok": False,
                "error": f"OpenWeatherMap request failed with HTTP {exc.code}",
                "details": response_body,
            }
        except (error.URLError, TimeoutError) as exc:
            return {"ok": False, "error": f"OpenWeatherMap request failed: {exc}"}
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error": "Failed to decode OpenWeatherMap response.",
                "details": str(exc),
            }

        return {"ok": True, "payload": payload}

    def _validated_query(
        self,
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        city = str(kwargs.get("city", "")).strip()
        country_code = str(kwargs.get("country_code", "")).strip()
        units = str(kwargs.get("units", "metric")).strip() or "metric"
        lang = str(kwargs.get("lang", "en")).strip() or "en"

        if not city:
            return {"ok": False, "error": "Missing required parameter: city"}

        if units not in {"metric", "imperial", "standard"}:
            return {
                "ok": False,
                "error": "Invalid units. Use metric, imperial, or standard.",
            }

        query_location = city
        if country_code:
            query_location = f"{city},{country_code}"

        return {
            "ok": True,
            "city": city,
            "country_code": country_code,
            "units": units,
            "lang": lang,
            "query_location": query_location,
        }

    def _fetch(self, url: str) -> str:
        req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=self.timeout_seconds) as response:
            return response.read().decode("utf-8", errors="replace")


class GetCurrentWeatherTool(_OpenWeatherBaseTool):
    """Fetch current weather details for a city via OpenWeatherMap."""

    name = "get_current_weather"
    description = "Get current weather for a location using OpenWeatherMap."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, for example London",
            },
            "country_code": {
                "type": "string",
                "description": "Optional 2-letter country code, for example GB",
            },
            "units": {
                "type": "string",
                "description": "Temperature units: metric, imperial, or standard",
                "enum": ["metric", "imperial", "standard"],
                "default": "metric",
            },
            "lang": {
                "type": "string",
                "description": "Optional response language, defaults to en",
                "default": "en",
            },
        },
        "required": ["city"],
    }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = self._validated_query(kwargs)
        if not query.get("ok"):
            return query

        response = await self._request_json(
            self.current_base_url,
            {
                "q": query["query_location"],
                "units": query["units"],
                "lang": query["lang"],
            },
        )
        if not response.get("ok"):
            return response

        payload = response.get("payload", {})

        weather_items = payload.get("weather", [])
        weather_summary = weather_items[0] if weather_items else {}
        main_data = payload.get("main", {})
        wind_data = payload.get("wind", {})
        sys_data = payload.get("sys", {})

        return {
            "ok": True,
            "provider": "openweathermap",
            "query": {
                "city": query["city"],
                "country_code": query["country_code"] or None,
                "units": query["units"],
                "lang": query["lang"],
            },
            "location": {
                "name": payload.get("name"),
                "country": sys_data.get("country"),
                "lat": payload.get("coord", {}).get("lat"),
                "lon": payload.get("coord", {}).get("lon"),
            },
            "weather": {
                "main": weather_summary.get("main"),
                "description": weather_summary.get("description"),
                "icon": weather_summary.get("icon"),
            },
            "temperature": {
                "current": main_data.get("temp"),
                "feels_like": main_data.get("feels_like"),
                "min": main_data.get("temp_min"),
                "max": main_data.get("temp_max"),
                "humidity": main_data.get("humidity"),
                "pressure": main_data.get("pressure"),
                "units": query["units"],
            },
            "wind": {
                "speed": wind_data.get("speed"),
                "deg": wind_data.get("deg"),
            },
            "clouds": payload.get("clouds", {}).get("all"),
            "visibility": payload.get("visibility"),
            "timestamp": payload.get("dt"),
            "raw": payload,
        }


class GetFutureWeatherTool(_OpenWeatherBaseTool):
    """Fetch short-term weather forecast via OpenWeatherMap forecast API."""

    name = "get_future_weather"
    description = "Get up to 5-day weather forecast (3-hour intervals) for a location."
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "City name, for example London",
            },
            "country_code": {
                "type": "string",
                "description": "Optional 2-letter country code, for example GB",
            },
            "units": {
                "type": "string",
                "description": "Temperature units: metric, imperial, or standard",
                "enum": ["metric", "imperial", "standard"],
                "default": "metric",
            },
            "lang": {
                "type": "string",
                "description": "Optional response language, defaults to en",
                "default": "en",
            },
            "count": {
                "type": "integer",
                "description": "Number of forecast entries to return (1-40), each entry is 3 hours.",
                "minimum": 1,
                "maximum": 40,
                "default": 8,
            },
        },
        "required": ["city"],
    }

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        query = self._validated_query(kwargs)
        if not query.get("ok"):
            return query

        count_raw = kwargs.get("count", 8)
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            return {
                "ok": False,
                "error": "Invalid count. Use an integer between 1 and 40.",
            }

        if count < 1 or count > 40:
            return {
                "ok": False,
                "error": "Invalid count. Use an integer between 1 and 40.",
            }

        response = await self._request_json(
            self.forecast_base_url,
            {
                "q": query["query_location"],
                "units": query["units"],
                "lang": query["lang"],
                "cnt": count,
            },
        )
        if not response.get("ok"):
            return response

        payload = response.get("payload", {})
        city_info = payload.get("city", {})
        entries = payload.get("list", [])

        forecast: list[dict[str, Any]] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            weather_items = item.get("weather", [])
            weather_summary = weather_items[0] if weather_items else {}
            main_data = item.get("main", {})
            wind_data = item.get("wind", {})
            forecast.append(
                {
                    "timestamp": item.get("dt"),
                    "datetime": item.get("dt_txt"),
                    "weather": {
                        "main": weather_summary.get("main"),
                        "description": weather_summary.get("description"),
                        "icon": weather_summary.get("icon"),
                    },
                    "temperature": {
                        "current": main_data.get("temp"),
                        "feels_like": main_data.get("feels_like"),
                        "min": main_data.get("temp_min"),
                        "max": main_data.get("temp_max"),
                        "humidity": main_data.get("humidity"),
                        "pressure": main_data.get("pressure"),
                        "units": query["units"],
                    },
                    "wind": {
                        "speed": wind_data.get("speed"),
                        "deg": wind_data.get("deg"),
                    },
                    "clouds": item.get("clouds", {}).get("all"),
                    "visibility": item.get("visibility"),
                    "precipitation_probability": item.get("pop"),
                }
            )

        return {
            "ok": True,
            "provider": "openweathermap",
            "query": {
                "city": query["city"],
                "country_code": query["country_code"] or None,
                "units": query["units"],
                "lang": query["lang"],
                "count": count,
            },
            "location": {
                "name": city_info.get("name"),
                "country": city_info.get("country"),
                "lat": city_info.get("coord", {}).get("lat"),
                "lon": city_info.get("coord", {}).get("lon"),
                "timezone": city_info.get("timezone"),
                "sunrise": city_info.get("sunrise"),
                "sunset": city_info.get("sunset"),
            },
            "forecast": forecast,
            "raw": payload,
        }
