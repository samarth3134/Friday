import threading
import time

import brain


_engine = None
_engine_lock = threading.RLock()
_whisper = None
_whisper_lock = threading.RLock()
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


def _get_whisper_model():
    global _whisper

    with _whisper_lock:
        if _whisper is None:
            import config
            from faster_whisper import WhisperModel

            _whisper = WhisperModel(
                getattr(config, "WHISPER_MODEL", "base"),
                download_root=getattr(config, "WHISPER_MODEL_DIR", r"D:\tools\voice_models\whisper"),
                device="cpu",
                compute_type="int8",
            )

    return _whisper


def _record_until_silence(samplerate=16000, max_seconds=6, silence_seconds=1.0, energy_threshold=0.008):
    """Record from the default microphone until speech stops or timeout.

    Returns a float32 numpy array of raw samples (mono, 16 kHz). Records at least
    until silence after speech, or returns whatever is captured otherwise.
    """
    import numpy as np
    import sounddevice as sd
    from collections import deque

    frame = 512  # 32 ms
    max_chunks = int(max_seconds * samplerate / frame)
    silence_chunks = int(silence_seconds * samplerate / frame)
    window = deque(maxlen=silence_chunks)
    chunks = []
    speech_detected = False

    with sd.InputStream(samplerate=samplerate, channels=1, dtype="float32", blocksize=frame) as stream:
        for _ in range(max_chunks):
            data, _overflowed = stream.read(frame)
            chunk = data[:, 0]
            rms = float(np.sqrt(np.mean(np.square(chunk)) + 1e-9))
            chunks.append(chunk)
            window.append(rms > energy_threshold)
            if rms > energy_threshold:
                speech_detected = True
            elif speech_detected and not any(window):
                break

    if not chunks:
        return np.array([], dtype=np.float32)
    return np.concatenate(chunks)


def listen(timeout=6):
    try:
        print("[ Friday is listening... ]")
        audio = _record_until_silence(samplerate=16000, max_seconds=timeout)
        if audio.size == 0:
            return None

        model = _get_whisper_model()
        segments, _info = model.transcribe(audio, language="en", beam_size=1)
        text = " ".join(segment.text for segment in segments).strip()
        return text or None
    except Exception:
        return None


def listen_and_respond(timeout=6):
    text = listen(timeout)
    if not text:
        return None

    response = brain.respond(text)
    speak(response)
    return response
