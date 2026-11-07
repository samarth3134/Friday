import threading
import time

import brain


_engine = None
_engine_lock = threading.RLock()
_stop_event = threading.Event()
_speaking = False


def _get_engine():
    global _engine

    if _engine is None:
        import pyttsx3

        _engine = pyttsx3.init()

    return _engine


def stop_speaking():
    global _speaking

    _stop_event.set()
    with _engine_lock:
        if _engine is not None:
            try:
                _engine.stop()
            except Exception:
                pass
    _speaking = False


def is_speaking():
    return _speaking


def speak(text):
    global _speaking

    if text is None:
        return

    message = str(text).strip()
    if not message:
        return

    _stop_event.clear()

    try:
        with _engine_lock:
            engine = _get_engine()
            _speaking = True
            engine.say(message)
            engine.startLoop(False)

            while _speaking:
                if _stop_event.is_set():
                    engine.stop()
                    break

                busy = engine.isBusy()
                if not busy:
                    break

                engine.iterate()
                time.sleep(0.05)

            try:
                engine.endLoop()
            except RuntimeError:
                pass
    except Exception:
        pass
    finally:
        _speaking = False


def listen(timeout=6):
    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print("[ Friday is listening... ]")
            recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)

        return recognizer.recognize_google(audio)
    except Exception:
        return None


def listen_and_respond(timeout=6):
    text = listen(timeout)
    if not text:
        return None

    response = brain.respond(text)
    speak(response)
    return response
