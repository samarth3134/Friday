import subprocess
import threading
import time

import pyautogui
import pygetwindow as gw

from config import WHATSAPP_SESSION_PATH

_wa_ready = False
_wa_error = None
_wa_lock = threading.RLock()


def _launch_whatsapp():
    try:
        subprocess.Popen(
            ["shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"],
            shell=True,
        )
        return True
    except Exception:
        return False


def _find_window(attempts=30):
    for _ in range(attempts):
        windows = gw.getWindowsWithTitle("WhatsApp")
        for w in windows:
            if w.visible:
                return w
        time.sleep(0.5)
    return None


def _activate():
    w = _find_window()
    if not w:
        return False
    try:
        w.activate()
        time.sleep(0.3)
        return True
    except Exception:
        return False


def _start_whatsapp_client():
    global _wa_ready, _wa_error

    _wa_ready = False
    _wa_error = None
    if not _launch_whatsapp():
        _wa_error = "Could not launch WhatsApp Desktop."
        return

    # A single polling loop has a total wait budget of ten seconds.
    w = _find_window(attempts=20)
    if w:
        _wa_ready = True
        return

    _wa_error = "WhatsApp window not found after 10 seconds."


def _ensure_whatsapp():
    if _wa_error:
        return None, _wa_error

    if not _wa_ready:
        _start_whatsapp_client()

    if _wa_ready:
        return True, None

    return None, _wa_error or "WhatsApp is not ready yet."


def wa_get_unread():
    ready, error = _ensure_whatsapp()
    if error:
        return error

    with _wa_lock:
        if not _activate():
            return "Could not find WhatsApp window."

        pyautogui.hotkey("ctrl", "1")
        time.sleep(0.5)

        pyautogui.hotkey("ctrl", "shift", "]")
        time.sleep(0.3)

        pyautogui.hotkey("ctrl", "shift", "[")
        time.sleep(0.5)

    return "Unread WhatsApp is available on the main screen. I cannot read it reliably through automation yet."


def wa_read_chat(contact_name, n=10):
    ready, error = _ensure_whatsapp()
    if error:
        return error

    with _wa_lock:
        if not _activate():
            return "Could not find WhatsApp window."

        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.5)
        pyautogui.write(contact_name)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1)

    return f"Opened chat with {contact_name}. Reading messages via automation is limited."


def wa_send(contact_name, message):
    ready, error = _ensure_whatsapp()
    if error:
        return error

    with _wa_lock:
        if not _activate():
            return "Could not find WhatsApp window."

        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.5)
        pyautogui.write(contact_name)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(0.5)
        pyautogui.write(message)
        time.sleep(0.2)
        pyautogui.press("enter")
        time.sleep(0.3)

    return (f"Attempted to send your WhatsApp message to {contact_name}. "
            "I could not verify the recipient or delivery; please check WhatsApp.")


def _start():
    thread = threading.Thread(target=_start_whatsapp_client, daemon=True)
    thread.start()
