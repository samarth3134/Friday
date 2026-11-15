"""Mode system: Fast by default, Think on demand.

Modes live in the user-editable modes.json next to this file. Each mode sets the
model, system prompt, num_ctx, num_predict, whether the reasoning model thinks,
whether memory lookup is allowed ("all" / "personal" / "none"), whether web search
is allowed, the keep_alive value, and how answers are spoken ("short" / "summary").

The active mode is process-local state (it resets to "fast" on startup).
"""
import json
import re
import threading
from pathlib import Path

MODES_FILE = Path(__file__).parent / "modes.json"

DEFAULT_MODES = {
    "version": 1,
    "fast": {
        "model": "qwen3:4b",
        "system": "You are Friday, a terse helpful assistant. Answer in one or two short sentences maximum.",
        "num_ctx": 8192,
        "num_predict": 1000,
        "think": False,
        "memory": "personal",
        "web_search": False,
        "keep_alive": "30m",
        "spoken": "short",
    },
    "think": {
        "model": "qwen3:4b",
        "system": "You are Friday, a careful assistant. Think step by step, then answer.",
        "num_ctx": 16384,
        "num_predict": 1536,
        "think": True,
        "memory": "all",
        "web_search": True,
        "keep_alive": "30m",
        "spoken": "summary",
    },
}

DEFAULT_FAST = "fast"
DEFAULT_THINK = "think"

_state = {"active": DEFAULT_FAST}
_lock = threading.RLock()

# Cheap per-question escalation heuristic: no LLM call, only pattern matching.
_ESCALATION_MARKERS = (
    "why", "how come", "why do", "why does", "why is", "should i",
    "compare", "comparison", "plan", "explain", "debug", "analyze", "analyse",
    "evaluate", "pros and cons", "pros & cons", "trade-off", "tradeoff",
    "step by step", "architecture", "design", "what if", "how would",
)
_ESCALATION_LONG = 180

_PERSONAL_MARKER = re.compile(r"\b(my|me|mine|myself|i)\b|\bremember\b", re.I)


def load_modes():
    """Read modes.json, tolerating missing or malformed files."""
    try:
        raw = json.loads(MODES_FILE.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("modes.json must contain a JSON object")
    except Exception:
        return {name: dict(settings) for name, settings in DEFAULT_MODES.items() if name != "version"}

    modes = {}
    version = raw.get("version", 1)
    for name, settings in raw.items():
        if name == "version" or not isinstance(settings, dict):
            continue
        merged = dict(DEFAULT_MODES.get(name, {}))
        merged.update(settings)
        modes[name] = merged
    if DEFAULT_FAST not in modes:
        modes[DEFAULT_FAST] = dict(DEFAULT_MODES["fast"])
    if DEFAULT_THINK not in modes:
        modes[DEFAULT_THINK] = dict(DEFAULT_MODES["think"])
    return modes | {"_version": version}


def _write(modes):
    payload = {"version": 2}
    for name, settings in modes.items():
        if name != "_version":
            payload[name] = settings
    tmp = MODES_FILE.with_suffix(".tmp.json")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(MODES_FILE)


def list_modes():
    modes = load_modes()
    return [name for name in modes if name != "_version"]


def mode_settings(name):
    modes = load_modes()
    return dict(modes.get(name) or modes.get(DEFAULT_FAST))


def active_mode():
    return _state["active"]


def set_active_mode(name):
    with _lock:
        if name not in list_modes():
            return False, f"I do not have a mode called {name}."
        previous = _state["active"]
        _state["active"] = name
        return True, (f"Switched to {name} mode." if previous != name else f"Already in {name} mode.")


def set_to_fast():
    return set_active_mode(DEFAULT_FAST)


def set_to_think():
    return set_active_mode(DEFAULT_THINK)


def is_personal_query(text):
    return bool(_PERSONAL_MARKER.search(text or ""))


def escalation_reason(text):
    """Cheap per-question heuristic. Returns a short reason or None; no LLM call."""
    lowered = (text or "").lower()
    for cue in _ESCALATION_MARKERS:
        pattern = r"\b" + re.escape(cue) + r"\b"
        if re.search(pattern, lowered):
            return cue
    if len(text or "") > _ESCALATION_LONG:
        return "long question"
    return None


def _template(instruction, name):
    instruction = (instruction or "").strip()
    return {
        "model": "qwen3:4b",
        "system": instruction or "Be helpful, concise, and truthful.",
        "num_ctx": 16384,
        "num_predict": 768,
        "think": False,
        "memory": "none",
        "web_search": False,
        "keep_alive": "30m",
        "spoken": "short",
        "custom": True,
        "custom_name": name,
    }


_CREATE_RE = re.compile(
    r"^(?:make|create|add|set up|setup)\s+a\s+mode\s+(?:called|named)\s+([a-zA-Z][\w-]{0,31})(?:\s+that|\s+which|\s+to|\s*[:,-]\s*)?\s*(.*)$",
    re.I | re.S,
)


def create_mode_from_text(text):
    match = _CREATE_RE.match((text or "").strip())
    if not match:
        return None
    name = match.group(1).lower()
    instruction = (match.group(2) or "").strip().rstrip(".")
    if name in {"fast", "think"}:
        return False, f"I already have a {name} mode built in."
    modes = load_modes()
    modes[name] = _template(instruction, name)
    try:
        _write(modes)
    except Exception as exc:
        return False, f"I could not save the {name} mode: {exc}"
    return True, f"Created mode {name}. Switch to it with 'switch to {name}'."


def describe_mode(name=None):
    active = name or _state["active"]
    settings = mode_settings(active)
    return {
        "name": active,
        "model": settings.get("model"),
        "think": bool(settings.get("think")),
        "memory": settings.get("memory"),
        "web_search": bool(settings.get("web_search")),
    }
