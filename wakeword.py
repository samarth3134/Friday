import math
import threading
import time

import brain
import voice


# OpenWakeWord handles the wake listener entirely offline (16 kHz mono input).
from pathlib import Path

STATE = "idle"
_thread = None
_running = False
_voice_command = None
_voice_response = None
_voice_version = 0

_oww = None
_oww_lock = threading.RLock()


def _ensure_oww():
    global _oww

    with _oww_lock:
        if _oww is None:
            from openwakeword.model import Model

            _oww = Model(
                wakeword_models=[str(Path(__file__).parent / "friday.onnx")],
                inference_framework="onnx",
            )

    return _oww


def _wake_threshold():
    try:
        import config

        return float(getattr(config, "WAKE_WORD_THRESHOLD", 0.5))
    except Exception:
        return 0.5


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


def _heard_friday(threshold=None, window_seconds=8):
    try:
        import numpy as np
        import sounddevice as sd

        threshold = _wake_threshold() if threshold is None else float(threshold)
        samplerate = 16000
        frame = 1280  # 80 ms at 16 kHz

        model = _ensure_oww()
        model.reset()
        deadline = time.time() + window_seconds
        with sd.InputStream(samplerate=samplerate, channels=1, dtype="int16", blocksize=frame) as stream:
            while time.time() < deadline:
                data, _overflowed = stream.read(frame)
                audio = data[:, 0]
                predictions = model.predict(audio)
                score = float(predictions.get("friday", 0.0))
                if score >= threshold:
                    return True
        return False
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
