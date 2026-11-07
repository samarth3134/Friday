from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config
from config import GMAIL_CREDENTIALS_PATH


SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_PATH = "calendar_token.json"
CALENDAR_ID = "primary"
WORKDAY_START = time(9, 0)
WORKDAY_END = time(17, 0)
CALENDAR_TIMEZONE = getattr(config, "CALENDAR_TIMEZONE", "Asia/Kolkata")


def _calendar_timezone():
    try:
        return ZoneInfo(CALENDAR_TIMEZONE)
    except ZoneInfoNotFoundError:
        # Windows may not ship an IANA database. India's current fixed offset
        # keeps the default usable without silently substituting the host zone.
        if CALENDAR_TIMEZONE in {"Asia/Kolkata", "Asia/Calcutta"}:
            return timezone(timedelta(hours=5, minutes=30), name=CALENDAR_TIMEZONE)
        if CALENDAR_TIMEZONE == "UTC":
            return timezone.utc
        raise ValueError("Install tzdata for the configured calendar timezone")


def _local_datetime(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    zone = _calendar_timezone()
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def _print_auth_help(error=None):
    print("Google Calendar setup needed:")
    print(f"1. Put your OAuth client credentials at {GMAIL_CREDENTIALS_PATH}.")
    print("2. Install google-api-python-client, google-auth-oauthlib, and google-auth-httplib2.")
    print("3. Run this function again and complete the browser OAuth flow.")
    if error:
        print(f"Auth error: {error}")


def _service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        token_path = Path(TOKEN_PATH)
        credentials_path = Path(GMAIL_CREDENTIALS_PATH)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not credentials_path.exists():
                    raise FileNotFoundError(f"Missing {GMAIL_CREDENTIALS_PATH}")
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("calendar", "v3", credentials=creds), None
    except Exception as error:
        _print_auth_help(error)
        return None, "I could not connect to Google Calendar. Please check the setup instructions in the console."


def _parse_date(value):
    if isinstance(value, datetime):
        return value.astimezone(_calendar_timezone()).date() if value.tzinfo else value.date()
    return datetime.fromisoformat(str(value)).date()


def _parse_datetime(date_value, time_value):
    event_date = _parse_date(date_value)
    event_time = datetime.strptime(str(time_value), "%H:%M").time()
    return datetime.combine(event_date, event_time, tzinfo=_calendar_timezone())


def _day_bounds(date_value):
    day = _parse_date(date_value)
    start = datetime.combine(day, time.min, tzinfo=_calendar_timezone())
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=_calendar_timezone())
    return start.isoformat(), end.isoformat()


def _format_time(value):
    if "T" not in value:
        return "all day"
    return _local_datetime(value).strftime("%I:%M %p").lstrip("0")


def _format_event(event):
    title = event.get("summary", "Untitled event")
    start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
    end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
    return f"{title}, from {_format_time(start)} to {_format_time(end)}"


def _events_between(start, end):
    service, error = _service()
    if error:
        return None, error

    events = []
    params = dict(calendarId=CALENDAR_ID, timeMin=start, timeMax=end,
                  singleEvents=True, orderBy="startTime")
    seen_tokens = set()
    while True:
        result = service.events().list(**params).execute()
        events.extend(result.get("items", []))
        next_page = result.get("nextPageToken")
        if not next_page:
            break
        if next_page in seen_tokens:
            raise RuntimeError("Calendar returned a repeated pagination token")
        seen_tokens.add(next_page)
        params["pageToken"] = next_page
    return events, None


def get_today():
    try:
        start, end = _day_bounds(datetime.now(_calendar_timezone()))
        events, error = _events_between(start, end)
        if error:
            return error

        if not events:
            return "You have no events today."

        return "Today you have: " + "; ".join(_format_event(event) for event in events) + "."
    except Exception:
        return "I could not get today's calendar events."


def get_upcoming(days=7):
    try:
        days = max(1, int(days))
        start = datetime.now(_calendar_timezone())
        end = start + timedelta(days=days)
        events, error = _events_between(start.isoformat(), end.isoformat())
        if error:
            return error

        if not events:
            return f"You have no events in the next {days} days."

        return f"In the next {days} days, you have: " + "; ".join(_format_event(event) for event in events) + "."
    except Exception:
        return "I could not get your upcoming calendar events."


def create_event(title, date, time, duration_minutes=60):
    try:
        if not title or not str(title).strip():
            return "Tell me the event title first."

        duration = int(duration_minutes)
        if duration <= 0:
            return "Event duration must be a positive number of minutes."
        start = _parse_datetime(date, time)
        end = start + timedelta(minutes=duration)
        service, error = _service()
        if error:
            return error
        event = {
            "summary": str(title).strip(),
            "start": {"dateTime": start.isoformat(), "timeZone": CALENDAR_TIMEZONE},
            "end": {"dateTime": end.isoformat(), "timeZone": CALENDAR_TIMEZONE},
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return f"Created {title} on {date} at {time} for {duration_minutes} minutes."
    except Exception:
        return "I could not create that calendar event."


def delete_event(title, date):
    service, error = _service()
    if error:
        return error

    try:
        start, end = _day_bounds(date)
        events, lookup_error = _events_between(start, end)
        if lookup_error:
            return lookup_error

        target = str(title).strip().lower()
        matches = [event for event in events if event.get("summary", "").strip().lower() == target]
        if len(matches) > 1:
            return f"There are multiple events named {title} on {date}. Please choose one in your calendar."
        if matches:
            service.events().delete(calendarId=CALENDAR_ID, eventId=matches[0]["id"]).execute()
            return f"Deleted {title} from your calendar."

        return f"I could not find {title} on {date}."
    except Exception:
        return "I could not delete that calendar event."


def find_free_slots(date):
    try:
        day = _parse_date(date)
        start, end = _day_bounds(day)
        events, error = _events_between(start, end)
        if error:
            return error

        zone = _calendar_timezone()
        workday_start = datetime.combine(day, WORKDAY_START, tzinfo=zone)
        end_of_day = datetime.combine(day, WORKDAY_END, tzinfo=zone)
        busy = []
        for event in events:
            if event.get("status") == "cancelled" or event.get("transparency") == "transparent":
                continue
            event_start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date")
            event_end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date")
            if not event_start or not event_end:
                continue
            busy_start = max(_local_datetime(event_start), workday_start)
            busy_end = min(_local_datetime(event_end), end_of_day)
            if busy_end > busy_start:
                busy.append((busy_start, busy_end))

        busy.sort()
        cursor = workday_start
        free_slots = []

        for busy_start, busy_end in busy:
            if busy_start > cursor:
                free_slots.append((cursor, min(busy_start, end_of_day)))
            if busy_end > cursor:
                cursor = busy_end

        if cursor < end_of_day:
            free_slots.append((cursor, end_of_day))

        readable = [
            f"{slot_start.strftime('%I:%M %p').lstrip('0')} to {slot_end.strftime('%I:%M %p').lstrip('0')}"
            for slot_start, slot_end in free_slots
            if slot_end > slot_start
        ]

        if not readable:
            return f"I could not find any free workday slots on {date}."

        return f"Your free slots on {date} are: " + "; ".join(readable) + "."
    except Exception:
        return "I could not find free calendar slots."
