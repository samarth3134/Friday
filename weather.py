"""Weather via Open-Meteo (https://open-meteo.com) — open-source, key-free API."""

from datetime import date

import requests

from config import WEATHER_CITY

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes returned by Open-Meteo.
WMO_CONDITIONS = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall", 77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}
WET_CODES = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99}


def _city(city):
    selected_city = city or WEATHER_CITY
    return selected_city.strip() if isinstance(selected_city, str) else ""


def _get(url, params):
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def _geocode(city):
    data = _get(GEOCODING_URL, {"name": city, "count": 1, "language": "en", "format": "json"})
    results = data.get("results") or []
    if not results:
        return None
    first = results[0]
    return {
        "name": first.get("name", city),
        "latitude": first.get("latitude"),
        "longitude": first.get("longitude"),
        "timezone": first.get("timezone", "auto"),
    }


def _load(city):
    """Resolve the city and fetch current + daily data in one request pair."""
    location = _geocode(city)
    if not location:
        return None, None
    data = _get(FORECAST_URL, {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "forecast_days": 6,
        # Ask the API to return days in the city's own timezone.
        "timezone": "auto",
    })
    return location, data


def _condition_text(code):
    try:
        return WMO_CONDITIONS.get(int(code), "unknown conditions")
    except (TypeError, ValueError):
        return "unknown conditions"


def _wind_text(speed):
    if speed < 8:
        return "Wind is light"
    if speed < 18:
        return "Wind is moderate"
    return "Wind is strong"


def get_weather(city=WEATHER_CITY):
    city = _city(city)
    if not city:
        return "Tell me which city to check, or set WEATHER_CITY in config.py."

    try:
        location, data = _load(city)
        if not location:
            return f"I could not find the city {city}."
        current = data.get("current") or {}
        temp = round(current.get("temperature_2m", 0))
        humidity = round(current.get("relative_humidity_2m", 0))
        condition = _condition_text(current.get("weather_code"))
        wind = current.get("wind_speed_10m", 0)

        return (
            f"It's {temp} degrees and {condition} in {location['name']}. "
            f"Humidity is {humidity} percent. {_wind_text(wind)} at {round(wind)} miles per hour."
        )
    except Exception:
        return "I could not get the weather right now."


def get_forecast(city=WEATHER_CITY):
    city = _city(city)
    if not city:
        return "Tell me which city to check, or set WEATHER_CITY in config.py."

    try:
        location, data = _load(city)
        if not location:
            return f"I could not find the city {city}."

        daily = data.get("daily") or {}
        times = list(daily.get("time") or [])[:5]
        codes = list(daily.get("weather_code") or [])
        highs = list(daily.get("temperature_2m_max") or [])
        lows = list(daily.get("temperature_2m_min") or [])

        summaries = []
        for index, day in enumerate(times):
            code = codes[index] if index < len(codes) else None
            low = round(lows[index]) if index < len(lows) else 0
            high = round(highs[index]) if index < len(highs) else 0
            weekday = date.fromisoformat(day).strftime("%A")
            summaries.append(f"{weekday}: {_condition_text(code)}, low {low}, high {high} degrees Fahrenheit")

        if not summaries:
            return "I could not find a forecast for that city."

        return f"Here is the 5 day forecast for {location['name']}: " + "; ".join(summaries) + "."
    except Exception:
        return "I could not get the forecast right now."


def should_bring_jacket(city=WEATHER_CITY):
    city = _city(city)
    if not city:
        return "Tell me which city to check, or set WEATHER_CITY in config.py."

    try:
        location, data = _load(city)
        if not location:
            return f"I could not find the city {city}."

        current = data.get("current") or {}
        temp = current.get("temperature_2m", 0)
        code = current.get("weather_code")
        condition = _condition_text(code)
        city_name = location["name"]

        if temp <= 60:
            return f"Yes, bring a jacket in {city_name}. It's only {round(temp)} degrees."

        if code in WET_CODES:
            return f"Yes, bring a jacket in {city_name}. It looks wet outside with {condition}."

        return f"No, you probably do not need a jacket in {city_name}. It's {round(temp)} degrees with {condition}."
    except Exception:
        return "I could not check whether you need a jacket right now."
