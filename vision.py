import base64
from pathlib import Path

import requests

from config import OLLAMA_VISION_MODEL


OLLAMA_URL = "http://localhost:11434/api/generate"
SCREENSHOT_DIR = Path("screenshots")


def _encode_image(path):
    with open(path, "rb") as image:
        return base64.b64encode(image.read()).decode("utf-8")


def _ask_ollama(image_path, prompt):
    try:
        image = _encode_image(image_path)
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_VISION_MODEL,
                "prompt": prompt,
                "images": [image],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()
        return answer or "I could not get a visual description."
    except Exception:
        return "I could not analyze the image with Ollama right now."


def _screenshot_path(prefix="screen"):
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREENSHOT_DIR / f"{prefix}.png"
    counter = 1

    while path.exists():
        path = SCREENSHOT_DIR / f"{prefix}_{counter}.png"
        counter += 1

    return path


def _take_screenshot(prefix="screen"):
    try:
        import pyautogui

        path = _screenshot_path(prefix)
        image = pyautogui.screenshot()
        image.save(path)
        return path, None
    except Exception:
        return None, "I could not take a screenshot."


def analyze_screen():
    path, error = _take_screenshot("screen_analysis")
    if error:
        return error

    return _ask_ollama(
        path,
        "Describe what is visible on this screen clearly and briefly.",
    )


def analyze_image(path):
    image_path = Path(path).expanduser()
    if not image_path.exists():
        return f"I could not find the image at {image_path}."

    if not image_path.is_file():
        return f"{image_path} is not an image file."

    return _ask_ollama(
        image_path,
        "Describe this image clearly and briefly.",
    )


def read_text_from_screen():
    path, error = _take_screenshot("screen_text")
    if error:
        return error

    try:
        import config as _config
        import pytesseract

        # Setting pytesseract.tesseract_cmd only rebinds the package namespace;
        # the worker module reads its own module-global, so set it there.
        tesseract_cmd = getattr(_config, "TESSERACT_CMD", "tesseract")
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        text = pytesseract.image_to_string(str(path)).strip()
        return text or "I could not read any text from the screen."
    except Exception:
        return "I could not read text from the screen."


def identify_object(path):
    image_path = Path(path).expanduser()
    if not image_path.exists():
        return f"I could not find the image at {image_path}."

    if not image_path.is_file():
        return f"{image_path} is not an image file."

    return _ask_ollama(
        image_path,
        "What is this object? Answer clearly and briefly.",
    )


def explain_error():
    path, error = _take_screenshot("screen_error")
    if error:
        return error

    return _ask_ollama(
        path,
        "What error is shown on this screen, and how do I fix it? Give a clear, practical answer.",
    )
