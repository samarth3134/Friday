import re
from datetime import date, datetime, timedelta
import requests
import config

OLLAMA_URL = "http://localhost:11434/api/generate"
SYSTEM_PROMPT = getattr(
    config,
    "SYSTEM_PROMPT",
    "You are Friday, a helpful local AI assistant. Be clear, practical, and concise.",
)


def _safe_import(module_name):
    try:
        return __import__(module_name)
    except Exception:
        return None


def _memory_context(text):
    memory = _safe_import("memory")
    if not memory:
        return ""
    try:
        results = memory.search_memory(text)
    except Exception:
        return ""
    lines = []
    for item in results:
        if isinstance(item, dict):
            lines.append(item.get("text", ""))
        else:
            lines.append(str(item))
    return "\n".join(line for line in lines if line)


def _save_exchange(user_text, friday_response):
    memory = _safe_import("memory")
    if not memory:
        return
    try:
        memory.save_conversation(user_text, friday_response)
    except Exception:
        pass


def _save_memory(text, memory_type="fact"):
    memory = _safe_import("memory")
    if not memory:
        return "I could not access memory right now."
    try:
        memory.save_memory(text, {"type": memory_type})
        return "I will remember that."
    except Exception:
        return "I could not save that memory right now."


def _system_prompt_for(intent):
    behavior = {
        "casual": "For casual replies, answer in at most two lines and be witty.",
        "joke": "For jokes, answer in at most two lines and be witty.",
        "research": "For research, be thorough, structured, and cite uncertainty clearly.",
        "task": "For task confirmations, be brief and clear.",
    }.get(intent, "Match your length to the complexity of the request.")
    return (
        f"{SYSTEM_PROMPT}\n"
        f"Always address the user as {config.USER_NAME}.\n"
        f"{behavior}"
    )


def _ollama(user_text, intent="casual", context=""):
    prompt = (
        f"{_system_prompt_for(intent)}\n\n"
        f"Relevant memory:\n{context or 'No relevant memory found.'}\n\n"
        f"User message:\n{user_text}\n\n"
        "Friday response:"
    )
    try:
        response = requests.post(
            OLLAMA_URL,
            json={"model": config.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return answer or f"I am here, {config.USER_NAME}."
    except Exception:
        return f"I could not reach Ollama right now, {config.USER_NAME}."


def _after_keyword(text, keywords):
    lowered = text.lower()
    for keyword in keywords:
        index = lowered.find(keyword)
        if index >= 0:
            return text[index + len(keyword):].strip(" :.-")
    return text.strip()


def _extract_quoted_or_tail(text, keywords):
    quoted = re.findall(r'"([^"]+)"|' + r"'([^']+)'", text)
    if quoted:
        return next(part for match in quoted for part in match if part)
    return _after_keyword(text, keywords)


def _extract_path(text):
    lowered = text.lower()

    # explicit drive paths in quotes
    quoted = re.findall(r'"([^"]+)"|' + r"'([^']+)'", text)
    if quoted:
        return next(part for match in quoted for part in match if part).strip()

    # explicit path pattern like D:/something
    path_match = re.search(r"([A-Za-z]:[\\/][^\n\r,?!]*)", text)
    if path_match:
        return path_match.group(1).strip(" .")

    # natural language path hints
    if "d drive" in lowered or "d:" in lowered:
        if "project" in lowered:
            return "D:/projects"
        return "D:/"
    if "project" in lowered:
        return "D:/projects"
    if "desktop" in lowered:
        return "C:/Users/" + getattr(config, "WINDOWS_USER", "Samarth") + "/Desktop"
    if "download" in lowered:
        return "C:/Users/" + getattr(config, "WINDOWS_USER", "Samarth") + "/Downloads"
    if "document" in lowered:
        return "C:/Users/" + getattr(config, "WINDOWS_USER", "Samarth") + "/Documents"

    # fallback: extract tail after prepositions
    tail = _after_keyword(text, [
        "look at my files in", "look at my files", "show my files in",
        "show my files", "what's in", "what is in", "contents of",
        "elements in", "open folder", "list folder", "list directory",
        "show folder", "show me", "what folders are in", "what files are in",
        "what folders", "what files", "names of files in",
        "names of folders in", "list", "see my", "check my",
    ])
    return tail if tail and tail != text.strip() else "D:/projects"


def _extract_file_search_term(text):
    quoted = re.findall(r'"([^"]+)"|' + r"'([^']+)'", text)
    if quoted:
        return next(part for match in quoted for part in match if part).strip()
    term = _after_keyword(text, [
        "find file named", "find file", "search file named",
        "search file", "locate file named", "locate file",
    ])
    return term.strip() if term else text.strip()


# ── INTENT CLASSIFIER ──────────────────────────────────────────────────────────
# Pure keyword matching — no Ollama, no hallucination possible.

def _has_phrase(text, phrases):
    """Match complete words/phrases, not fragments inside other words."""
    return any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text)
               for phrase in phrases)


def classify_intent(text):
    t = re.sub(r"\s+", " ", text.lower()).strip()
    command = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", t)

    # Explicit file commands take priority, even if the path contains a service name.
    file_commands = (
        (r"(?:find|search|locate) file\b", "file_search"),
        (r"(?:read file|open file and read|summarize file)\b", "file_read"),
        (r"(?:open|launch) file\b", "file_open"),
        (r"(?:delete|remove|trash) file\b", "file_delete"),
        (r"(?:write|create|save) file\b|make a file\b", "file_write"),
    )
    for pattern, intent in file_commands:
        if re.match(pattern, command):
            return intent

    if re.match(r"(?:remember that|save this|don't forget)\b", command):
        return "memory_save"
    if _has_phrase(t, ["what did i", "recall", "do you remember"]):
        return "memory_recall"

    # Action prefixes identify the service before inspecting titles or message bodies.
    service_commands = (
        (r"(?:add|new|complete|finish|delete|remove) task\b|remind me to\b|todo\b", "task"),
        (r"(?:send|read|search|find) (?:email|mail)\b", "email"),
        (r"(?:send |read )?(?:whatsapp|whats app)\b", "whatsapp"),
        (r"(?:create|add|delete|remove) event\b|schedule\b", "calendar"),
    )
    for pattern, intent in service_commands:
        if re.match(pattern, command):
            return intent

    # Listing only implies files when a directory/file target is present.
    listing = _has_phrase(t, ["list", "show", "what's in", "what is in", "contents",
                              "elements", "look at", "see my", "check my", "names of",
                              "what folders", "what files", "what's inside", "inside my"])
    file_target = bool(re.search(r"\b(?:files?|folders?|director(?:y|ies)|desktop|downloads|documents|projects?|drive)\b", t)
                       or re.search(r"\b[a-z]:[\\/]", t))
    if listing and file_target:
        return "file_list"

    if _has_phrase(t, ["open app", "launch app", "close app", "running apps"]):
        return "system_app"
    if re.match(r"close\s+", command):
        return "system_app"
    if _has_phrase(t, ["lock screen", "screenshot", "brightness", "click at", "type this", "hotkey"]):
        return "system_screen"
    if _has_phrase(t, ["shutdown", "restart", "sleep mode", "cancel shutdown"]):
        return "system_power"

    # Service-specific requests precede generic controls such as volume.
    if _has_phrase(t, ["weather", "temperature", "forecast", "jacket", "rain today"]):
        return "weather"
    if _has_phrase(t, ["task", "tasks", "remind", "todo", "to do", "overdue"]):
        return "task"
    if _has_phrase(t, ["play", "pause music", "resume music", "skip song", "next song",
                       "music", "song", "songs", "playlist", "now playing"]):
        return "music"
    if _has_phrase(t, ["email", "emails", "gmail", "inbox", "mail"]):
        return "email"
    if _has_phrase(t, ["whatsapp", "whats app"]):
        return "whatsapp"
    if _has_phrase(t, ["calendar", "schedule", "event", "events", "meeting today",
                       "what do i have", "appointments"]):
        return "calendar"
    if _has_phrase(t, ["screen", "analyze image", "identify object", "ocr", "explain error"]):
        return "vision"
    if _has_phrase(t, ["volume", "mute", "unmute"]):
        return "system_volume"
    if re.match(r"(?:open|launch)\s+", command):
        return "system_app"
    if _has_phrase(t, ["search for", "look up", "google", "news about", "latest on"]):
        return "search"
    if _has_phrase(t, ["explain", "how does", "what is", "why does", "tell me about"]):
        return "research"
    return "casual"


# ── ROUTERS ────────────────────────────────────────────────────────────────────

def _route_search(user_text, intent, memory_context):
    search = _safe_import("search")
    if not search:
        return "Search is not available right now."
    query = _after_keyword(user_text, ["research", "search for", "look up", "latest", "news about"])
    if "news" in user_text.lower():
        web_context = search.news_search(query)
    else:
        web_context = search.web_search(query)
    context = f"{memory_context}\n\nWeb context:\n{web_context}".strip()
    return _ollama(user_text, intent, context)


def _parse_command_date(value):
    value = value.strip().lower()
    if value in {"today", "tomorrow"}:
        return (date.today() + timedelta(days=value == "tomorrow")).isoformat()
    return date.fromisoformat(value).isoformat()


def _route_task(user_text):
    tasks = _safe_import("tasks")
    if not tasks:
        return "Tasks are not available right now."
    command = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", user_text.strip(), flags=re.I)
    lower = command.lower()

    # Read actions must not intercept titles such as "add task finish report".
    if re.match(r"(?:list|show|what are my)\b", lower) or lower in {"tasks", "overdue tasks"}:
        if _has_phrase(lower, ["overdue"]):
            return tasks.get_overdue()
        task_filter = next((value for value in ("done", "today", "pending")
                            if _has_phrase(lower, [value])), "all")
        return tasks.list_tasks(task_filter)
    if lower == "overdue":
        return tasks.get_overdue()
    action = re.match(r"^(complete|done|finish|delete|remove)\s+(?:task\s+)?(.+)$", command, re.I)
    if action:
        identifier = action.group(2).strip().strip("\"'")
        if action.group(1).lower() in {"delete", "remove"}:
            return tasks.delete_task(identifier)
        return tasks.complete_task(identifier)

    title = re.sub(r"^(?:add task|new task|remind me to|todo|task)\s*", "", command, flags=re.I).strip()
    options = {}
    for _ in range(2):
        priority = re.search(r"\s+priority\s+(low|normal|high)\s*$", title, re.I)
        due = re.search(r"\s+due(?: on)?\s+(\d{4}-\d{2}-\d{2}|today|tomorrow)\s*$", title, re.I)
        if priority:
            options["priority"] = priority.group(1).lower()
            title = title[:priority.start()].strip()
        elif due:
            try:
                options["due_date"] = _parse_command_date(due.group(1))
            except ValueError:
                return "Tell me a valid due date (YYYY-MM-DD, today, or tomorrow)."
            title = title[:due.start()].strip()
        else:
            break
    return tasks.add_task(title, **options)


def _route_files(user_text, intent):
    filesystem = _safe_import("filesystem")
    if not filesystem:
        return "File tools are not available right now."

    if intent == "file_search":
        return filesystem.find_file(_extract_file_search_term(user_text))
    if intent == "file_read":
        return filesystem.read_file(_extract_quoted_or_tail(user_text, ["read file", "show file", "summarize file"]))
    if intent == "file_open":
        return filesystem.open_file(_extract_quoted_or_tail(user_text, ["open file", "launch file"]))
    if intent == "file_list":
        path = _extract_path(user_text)
        print(f"[FILE_LIST] Listing real directory: {path}")
        result = filesystem.list_dir(path)
        # Return real result directly — no Ollama involvement
        return result
    if intent == "file_delete":
        return filesystem.delete_file(_extract_quoted_or_tail(user_text, ["delete file", "remove file"]))
    if intent == "file_write":
        match = re.search(
            r"(?:write|save|create) file ['\"]?([^'\"]+)['\"]?\s+(?:with|as|content)\s+(.+)",
            user_text, re.I | re.S,
        )
        if not match:
            return "Tell me the file path and content to write."
        return filesystem.write_file(match.group(1).strip(), match.group(2).strip())

    return "I am not sure which file action to take."


def _route_system(user_text, intent):
    system = _safe_import("system_control")
    if not system:
        return "System controls are not available right now."
    lower = user_text.lower()

    if intent == "system_volume":
        if "unmute" in lower:
            return system.unmute()
        if "mute" in lower:
            return system.mute()
        level = re.search(r"\d+", user_text)
        return system.set_volume(int(level.group(0)) if level else 50)

    if intent == "system_app":
        if "running" in lower or ("list" in lower and "app" in lower):
            return system.list_running_apps()
        if "close" in lower:
            return system.close_app(_after_keyword(user_text, ["close app", "close"]))
        return system.open_app(_after_keyword(user_text, ["open app", "launch app", "open", "launch"]))

    if intent == "system_screen":
        if "lock" in lower:
            return system.lock_screen()
        if "screenshot" in lower:
            return system.take_screenshot()
        if "brightness" in lower:
            level = re.search(r"\d+", user_text)
            return system.set_brightness(int(level.group(0)) if level else 50)
        if "click" in lower:
            nums = re.findall(r"\d+", user_text)
            return system.click(nums[0], nums[1]) if len(nums) >= 2 else "Tell me x and y to click."
        if "hotkey" in lower:
            keys = _after_keyword(user_text, ["hotkey"]).replace("+", " ").split()
            return system.hotkey(*keys)
        if "type" in lower:
            return system.type_text(_after_keyword(user_text, ["type"]))

    if intent == "system_power":
        delay_match = re.search(r"\d+", user_text)
        delay = int(delay_match.group(0)) if delay_match else 60
        if "cancel" in lower:
            return system.cancel_shutdown()
        if "restart" in lower:
            return system.restart(delay)
        if "sleep" in lower:
            return system.sleep_mode()
        return system.shutdown(delay)

    return "I am not sure which system action to take."


def _route_weather(user_text):
    weather = _safe_import("weather")
    if not weather:
        return "Weather is not available right now."
    lower = user_text.lower()
    city = getattr(config, "WEATHER_CITY", "")
    city_match = re.search(r"\b(?:in|for|at)\s+(.+?)\s*[?.!]*$", user_text, re.I)
    if city_match:
        candidate = re.split(r"\s+(?:today|tomorrow|this week|please)\b", city_match.group(1), maxsplit=1, flags=re.I)[0]
        candidate = candidate.strip(" \"'?.!")
        if candidate.lower() not in {"today", "tomorrow", "this week"} and re.search(r"[^\W\d_]", candidate):
            city = candidate
    if "forecast" in lower:
        return weather.get_forecast(city)
    if "jacket" in lower:
        return weather.should_bring_jacket(city)
    return weather.get_weather(city)


def _filesystem_confirmation_reply(user_text):
    """Route a plain yes/no answer to a pending file mutation, if any."""
    lowered = user_text.lower().strip().strip(".,!?")
    confirm = re.match(r"^(yes|yeah|yep|sure|ok|okay|confirm|confirmed|do it|go ahead|proceed|please do|sounds good)\b", lowered)
    cancel = re.match(r"^(no|nope|nah|cancel|abort|stop|never mind|nevermind|forget it|don.?t|do not)\b", lowered)
    if not confirm and not cancel:
        return None
    filesystem = _safe_import("filesystem")
    if not filesystem:
        return "File tools are not available right now."
    try:
        if not filesystem.has_pending():
            return None
    except Exception:
        return None
    try:
        return filesystem.confirm_pending() if confirm else filesystem.cancel_pending()
    except Exception as error:
        return f"Something went wrong: {error}"


def _route_music(user_text):
    music = _safe_import("music")
    if not music:
        return "Music controls are not available right now."
    lower = user_text.lower()
    if "pause" in lower:
        return music.pause()
    if "resume" in lower:
        return music.resume()
    if "skip" in lower or "next" in lower:
        return music.skip()
    if "previous" in lower or "back" in lower:
        return music.previous()
    if "volume" in lower:
        level = re.search(r"\d+", user_text)
        return music.set_volume(int(level.group(0)) if level else 50)
    if "now playing" in lower or "what is playing" in lower or "what's playing" in lower:
        return music.now_playing()
    if "mood" in lower:
        return music.play_mood(_after_keyword(user_text, ["mood"]))
    # "add X to (the) queue" / "put X on (the) queue" / "add (to|on) (the|my) queue X"
    if re.match(r"^(?:add|put)\b", user_text.strip(), re.I) and re.search(r"\bqueue\b", user_text, re.I):
        match = re.match(r"^(?:add|put)\s+(.+?)\s+(?:to|on)\s+(?:(?:the|my|a)\s+)?queue\s*$", user_text, re.I)
        if not match:
            match = re.match(r"^(?:add|put)\s+(?:to\s+|on\s+)?(?:(?:the|my|a)\s+)?queue\s+(.+)$", user_text, re.I)
        if match:
            return music.add_to_queue(match.group(1).strip(' :.-"'))
        return "Tell me which song to add to the queue."
    if re.search(r"\b(?:clear|empty)\b.*\bqueue\b|\bqueue\b.*\b(?:clear|empty)\b", user_text, re.I):
        return music.clear_queue()
    query = _after_keyword(user_text, ["play music", "play song", "play"])
    return music.play(query)


def _route_calendar(user_text):
    calendar = _safe_import("calendar_integration")
    if not calendar:
        return "Calendar is not available right now."
    command = re.sub(r"^(?:(?:can|could|would) you\s+)?(?:please\s+)?", "", user_text.strip(), flags=re.I)
    lower = command.lower()
    date_pattern = r"(\d{4}-\d{2}-\d{2}|today|tomorrow)"

    # Mutations take precedence over date words and words occurring in titles.
    if re.match(r"(?:delete|remove)\b", lower):
        match = re.fullmatch(r"(?:delete|remove) (?:event )?(.+?)\s+(?:(?:on|for)\s+)?" + date_pattern + r"[.!?]?", command, re.I)
        if not match:
            return "Tell me the event title and date to delete."
        try:
            event_date = _parse_command_date(match.group(2))
        except ValueError:
            return "Tell me a valid event date (YYYY-MM-DD, today, or tomorrow)."
        return calendar.delete_event(match.group(1).strip(), event_date)
    if re.match(r"(?:create|add|schedule)\b", lower):
        match = re.fullmatch(r"(?:create|add|schedule) (?:event )?(.+?)\s+(?:(?:on|for)\s+)?" + date_pattern + r" at (\d{1,2}:\d{2}|\d{1,2}(?::\d{2})?\s*[ap]m)[.!?]?", command, re.I)
        if not match:
            return "Tell me the event title, date (YYYY-MM-DD, today, or tomorrow), and time."
        try:
            event_date = _parse_command_date(match.group(2))
            time_text = re.sub(r"\s+", "", match.group(3).lower())
            time_format = "%I:%M%p" if ":" in time_text else "%I%p"
            if not time_text.endswith(("am", "pm")):
                time_format = "%H:%M"
            event_time = datetime.strptime(time_text, time_format).strftime("%H:%M")
        except ValueError:
            return "Tell me a valid event date and time."
        return calendar.create_event(match.group(1).strip(), event_date, event_time)
    if _has_phrase(lower, ["free"]):
        match = re.search(date_pattern + r"[.!?]?$", lower)
        if not match:
            return "Tell me which date to check for free slots."
        try:
            return calendar.find_free_slots(_parse_command_date(match.group(1)))
        except ValueError:
            return "Tell me a valid date to check for free slots."
    if _has_phrase(lower, ["today", "do i have"]):
        return calendar.get_today()
    if _has_phrase(lower, ["upcoming", "next", "this week"]):
        days = re.search(r"\d+", user_text)
        return calendar.get_upcoming(int(days.group(0)) if days else 7)
    return calendar.get_upcoming()


def _route_messaging(user_text, intent):
    messaging = _safe_import("messaging")
    if not messaging:
        return "Messaging is not available right now."
    lower = user_text.lower()

    if intent == "whatsapp":
        if "unread" in lower:
            return messaging.wa_get_unread()
        if "read" in lower:
            contact = _after_keyword(user_text, ["read whatsapp from", "read chat with", "messages from"])
            return messaging.wa_read_chat(contact)
        match = re.search(r"(?:send whatsapp|message|whatsapp) (?:to )?(.+?):\s*(.+)", user_text, re.I | re.S)
        if not match:
            return "Tell me the WhatsApp contact and message to send."
        return messaging.wa_send(match.group(1).strip(), match.group(2).strip())

    # email
    if "unread" in lower:
        count = re.search(r"\d+", user_text)
        return messaging.gmail_get_unread(int(count.group(0)) if count else 5)
    if "send" in lower:
        match = re.search(r"send (?:email|mail) to (\S+) subject (.+?) body (.+)", user_text, re.I | re.S)
        if not match:
            return "Tell me the recipient, subject, and body."
        return messaging.gmail_send(match.group(1), match.group(2), match.group(3))
    if "read" in lower:
        return messaging.gmail_read(_after_keyword(user_text, ["read email from", "read email", "read mail"]))
    return messaging.gmail_search(_after_keyword(user_text, ["search email", "search mail", "find email"]))


def _route_vision(user_text):
    vision = _safe_import("vision")
    if not vision:
        return "Vision is not available right now."
    lower = user_text.lower()
    if "read text" in lower or "ocr" in lower:
        return vision.read_text_from_screen()
    if "error" in lower:
        return vision.explain_error()
    if "object" in lower:
        return vision.identify_object(_extract_quoted_or_tail(user_text, ["object in", "identify"]))
    if "image" in lower:
        return vision.analyze_image(_extract_quoted_or_tail(user_text, ["image", "photo", "picture"]))
    return vision.analyze_screen()


# ── MAIN ROUTER ────────────────────────────────────────────────────────────────

def route(user_text, intent, memory_context=""):
    if intent in {"search", "research"}:
        return _route_search(user_text, intent, memory_context)
    if intent == "task":
        return _route_task(user_text)
    if intent.startswith("file_"):
        return _route_files(user_text, intent)
    if intent.startswith("system_"):
        return _route_system(user_text, intent)
    if intent == "weather":
        return _route_weather(user_text)
    if intent == "music":
        return _route_music(user_text)
    if intent == "calendar":
        return _route_calendar(user_text)
    if intent in {"whatsapp", "email"}:
        return _route_messaging(user_text, intent)
    if intent == "vision":
        return _route_vision(user_text)
    if intent == "memory_save":
        return _save_memory(user_text, "preference")
    if intent == "memory_recall":
        return memory_context or "I do not remember anything relevant yet."

    # casual / joke / anything else → Ollama only
    return _ollama(user_text, intent, memory_context)


# ── ENTRY POINTS ───────────────────────────────────────────────────────────────

def respond(user_text):
    if not isinstance(user_text, str) or not user_text.strip():
        return f"I did not catch that, {config.USER_NAME}."

    user_text = user_text.strip()
    confirmation = _filesystem_confirmation_reply(user_text)
    if confirmation is not None:
        _save_exchange(user_text, confirmation)
        return confirmation

    intent = classify_intent(user_text)

    # debug print so you can see exactly what's happening
    path_hint = f" [PATH: {_extract_path(user_text)}]" if intent == "file_list" else ""
    print(f"[INTENT: {intent}]{path_hint}")

    memory_context = _memory_context(user_text)

    try:
        response = route(user_text, intent, memory_context)
    except Exception as e:
        response = f"Something went wrong: {e}"

    _save_exchange(user_text, response)
    return response


# aliases so any import style works
def handle(user_text):
    return respond(user_text)

def process(user_text):
    return respond(user_text)

def chat(user_text):
    return respond(user_text)
