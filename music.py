import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import config as _config

FFMPEG_LOCATION = getattr(_config, "FFMPEG_LOCATION", "") or ""

from config import YT_MUSIC_QUALITY


TEMP_DIR = "./temp_audio"
os.makedirs(TEMP_DIR, exist_ok=True)

MOOD_QUERIES = {
    "chill": "chill music playlist",
    "hype": "hype music playlist",
    "focus": "focus music playlist",
    "sad": "sad songs playlist",
    "sleep": "sleep music playlist",
}

_queue = []
_current_track = None
_player_thread = None
_stop_event = threading.Event()
_lock = threading.RLock()
_mixer_ready = False
TEMP_AUDIO_DIR = Path("temp_audio")
CURRENT_TRACK_PATH = TEMP_AUDIO_DIR / "current_track.mp3"


def _friendly_error():
    return "I could not play music right now. Make sure ytmusicapi, yt-dlp, and pygame are installed."


def _init_mixer():
    global _mixer_ready

    if _mixer_ready:
        return True

    try:
        import pygame

        pygame.mixer.init()
        _mixer_ready = True
        return True
    except Exception:
        return False


def _search_track(query):
    from ytmusicapi import YTMusic

    ytmusic = YTMusic()
    results = ytmusic.search(str(query).strip(), filter="songs", limit=1)
    if not results:
        results = ytmusic.search(str(query).strip(), limit=1)
    if not results:
        return None

    result = results[0]
    video_id = result.get("videoId")
    if not video_id:
        return None

    artists = result.get("artists") or []
    artist_names = ", ".join(artist.get("name", "") for artist in artists if artist.get("name"))

    return {
        "title": result.get("title", "Unknown song"),
        "artist": artist_names or "unknown artist",
        "url": f"https://youtube.com/watch?v={video_id}",
    }


def _ffmpeg_command():
    if FFMPEG_LOCATION:
        if os.path.isdir(FFMPEG_LOCATION):
            candidate = os.path.join(FFMPEG_LOCATION, "ffmpeg.exe")
            if os.path.exists(candidate):
                return candidate
        elif os.path.exists(FFMPEG_LOCATION):
            return FFMPEG_LOCATION
    return shutil.which("ffmpeg") or ""


def _ffmpeg_available():
    if _ffmpeg_command():
        return True

    print("FFmpeg not found. Install it on D: (e.g. D:\\tools\\ffmpeg) or set FFMPEG_LOCATION.")
    return False


def _download_track(track_url):
    import yt_dlp

    if not _ffmpeg_available():
        return None

    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    for file_path in TEMP_AUDIO_DIR.glob("current_track.*"):
        try:
            file_path.unlink()
        except Exception:
            pass

    options = {
        "format": YT_MUSIC_QUALITY,
        "outtmpl": str(TEMP_AUDIO_DIR / "current_track.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    if FFMPEG_LOCATION:
        options["ffmpeg_location"] = FFMPEG_LOCATION
    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(track_url, download=True)

    return CURRENT_TRACK_PATH if CURRENT_TRACK_PATH.exists() else None


def _play_track(track):
    global _current_track

    if not _init_mixer():
        return False

    try:
        import pygame

        pygame.mixer.music.stop()
        _current_track = None
        pygame.mixer.music.unload()
        audio_path = _download_track(track["url"])
        if not audio_path:
            return False

        pygame.mixer.music.load(str(audio_path))
        pygame.mixer.music.play()
        _current_track = track
        return True
    except Exception:
        return False


def _playback_loop():
    global _current_track, _player_thread

    try:
        import pygame

        while not _stop_event.is_set():
            with _lock:
                if not _queue:
                    _current_track = None
                    break
                track = _queue.pop(0)

            if not _play_track(track):
                continue

            while pygame.mixer.music.get_busy() and not _stop_event.is_set():
                time.sleep(0.25)

            if _stop_event.is_set():
                pygame.mixer.music.stop()
                break
    except Exception:
        pass
    finally:
        _current_track = None
        _player_thread = None


def _ensure_player_running():
    global _player_thread

    if _player_thread and _player_thread.is_alive():
        return

    _stop_event.clear()
    _player_thread = threading.Thread(target=_playback_loop, daemon=True)
    _player_thread.start()


def add_to_queue(query):
    if not query or not str(query).strip():
        return "Tell me what song to add to the queue."

    try:
        track = _search_track(query)
        if not track:
            return f"I could not find {query} on YouTube Music."

        with _lock:
            _queue.append(track)

        if not _current_track:
            _ensure_player_running()

        return f"Added {track['title']} by {track['artist']} to the queue."
    except Exception:
        return _friendly_error()


def clear_queue():
    with _lock:
        _queue.clear()
    return "The music queue is clear."


def play(query):
    global _current_track

    try:
        import pygame
        from ytmusicapi import YTMusic

        if not query or not str(query).strip():
            return "Tell me what song to play."

        # Step 1: search
        yt = YTMusic()
        results = yt.search(query, filter="songs")
        if not results:
            return "Could not find that song."

        top = results[0]
        video_id = top.get("videoId")
        if not video_id:
            return "Could not find a playable song."
        title = top.get("title", "Unknown")
        artists = top.get("artists") or []
        artist = ", ".join(item.get("name", "") for item in artists if item.get("name")) or "Unknown"
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Step 2: download with yt-dlp via subprocess
        out_path = os.path.join(TEMP_DIR, "current_track.%(ext)s")
        final_path = os.path.join(TEMP_DIR, "current_track.mp3")

        if not _init_mixer():
            return _friendly_error()

        # Release pygame's file handle before replacing the MP3 on Windows.
        # Once stopped, failures must not leave the previous song in status.
        pygame.mixer.music.stop()
        _current_track = None
        pygame.mixer.music.unload()
        if os.path.exists(final_path):
            os.remove(final_path)

        cmd = [
            "yt-dlp",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "0",
        ]
        if FFMPEG_LOCATION:
            cmd += ["--ffmpeg-location", FFMPEG_LOCATION]
        cmd += [
            "-o", out_path,
            "--no-playlist",
            url
        ]

        print(f"[MUSIC] Downloading: {title} by {artist}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0 or not os.path.exists(final_path):
            print(f"[MUSIC] yt-dlp stderr: {result.stderr}")
            return f"Could not download {title}."

        # Step 3: play with pygame
        pygame.mixer.music.load(final_path)
        pygame.mixer.music.play()
        _current_track = {"title": title, "artist": artist, "url": url}

        return f"Playing {title} by {artist}."

    except Exception as e:
        return f"Music error: {e}"


def pause():
    try:
        if not _init_mixer():
            return _friendly_error()

        import pygame

        pygame.mixer.music.pause()
        return "Paused the music."
    except Exception:
        return "I could not pause the music."


def resume():
    try:
        if not _init_mixer():
            return _friendly_error()

        import pygame

        pygame.mixer.music.unpause()
        return "Resumed the music."
    except Exception:
        return "I could not resume the music."


def skip():
    global _current_track

    try:
        if not _init_mixer():
            return _friendly_error()

        import pygame

        pygame.mixer.music.stop()
        _current_track = None
        with _lock:
            has_next = bool(_queue)

        if has_next:
            _ensure_player_running()
            return "Skipped to the next song."

        return "Skipped the current song. The queue is empty."
    except Exception:
        return "I could not skip the song."


def previous():
    return "Previous track is not available for local YouTube Music playback yet."


def set_volume(level):
    try:
        if not _init_mixer():
            return _friendly_error()

        import pygame

        level = max(0, min(100, int(level)))
        pygame.mixer.music.set_volume(level / 100)
        return f"Music volume set to {level} percent."
    except Exception:
        return "I could not set the music volume."


def now_playing():
    if not _current_track:
        return "Nothing is playing right now."

    return f"Now playing {_current_track['title']} by {_current_track['artist']}."


def play_mood(mood):
    if not mood or not str(mood).strip():
        return "Tell me what mood you want."

    mood_key = str(mood).strip().lower()
    query = MOOD_QUERIES.get(mood_key)
    if not query:
        return "I know chill, hype, focus, sad, and sleep moods."

    return play(query)
