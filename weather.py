from collections import defaultdict
from datetime import datetime, timedelta, timezone

import requests

from config import OPENWEATHER_API_KEY, WEATHER_CITY


CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


def _city(city):
    selected_city = city or WEATHER_CITY
    return selected_city.strip() if isinstance(selected_city, str) else ""


def _has_weather_config(city):
    if not OPENWEATHER_API_KEY:
        return False, "I need an OpenWeatherMap API key before I can check the weather."
    if not city:
        return False, "Tell me which city to check, or set WEATHER_CITY in config.py."
    return True, ""


def _get(url, city):
    response = requests.get(
        url,
        params={
            "q": city,
            "appid": OPENWEATHER_API_KEY,
            "units": "imperial",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _wind_text(speed):
    if speed < 8:
        return "Wind is light"
    if speed < 18:
        return "Wind is moderate"
    return "Wind is strong"


def _condition_text(weather):
    if not weather:
        return "unknown conditions"
    return weather[0].get("description", "unknown conditions")


def get_weather(city=WEATHER_CITY):
    city = _city(city)
    ready, message = _has_weather_config(city)
    if not ready:
        return message

    try:
        data = _get(CURRENT_URL, city)
        temp = round(data["main"]["temp"])
        humidity = data["main"]["humidity"]
        condition = _condition_text(data.get("weather"))
        wind = data.get("wind", {}).get("speed", 0)

        return (
            f"It's {temp} degrees and {condition} in {data.get('name', city)}. "
            f"Humidity is {humidity} percent. {_wind_text(wind)} at {round(wind)} miles per hour."
        )
    except Exception:
        return "I could not get the weather right now."


def get_forecast(city=WEATHER_CITY):
    city = _city(city)
    ready, message = _has_weather_config(city)
    if not ready:
        return message

    try:
        data = _get(FORECAST_URL, city)
        daily = defaultdict(list)
        # OpenWeather reports the city's UTC offset in seconds; group forecast
        # days in city time rather than server-local time.
        tz_offset = data.get("city", {}).get("timezone")
        tz = timezone(timedelta(seconds=tz_offset)) if isinstance(tz_offset, (int, float)) else None

        for item in data.get("list", []):
            if tz:
                day = datetime.fromtimestamp(item["dt"], tz).strftime("%A")
            else:
                day = datetime.fromtimestamp(item["dt"]).strftime("%A")
            daily[day].append(item)

        summaries = []
        for day, entries in list(daily.items())[:5]:
            temps = [entry["main"]["temp"] for entry in entries]
            conditions = [_condition_text(entry.get("weather")) for entry in entries]
            condition = max(set(conditions), key=conditions.count)
            low = round(min(temps))
            high = round(max(temps))
            summaries.append(f"{day}: {condition}, low {low}, high {high} degrees Fahrenheit")

        if not summaries:
            return "I could not find a forecast for that city."

        city_name = data.get("city", {}).get("name", city)
        return f"Here is the 5 day forecast for {city_name}: " + "; ".join(summaries) + "."
    except Exception:
        return "I could not get the forecast right now."


def should_bring_jacket(city=WEATHER_CITY):
    city = _city(city)
    ready, message = _has_weather_config(city)
    if not ready:
        return message

    try:
        data = _get(CURRENT_URL, city)
        temp = data["main"]["temp"]
        condition = _condition_text(data.get("weather")).lower()
        rain = data.get("rain", {}).get("1h", 0) or data.get("rain", {}).get("3h", 0)
        city_name = data.get("name", city)

        if temp <= 60:
            return f"Yes, bring a jacket in {city_name}. It's only {round(temp)} degrees."

        if rain or "rain" in condition or "drizzle" in condition or "thunderstorm" in condition:
            return f"Yes, bring a jacket in {city_name}. It looks wet outside with {condition}."

        return f"No, you probably do not need a jacket in {city_name}. It's {round(temp)} degrees with {condition}."
    except Exception:
        return "I could not check whether you need a jacket right now."
