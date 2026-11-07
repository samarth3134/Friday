import math
import re
import threading
import time

import brain
import voice


STATE = "idle"
_thread = None
_running = False
_voice_command = None
_voice_response = None
_voice_version = 0

# Reusable recognizer & microphone (avoids recreate overhead each cycle)
_recognizer = None
_microphone = None
_mic_source = None


def _ensure_mic():
    global _recognizer, _microphone, _mic_source
    if _recognizer is None:
        import speech_recognition as sr
        _recognizer = sr.Recognizer()
        _recognizer.energy_threshold = 4000
        _recognizer.dynamic_energy_threshold = False
        _microphone = sr.Microphone()
        with _microphone as source:
            _recognizer.adjust_for_ambient_noise(source, duration=0.15)
        _mic_source = sr.Microphone()
    return _recognizer, _mic_source


def _set_state(state):
    global STATE
    STATE = state


def _play_beep():
    try:
        import numpy as np
        import sounddevice as sd

        sample_rate = 44100
        duration = 0.16
        frequency = 880
        samples = np.arange(int(sample_rate * duration))
        wave = 0.25 * np.sin(2 * math.pi * frequency * samples / sample_rate)
        sd.play(wave, sample_rate)
        sd.wait()
    except Exception:
        pass


def _heard_friday():
    try:
        recognizer, source = _ensure_mic()
        with source as s:
            audio = recognizer.listen(s, timeout=0.8, phrase_time_limit=1.5)

        transcript = recognizer.recognize_google(audio)
        return re.search(r"\bfriday\b", transcript, re.IGNORECASE) is not None
    except Exception:
        return False


def _handle_detection():
    global _voice_command, _voice_response, _voice_version

    voice.stop_speaking()
    _play_beep()

    _set_state("listening")
    print("[WAKE] Listening for command...")
    command = voice.listen()
    if not command:
        _set_state("idle")
        return

    _voice_command = command

    _set_state("thinking")
    response = brain.process(command)
    _voice_response = response
    _voice_version += 1

    _set_state("speaking")
    voice.speak(response)
    _set_state("idle")


def _wake_loop():
    global _running

    _set_state("idle")
    print("[WAKE] Listening for 'friday' via microphone...")

    while _running:
        try:
            if _heard_friday():
                print("[WAKE] Heard 'friday'!")
                _handle_detection()
                time.sleep(0.8)
            else:
                _set_state("idle")
        except Exception:
            _set_state("idle")
            time.sleep(0.3)


def start():
    global _thread, _running

    if _thread and _thread.is_alive():
        return "Friday wake word listener is already running."

    _running = True
    _thread = threading.Thread(target=_wake_loop, daemon=True)
    _thread.start()
    time.sleep(0.1)
    return "Friday wake word listener started."
