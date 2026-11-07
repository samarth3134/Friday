import time
from datetime import datetime

# The dashboard timer refreshes every second; external calls (weather, calendar,
# Gmail, tasks, music) are expensive, so reuse a status snapshot for a minute.
STATUS_CACHE_TTL_SECONDS = 60
_cache = {"stamp": 0.0, "status": None}


def clear_status_cache():
    _cache["stamp"] = 0.0
    _cache["status"] = None


def _import(module_name):
    try:
        return __import__(module_name)
    except Exception:
        return None


def _call(module_name, function_name, fallback, *args):
    module = _import(module_name)
    if not module:
        return fallback

    try:
        return getattr(module, function_name)(*args)
    except Exception:
        return fallback


def _count_from_spoken(text):
    if not isinstance(text, str):
        return text

    lowered = text.lower()
    if "no unread" in lowered:
        return 0
    if "could not" in lowered or "setup" in lowered or "connect" in lowered:
        return text

    if ":" not in text:
        return text

    items = [item.strip() for item in text.split(":", 1)[1].strip(" .").split(";") if item.strip()]
    return len(items)


def _recent_memory():
    memory = _import("memory")
    if not memory:
        return []

    try:
        recent = memory.get_recent(5)
    except Exception:
        return []

    snippets = []
    for item in recent:
        if isinstance(item, dict):
            user = item.get("user", "")
            friday = item.get("friday", "")
            snippet = f"User: {user} | Friday: {friday}".strip()
        else:
            snippet = str(item)

        if snippet:
            snippets.append(snippet[:220])

    return snippets


def get_status():
    now = time.monotonic()
    if _cache["status"] is not None and now - _cache["stamp"] < STATUS_CACHE_TTL_SECONDS:
        return dict(_cache["status"])

    now_clock = datetime.now()
    unread_email = _call("messaging", "gmail_get_unread", "Email is unavailable.", 5)
    # WhatsApp currently exposes only UI automation, not a passive unread API.
    # A timer refresh must never activate another app or send keystrokes.
    unread_whatsapp = "Unread count unavailable through desktop automation."
    wakeword = _import("wakeword")

    status = {
        "current_time": now_clock.strftime("%I:%M:%S %p").lstrip("0"),
        "date": now_clock.strftime("%A, %B %d, %Y"),
        "weather": _call("weather", "get_weather", "Weather is unavailable."),
        "todays_tasks": _call("tasks", "list_tasks", "Tasks are unavailable.", "today"),
        "todays_calendar_events": _call("calendar_integration", "get_today", "Calendar is unavailable."),
        "unread_email_count": _count_from_spoken(unread_email),
        "unread_whatsapp_count": _count_from_spoken(unread_whatsapp),
        "now_playing": _call("music", "now_playing", "Music is unavailable."),
        "friday_state": getattr(wakeword, "STATE", "idle") if wakeword else "idle",
        "recent_memory_snippets": _recent_memory(),
    }
    _cache["stamp"] = now
    _cache["status"] = status
    return dict(status)
