import base64
from email.mime.text import MIMEText
from pathlib import Path

from config import GMAIL_CREDENTIALS_PATH

try:
    import whatsapp_desktop
except Exception:
    # Desktop-only dependencies must not prevent independent Gmail use.
    whatsapp_desktop = None

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]
GMAIL_TOKEN_PATH = "gmail_token.json"


def _print_gmail_setup(error=None):
    if Path(GMAIL_TOKEN_PATH).exists():
        print("Gmail: stored token was rejected — the app will open the browser for re-authorization.")
        print("Approve the Google permission screen; if it fails repeatedly, delete gmail_token.json and retry.")
    else:
        print("Gmail setup needed:")
        print(f"1. Put your OAuth client credentials at {GMAIL_CREDENTIALS_PATH}.")
        print("2. Install google-api-python-client, google-auth-oauthlib, and google-auth-httplib2.")
        print("3. Run a Gmail function again and complete the browser OAuth flow.")
    if error:
        print(f"Gmail error: {error}")


def _gmail_service():
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        token_path = Path(GMAIL_TOKEN_PATH)
        credentials_path = Path(GMAIL_CREDENTIALS_PATH)

        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

        if not creds or not creds.valid:
            refreshed = False
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    refreshed = bool(creds and creds.valid)
                except Exception as refresh_error:
                    print(f"Stored Gmail token could not be refreshed ({refresh_error}); re-authorization will be requested.")
            if not refreshed:
                if not credentials_path.exists():
                    raise FileNotFoundError(f"Missing {GMAIL_CREDENTIALS_PATH}")
                flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GMAIL_SCOPES)
                creds = flow.run_local_server(port=0)

            token_path.write_text(creds.to_json(), encoding="utf-8")

        return build("gmail", "v1", credentials=creds), None
    except Exception as error:
        _print_gmail_setup(error)
        return None, "I could not connect to Gmail. Please check the setup instructions in the console."


def _get_header(headers, name):
    for header in headers:
        if header.get("name", "").lower() == name.lower():
            return header.get("value", "")
    return ""


def _decode_body(data):
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")


def _extract_body(payload):
    body = _decode_body(payload.get("body", {}).get("data"))
    if body:
        return body

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            body = _decode_body(part.get("body", {}).get("data"))
            if body:
                return body
        nested = _extract_body(part)
        if nested:
            return nested

    return ""


def _gmail_message(service, message_id, full=False):
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full" if full else "metadata",
        metadataHeaders=["From", "Subject"],
    ).execute()
    payload = message.get("payload", {})
    headers = payload.get("headers", [])
    return {
        "sender": _get_header(headers, "From"),
        "subject": _get_header(headers, "Subject"),
        "snippet": message.get("snippet", ""),
        "body": _extract_body(payload) if full else "",
    }


def _ensure_whatsapp():
    if whatsapp_desktop is None:
        return None, "WhatsApp Desktop is unavailable. Check its desktop dependencies."
    whatsapp_desktop._start()
    return True, None


def wa_get_unread():
    if whatsapp_desktop is None:
        return "WhatsApp Desktop is unavailable. Check its desktop dependencies."
    return whatsapp_desktop.wa_get_unread()


def wa_read_chat(contact_name, n=10):
    if whatsapp_desktop is None:
        return "WhatsApp Desktop is unavailable. Check its desktop dependencies."
    return whatsapp_desktop.wa_read_chat(contact_name, n)


def wa_send(contact_name, message):
    if whatsapp_desktop is None:
        return "WhatsApp Desktop is unavailable. Check its desktop dependencies."
    return whatsapp_desktop.wa_send(contact_name, message)


def gmail_get_unread(n=5):
    service, error = _gmail_service()
    if error:
        return error

    try:
        result = service.users().messages().list(userId="me", q="is:unread", maxResults=int(n)).execute()
        messages = result.get("messages", [])
        if not messages:
            return "You have no unread emails."

        lines = []
        for item in messages:
            message = _gmail_message(service, item["id"])
            lines.append(f"From {message['sender']}, subject {message['subject']}. {message['snippet']}")

        return "Unread emails: " + "; ".join(lines) + "."
    except Exception:
        return "I could not get unread emails."


def gmail_read(subject_or_sender):
    service, error = _gmail_service()
    if error:
        return error

    try:
        query = str(subject_or_sender).strip()
        result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = result.get("messages", [])
        if not messages:
            return f"I could not find an email matching {query}."

        message = _gmail_message(service, messages[0]["id"], full=True)
        body = message["body"] or message["snippet"]
        return f"Email from {message['sender']}, subject {message['subject']}: {body}"
    except Exception:
        return "I could not read that email."


def gmail_send(to, subject, body):
    service, error = _gmail_service()
    if error:
        return error

    try:
        email = MIMEText(body)
        email["to"] = to
        email["subject"] = subject
        raw = base64.urlsafe_b64encode(email.as_bytes()).decode("utf-8")
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Sent email to {to} with subject {subject}."
    except Exception:
        return f"I could not send the email to {to}."


def gmail_search(query):
    service, error = _gmail_service()
    if error:
        return error

    try:
        result = service.users().messages().list(userId="me", q=str(query), maxResults=10).execute()
        messages = result.get("messages", [])
        if not messages:
            return f"I could not find emails matching {query}."

        lines = []
        for item in messages:
            message = _gmail_message(service, item["id"])
            lines.append(f"From {message['sender']}, subject {message['subject']}. {message['snippet']}")

        return "Matching emails: " + "; ".join(lines) + "."
    except Exception:
        return "I could not search Gmail."
