import os
import requests
from datetime import datetime, timedelta, timezone
from new_voice import speak_text
from functools import wraps
import socket
import hashlib

# === Config ===
WEATHER_CACHE = {"forecast": None, "hash": None, "fetched": None}
WEATHER_TTL = timedelta(hours=1)
WATCH_DIR = "watch"
WEATHER_FILE_PATH = os.path.join(WATCH_DIR, "weather.txt")

# === Online check ===
def is_online(host="www.google.com", port=80, timeout=2) -> bool:
    try:
        socket.create_connection((host, port), timeout=timeout)
        return True
    except OSError:
        return False

def requires_online(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_online():
            msg = (
                "Sir, I'm currently offline and cannot access online services. "
                "Please try again once connectivity is restored."
            )
            try:
                speak_text(msg)
            except Exception:
                pass
            return msg
        return func(*args, **kwargs)
    return wrapper

# === Utilities ===
def _hash(txt: str) -> str:
    return hashlib.sha1(txt.encode()).hexdigest()

def write_forecast_to_file(forecast: str, path: str = WEATHER_FILE_PATH):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(forecast)
        print(f"✅ Updated weather file: {path}")
    except Exception as e:
        print(f"❌ Failed to write weather file: {e}")

# === Weather fetch ===
@requires_online
def fetch_weekly_weather() -> str:
    try:
        loc = requests.get("http://ip-api.com/json", timeout=3).json()
        lat, lon = loc["lat"], loc["lon"]
        city, region = loc["city"], loc["regionName"]
    except Exception:
        lat, lon, city, region = 39.3722, -76.9684, "Default Location", "MD"

    point = requests.get(f"https://api.weather.gov/points/{lat},{lon}", timeout=5).json()
    periods = requests.get(point["properties"]["forecast"], timeout=5).json()["properties"]["periods"][:14]

    daily = {}
    for p in periods:
        name = p["name"]
        day_name = name.split()[0]
        if day_name.lower() == "tonight":
            day_name = datetime.now(timezone.utc).strftime("%A") + " Night"
        daily.setdefault(day_name, f"{p['temperature']}{p['temperatureUnit']} – {p['shortForecast']}")

    summary = "; ".join([f"{d}: {s}" for d, s in list(daily.items())[:7]])
    full_forecast = f"7-day forecast for {city}, {region}: {summary}."

    write_forecast_to_file(full_forecast)  # Write to watch/weather.txt
    return full_forecast

# === Cached access ===
def get_cached_weather() -> str:
    now = datetime.now(timezone.utc)
    if WEATHER_CACHE["forecast"] and WEATHER_CACHE["fetched"] and now - WEATHER_CACHE["fetched"] < WEATHER_TTL:
        return WEATHER_CACHE["forecast"]

    fresh = fetch_weekly_weather()
    if _hash(fresh) != WEATHER_CACHE.get("hash"):
        WEATHER_CACHE.update({"forecast": fresh, "hash": _hash(fresh), "fetched": now})
    return WEATHER_CACHE["forecast"]
