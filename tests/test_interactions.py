"""Offline acceptance checks; no microphone, network, desktop or power actions.

Regression tests assert desired behavior and intentionally fail on current bugs.
"""
import base64
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def load_isolated(name, **stubs):
    config = types.SimpleNamespace(YT_MUSIC_QUALITY="bestaudio", OLLAMA_VISION_MODEL="llava")
    defaults = {"config": config, "brain": MagicMock(), "voice": MagicMock(), "requests": MagicMock()}
    defaults.update(stubs)
    spec = importlib.util.spec_from_file_location("isolated_" + name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, defaults):
        spec.loader.exec_module(module)
    return module


class IsolatedCase(unittest.TestCase):
    def setUp(self):
        self.previous_cwd = Path.cwd()
        self.temp = tempfile.TemporaryDirectory(prefix="friday-tests-")
        os.chdir(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.previous_cwd)


class VoiceTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.module = load_isolated("voice")
        import numpy as np
        self.np = np

    def test_listen_transcript_and_timeout_arguments(self):
        whisper = MagicMock()
        segment = types.SimpleNamespace(text="test command")
        whisper.transcribe.return_value = ([segment], types.SimpleNamespace(language="en"))
        audio = self.np.zeros(16000, dtype="float32")
        with patch.object(self.module, "_get_whisper_model", return_value=whisper), \
                patch.object(self.module, "_record_until_silence", return_value=audio) as record:
            self.assertEqual(self.module.listen(3), "test command")
        record.assert_called_once_with(samplerate=16000, max_seconds=3)
        whisper.transcribe.assert_called_once_with(audio, language="en", beam_size=1)

    def test_listen_silence_timeout_device_and_network_failures(self):
        with patch.object(self.module, "_record_until_silence", return_value=self.np.zeros(0, dtype="float32")):
            self.assertIsNone(self.module.listen())
        with patch.object(self.module, "_record_until_silence", side_effect=OSError("No input device")):
            self.assertIsNone(self.module.listen())
        whisper = MagicMock()
        whisper.transcribe.side_effect = RuntimeError("model unavailable")
        audio = self.np.zeros(16000, dtype="float32")
        with patch.object(self.module, "_get_whisper_model", return_value=whisper), \
                patch.object(self.module, "_record_until_silence", return_value=audio):
            self.assertIsNone(self.module.listen())

    def test_speak_repeated_calls_and_blank_input(self):
        engine = MagicMock()
        engine.isBusy.side_effect = [True, False, False]
        with patch.object(self.module, "_get_engine", return_value=engine), patch.object(self.module, "time", MagicMock()):
            self.module.speak(" one ")
            self.module.speak("two")
            self.module.speak(None)
            self.module.speak(" ")
        self.assertEqual([c.args[0] for c in engine.say.call_args_list], ["one", "two"])
        self.assertEqual(engine.endLoop.call_count, 2)
        self.assertFalse(self.module.is_speaking())

    def test_speech_cancellation_and_engine_failure_reset_state(self):
        engine = MagicMock()
        engine.isBusy.return_value = True
        engine.iterate.side_effect = self.module._stop_event.set
        with patch.object(self.module, "_get_engine", return_value=engine), patch.object(self.module, "time", MagicMock()):
            self.module.speak("cancel")
        engine.stop.assert_called_once()
        self.assertFalse(self.module.is_speaking())
        with patch.object(self.module, "_get_engine", side_effect=RuntimeError("no engine")):
            self.module.speak("hello")
        self.assertFalse(self.module.is_speaking())


class WakeTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.module = load_isolated("wakeword")
        self.module._play_beep = MagicMock()
        import numpy as np
        self.np = np

    @staticmethod
    def _fake_stream():
        import numpy as np

        class Stream:
            def __init__(self, frames):
                self._frames = list(frames)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, frame):
                if self._frames:
                    return self._frames.pop(0), False
                return np.zeros((frame, 1), dtype="int16"), False

        return Stream

    def test_heard_friday_triggers_at_threshold(self):
        import numpy as np
        oww = MagicMock()
        oww.predict.return_value = {"friday": 0.6}
        Stream = self._fake_stream()
        frames = [np.zeros((1280, 1), dtype="int16")] * 4
        with patch.object(self.module, "_ensure_oww", return_value=oww), \
                patch("sounddevice.InputStream", return_value=Stream(frames)):
            self.assertTrue(self.module._heard_friday(threshold=0.5, window_seconds=1))
        oww.reset.assert_called_once_with()

    def test_regression_unrelated_friday_substring_is_not_wake_word(self):
        # OpenWakeWord detection must stay below the default threshold on silence/ambient noise.
        import numpy as np
        oww = MagicMock()
        oww.predict.side_effect = [{"friday": 0.01}, {"friday": 0.02}, {"friday": 0.015}] + [{"friday": 0.01}] * 60
        Stream = self._fake_stream()
        frames = [np.zeros((1280, 1), dtype="int16")] * 64
        with patch.object(self.module, "_ensure_oww", return_value=oww), \
                patch("sounddevice.InputStream", return_value=Stream(frames)):
            self.assertFalse(self.module._heard_friday(threshold=0.5, window_seconds=0.5))
        self.assertGreaterEqual(oww.predict.call_count, 1)

    def test_heard_friday_device_failure(self):
        with patch.object(self.module, "_ensure_oww", side_effect=RuntimeError("oww unavailable")):
            self.assertFalse(self.module._heard_friday(window_seconds=0.1))

    def test_start_is_idempotent_without_real_thread(self):
        thread = MagicMock()
        thread.is_alive.return_value = True
        with patch.object(self.module.threading, "Thread", return_value=thread) as factory, patch.object(self.module, "time", MagicMock()):
            self.assertIn("started", self.module.start())
            self.assertIn("already running", self.module.start())
        factory.assert_called_once()
        thread.start.assert_called_once()

    def test_detection_state_sequence_and_handoff(self):
        self.module.voice.listen.return_value = "hello"
        self.module.brain.process.return_value = "reply"
        states = []
        actual_set_state = self.module._set_state
        def record(state):
            states.append(state)
            actual_set_state(state)
        with patch.object(self.module, "_set_state", side_effect=record):
            self.module._handle_detection()
        self.assertEqual(states, ["listening", "thinking", "speaking", "idle"])
        self.assertEqual((self.module._voice_command, self.module._voice_response, self.module._voice_version), ("hello", "reply", 1))
        self.module.voice.speak.assert_called_once_with("reply")

    def test_no_command_and_loop_exception_recover_idle(self):
        self.module.voice.listen.return_value = None
        self.module._handle_detection()
        self.assertEqual(self.module.STATE, "idle")
        self.assertEqual(self.module._voice_version, 0)
        self.module._running = True
        def fail_once():
            self.module._running = False
            raise RuntimeError("device")
        with patch.object(self.module, "_heard_friday", side_effect=fail_once), patch.object(self.module, "time", MagicMock()):
            self.module._wake_loop()
        self.assertEqual(self.module.STATE, "idle")


class VisionTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.module = load_isolated("vision")
        self.fixture = Path("fixture.png")
        self.fixture.write_bytes(b"fixture-image-bytes")

    def test_ollama_payload_success_and_failures(self):
        response = self.module.requests.post.return_value
        response.json.return_value = {"response": "  description  "}
        self.assertEqual(self.module._ask_ollama(self.fixture, "describe"), "description")
        args = self.module.requests.post.call_args.kwargs
        self.assertEqual(args["json"], {"model": "llava", "prompt": "describe", "images": [base64.b64encode(self.fixture.read_bytes()).decode()], "stream": False})
        self.assertEqual(args["timeout"], 120)
        response.json.return_value = {"response": ""}
        self.assertIn("could not get", self.module._ask_ollama(self.fixture, "describe"))
        response.raise_for_status.side_effect = RuntimeError("HTTP 500")
        self.assertIn("could not analyze", self.module._ask_ollama(self.fixture, "describe"))
        response.raise_for_status.side_effect = None
        self.module.requests.post.side_effect = TimeoutError()
        self.assertIn("could not analyze", self.module._ask_ollama(self.fixture, "describe"))

    def test_image_path_validation_and_prompts(self):
        with patch.object(self.module, "_ask_ollama", return_value="ok") as ask:
            for function in (self.module.analyze_image, self.module.identify_object):
                self.assertIn("could not find", function("missing.png"))
                self.assertIn("not an image file", function("."))
                self.assertEqual(function(self.fixture), "ok")
            self.assertIn("object", ask.call_args.args[1])

    def test_screen_and_error_capture_prompts_and_failures(self):
        with patch.object(self.module, "_take_screenshot", return_value=(self.fixture, None)) as capture, patch.object(self.module, "_ask_ollama", return_value="ok") as ask:
            self.assertEqual(self.module.analyze_screen(), "ok")
            self.assertIn("visible", ask.call_args.args[1])
            self.assertEqual(self.module.explain_error(), "ok")
            self.assertIn("error", ask.call_args.args[1])
            self.assertEqual([c.args[0] for c in capture.call_args_list], ["screen_analysis", "screen_error"])
            capture.return_value = (None, "capture failed")
            self.assertEqual(self.module.analyze_screen(), "capture failed")
            self.assertEqual(self.module.explain_error(), "capture failed")

    def test_ocr_text_blank_and_failure(self):
        gui, ocr = MagicMock(), MagicMock()
        with patch.dict(sys.modules, {"pyautogui": gui, "pytesseract": ocr}):
            ocr.image_to_string.return_value = " hello "
            self.assertEqual(self.module.read_text_from_screen(), "hello")
            ocr.image_to_string.return_value = " "
            self.assertIn("could not read any", self.module.read_text_from_screen())
            ocr.image_to_string.side_effect = RuntimeError("Tesseract unavailable")
            self.assertIn("could not read text", self.module.read_text_from_screen())
        with patch.dict(sys.modules, {"pyautogui": gui, "pytesseract": None}):
            self.assertIn("could not read text", self.module.read_text_from_screen())

    def test_regression_ocr_captures_only_once(self):
        gui, ocr = MagicMock(), MagicMock()
        ocr.image_to_string.return_value = "hello"
        with patch.dict(sys.modules, {"pyautogui": gui, "pytesseract": ocr}):
            self.module.read_text_from_screen()
        gui.screenshot.assert_called_once()
        ocr.image_to_string.assert_called_once_with(str(Path("screenshots/screen_text.png")))


class MusicTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        self.module = load_isolated("music")
        self.pygame, self.yt = MagicMock(), MagicMock()
        self.track = {"videoId": "fixture-id", "title": "Test song", "artists": [{"name": "Test artist"}]}
        self.yt.YTMusic.return_value.search.return_value = [self.track]
        self.modules = patch.dict(sys.modules, {"pygame": self.pygame, "ytmusicapi": self.yt})
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def test_search_found_empty_and_missing_id(self):
        self.assertEqual(self.module._search_track("query")["title"], "Test song")
        self.yt.YTMusic.return_value.search.return_value = []
        self.assertIsNone(self.module._search_track("query"))
        self.yt.YTMusic.return_value.search.return_value = [{"title": "no ID"}]
        self.assertIsNone(self.module._search_track("query"))

    def test_play_errors_no_results_download_dependency_and_player(self):
        self.yt.YTMusic.return_value.search.return_value = []
        self.assertIn("Could not find", self.module.play("query"))
        self.yt.YTMusic.return_value.search.return_value = [self.track]
        with patch.object(self.module, "subprocess", MagicMock()):
            self.assertIn("Could not download", self.module.play("query"))
        with patch.dict(sys.modules, {"pygame": None}):
            self.assertIn("Music error", self.module.play("query"))
        with patch.object(self.module, "_download_track", return_value=Path("fake.mp3")):
            self.pygame.mixer.music.load.side_effect = RuntimeError("audio device")
            self.assertFalse(self.module._play_track({"url": "fixture"}))

    def test_missing_ffmpeg_prevents_download(self):
        downloader = MagicMock()
        with patch.dict(sys.modules, {"yt_dlp": downloader}), patch.object(self.module, "shutil", MagicMock()) as util:
            util.which.return_value = None
            self.assertIsNone(self.module._download_track("fixture-url"))
        downloader.YoutubeDL.assert_not_called()

    def test_regression_successful_play_updates_now_playing(self):
        def fake_download(*args, **kwargs):
            Path("temp_audio/current_track.mp3").write_bytes(b"fake audio")
            return types.SimpleNamespace(returncode=0, stderr="")
        with patch.object(self.module, "subprocess", MagicMock()) as process:
            process.run.side_effect = fake_download
            self.assertIn("Playing Test song", self.module.play("query"))
        self.assertIn("Test song", self.module.now_playing())

    def test_play_releases_existing_file_before_replacing_it(self):
        path = Path("temp_audio/current_track.mp3")
        path.write_bytes(b"previous track")
        self.module._current_track = {"title": "Previous", "artist": "Earlier"}
        events = []
        self.pygame.mixer.music.stop.side_effect = lambda: events.append("stop")
        self.pygame.mixer.music.unload.side_effect = lambda: events.append("unload")
        def remove_unlocked(filename):
            self.assertEqual(events, ["stop", "unload"])
            Path(filename).unlink()
            events.append("remove")
        def download(*args, **kwargs):
            self.assertEqual(events, ["stop", "unload", "remove"])
            path.write_bytes(b"replacement")
            return types.SimpleNamespace(returncode=0, stderr="")
        with patch.object(self.module.os, "remove", side_effect=remove_unlocked), patch.object(self.module, "subprocess", MagicMock()) as process:
            process.run.side_effect = download
            self.assertIn("Playing Test song", self.module.play("query"))
        self.assertEqual(path.read_bytes(), b"replacement")
        self.assertIn("Test song by Test artist", self.module.now_playing())

    def test_play_failure_after_stopping_clears_previous_status(self):
        self.module._current_track = {"title": "Previous", "artist": "Earlier"}
        Path("temp_audio/current_track.mp3").write_bytes(b"previous")
        with patch.object(self.module.os, "remove", side_effect=PermissionError("locked")), patch.object(self.module, "subprocess", MagicMock()) as process:
            self.assertIn("Music error", self.module.play("query"))
            process.run.assert_not_called()
        self.assertEqual(self.module.now_playing(), "Nothing is playing right now.")

    def test_nonzero_download_with_partial_file_does_not_claim_success(self):
        def fail_download(*args, **kwargs):
            Path("temp_audio/current_track.mp3").write_bytes(b"partial")
            return types.SimpleNamespace(returncode=1, stderr="failed")
        with patch.object(self.module, "subprocess", MagicMock()) as process:
            process.run.side_effect = fail_download
            self.assertIn("Could not download", self.module.play("query"))
        self.pygame.mixer.music.play.assert_not_called()
        self.assertIsNone(self.module._current_track)

    def test_unplayable_search_result_leaves_existing_track_alone(self):
        old = {"title": "Previous", "artist": "Earlier"}
        self.module._current_track = old
        self.yt.YTMusic.return_value.search.return_value = [{"title": "No ID"}]
        with patch.object(self.module, "subprocess", MagicMock()) as process:
            self.assertIn("Could not find a playable", self.module.play("query"))
            process.run.assert_not_called()
        self.pygame.mixer.music.stop.assert_not_called()
        self.assertIs(self.module._current_track, old)

    def test_load_or_play_failure_does_not_set_current_track(self):
        for stage in ("load", "play"):
            with self.subTest(stage=stage):
                self.pygame.mixer.music.reset_mock(side_effect=True)
                getattr(self.pygame.mixer.music, stage).side_effect = RuntimeError("device failed")
                self.module._current_track = {"title": "Previous", "artist": "Earlier"}
                with patch.object(self.module, "_download_track", return_value=Path("fake.mp3")):
                    self.assertFalse(self.module._play_track({"title": "Next", "artist": "Later", "url": "fixture"}))
                self.assertIsNone(self.module._current_track)

    def test_volume_bounds_invalid_and_moods(self):
        for level, expected in [(-1, 0), (130, 1), (25, .25)]:
            with self.subTest(level=level):
                self.assertIn("Music volume set", self.module.set_volume(level))
                self.pygame.mixer.music.set_volume.assert_called_with(expected)
        self.assertIn("could not", self.module.set_volume("bad"))
        with patch.object(self.module, "play", return_value="played") as play:
            for mood, query in self.module.MOOD_QUERIES.items():
                self.assertEqual(self.module.play_mood(mood.upper()), "played")
                play.assert_called_with(query)
            self.assertIn("Tell me", self.module.play_mood(""))
            self.assertIn("I know", self.module.play_mood("unknown"))

    def test_queue_order_clear_skip_and_pause_dispatch(self):
        tracks = [{"title": "A", "artist": "a", "url": "a"}, {"title": "B", "artist": "b", "url": "b"}]
        with patch.object(self.module, "_search_track", side_effect=tracks), patch.object(self.module, "_ensure_player_running") as start:
            self.module.add_to_queue("A")
            self.module.add_to_queue("B")
            self.assertEqual(self.module._queue, tracks)
            self.assertIn("next song", self.module.skip())
            self.assertTrue(start.called)
        self.module.clear_queue()
        self.assertEqual(self.module._queue, [])
        self.assertIn("empty", self.module.skip())
        self.assertIn("Paused", self.module.pause())
        self.assertIn("Resumed", self.module.resume())
        self.pygame.mixer.music.pause.assert_called_once()
        self.pygame.mixer.music.unpause.assert_called_once()
        self.assertIn("not available", self.module.previous())


class SystemControlTests(IsolatedCase):
    def setUp(self):
        super().setUp()
        # platform.system() can launch `ver` internally on Windows Python 3.12.
        # Platform command branches are selected explicitly in each test.
        with patch("platform.system", return_value="Windows"):
            self.module = load_isolated("system_control")
        self.module.subprocess = MagicMock()
        self.gui = MagicMock()
        self.gui_patch = patch.dict(sys.modules, {"pyautogui": self.gui})
        self.gui_patch.start()
        self.addCleanup(self.gui_patch.stop)

    def test_power_commands_all_platforms_and_errors(self):
        commands = {
            "Windows": [ ["rundll32.exe", "user32.dll,LockWorkStation"], ["shutdown", "/s", "/t", "120"], ["shutdown", "/r", "/t", "120"], ["shutdown", "/a"], ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"] ],
            "Darwin": [ ["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"], ["sudo", "shutdown", "-h", "+2"], ["sudo", "shutdown", "-r", "+2"], ["sudo", "killall", "shutdown"], ["pmset", "sleepnow"] ],
            "Linux": [ ["loginctl", "lock-session"], ["shutdown", "-h", "+2"], ["shutdown", "-r", "+2"], ["shutdown", "-c"], ["systemctl", "suspend"] ],
        }
        for platform, expected in commands.items():
            with self.subTest(platform=platform), patch.object(self.module, "SYSTEM", platform):
                calls = [(self.module.lock_screen, ()), (self.module.shutdown, (120,)), (self.module.restart, (120,)), (self.module.cancel_shutdown, ()), (self.module.sleep_mode, ())]
                for (function, args), command in zip(calls, expected):
                    self.assertNotIn("could not", function(*args))
                    self.module.subprocess.run.assert_called_with(command, check=True)
                self.module.subprocess.run.side_effect = OSError("denied")
                for function, args in calls:
                    self.assertIn("could not", function(*args))
                self.module.subprocess.run.side_effect = None
        self.module.SYSTEM = "Windows"
        self.module.shutdown(-2)
        self.module.subprocess.run.assert_called_with(["shutdown", "/s", "/t", "0"], check=True)
        for function in (self.module.shutdown, self.module.restart):
            self.assertIn("could not", function("invalid"))

    def test_click_type_hotkey_dispatch_and_failures(self):
        self.assertIn("Clicked", self.module.click("12", "34"))
        self.gui.click.assert_called_once_with(12, 34)
        self.assertIn("could not", self.module.click("x", 1))
        self.assertIn("Typed", self.module.type_text("fixture text"))
        self.gui.typewrite.assert_called_once_with("fixture text")
        self.assertIn("Tell me", self.module.hotkey())
        self.assertIn("Pressed", self.module.hotkey("ctrl", "a"))
        self.gui.hotkey.assert_called_once_with("ctrl", "a")
        for function, args, api in [(self.module.click, (1, 2), self.gui.click), (self.module.type_text, ("x",), self.gui.typewrite), (self.module.hotkey, ("a",), self.gui.hotkey)]:
            api.side_effect = RuntimeError("desktop unavailable")
            self.assertIn("could not", function(*args))

    def test_screenshot_unique_filenames_and_errors(self):
        image = self.gui.screenshot.return_value
        image.save.side_effect = lambda p: Path(p).write_bytes(b"fixture")
        self.assertIn("screenshot.png", self.module.take_screenshot())
        self.assertIn("screenshot_1.png", self.module.take_screenshot())
        self.gui.screenshot.side_effect = RuntimeError("no display")
        self.assertIn("could not", self.module.take_screenshot())
        self.gui.screenshot.side_effect = None
        image.save.side_effect = PermissionError("denied")
        self.assertIn("could not", self.module.take_screenshot())

    def test_volume_brightness_dispatch_and_bounds(self):
        audio, endpoint, comtypes, brightness = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        pycaw = types.SimpleNamespace(AudioUtilities=audio, IAudioEndpointVolume=endpoint)
        volume = audio.GetSpeakers.return_value.Activate.return_value.QueryInterface.return_value
        with patch.dict(sys.modules, {"comtypes": comtypes, "pycaw": types.ModuleType("pycaw"), "pycaw.pycaw": pycaw, "screen_brightness_control": brightness}):
            self.module.SYSTEM = "Windows"
            for level, expected in [(-1, 0), (101, 1), (50, .5)]:
                self.assertIn("Volume set", self.module.set_volume(level))
                volume.SetMasterVolumeLevelScalar.assert_called_with(expected, None)
            self.module.mute()
            volume.SetMute.assert_called_with(1, None)
            self.module.unmute()
            volume.SetMute.assert_called_with(0, None)
            for level, expected in [(-1, 0), (101, 100)]:
                self.module.set_brightness(level)
                brightness.set_brightness.assert_called_with(expected)
            brightness.set_brightness.side_effect = OSError("no device")
            self.assertIn("could not", self.module.set_brightness(50))
            volume.SetMute.side_effect = OSError("no device")
            self.assertIn("could not", self.module.mute())
            self.assertIn("could not", self.module.unmute())
            volume.SetMasterVolumeLevelScalar.side_effect = OSError("no device")
            self.assertIn("could not", self.module.set_volume(50))
        for platform in ("Darwin", "Linux"):
            self.module.SYSTEM = platform
            expected = {
                "Darwin": [["osascript", "-e", "set volume output volume 50"], ["osascript", "-e", "set volume output muted true"], ["osascript", "-e", "set volume output muted false"]],
                "Linux": [["amixer", "sset", "Master", "50%"], ["amixer", "sset", "Master", "mute"], ["amixer", "sset", "Master", "unmute"]],
            }[platform]
            for (function, args), command in zip([(self.module.set_volume, (50,)), (self.module.mute, ()), (self.module.unmute, ())], expected):
                self.assertNotIn("could not", function(*args))
                self.module.subprocess.run.assert_called_with(command, check=True)
        self.assertIn("could not", self.module.set_volume("bad"))
        self.assertIn("could not", self.module.set_brightness("bad"))
        self.module.SYSTEM = "Windows"
        with patch.dict(sys.modules, {"comtypes": None, "screen_brightness_control": None}):
            self.assertIn("could not", self.module.set_volume(50))
            self.assertIn("could not", self.module.mute())
            self.assertIn("could not", self.module.unmute())
            self.assertIn("could not", self.module.set_brightness(50))

    def test_apps_path_lookup_launch_and_failure(self):
        with patch("shutil.which", return_value="C:/fixture/tool.exe"):
            self.assertEqual(self.module._find_windows_app("tool"), "C:/fixture/tool.exe")
        with patch.object(self.module, "_find_windows_app", return_value="C:/fixture/tool.exe"), patch.object(self.module, "_move_window_to_top"):
            self.module.SYSTEM = "Windows"
            self.assertIn("Opening", self.module.open_app("tool"))
            self.module.subprocess.Popen.assert_called_with(["C:/fixture/tool.exe"], shell=True)
            self.module.subprocess.Popen.side_effect = OSError("not found")
            self.assertIn("could not", self.module.open_app("tool"))
            self.assertIn("Tell me", self.module.open_app(" "))

    def test_process_listing_and_permission_errors(self):
        proc = MagicMock()
        proc.info = {"name": "tool.exe"}
        unnamed = MagicMock()
        unnamed.info = {"name": None}
        psutil = MagicMock()
        psutil.process_iter.return_value = [proc, unnamed, proc]
        with patch.dict(sys.modules, {"psutil": psutil}):
            self.assertEqual(self.module.list_running_apps(), "Running apps include: tool.exe.")
            self.assertIn("could not find", self.module.close_app("absent"))
            proc.terminate.side_effect = PermissionError("denied")
            self.assertIn("could not close", self.module.close_app("tool"))

    def test_regression_close_app_does_not_match_unrelated_substring(self):
        intended, unrelated = MagicMock(), MagicMock()
        intended.info, unrelated.info = {"name": "code.exe"}, {"name": "encoder.exe"}
        psutil = MagicMock()
        psutil.process_iter.return_value = [intended, unrelated]
        with patch.dict(sys.modules, {"psutil": psutil}):
            self.module.close_app("code")
        intended.terminate.assert_called_once()
        unrelated.terminate.assert_not_called()

    def test_close_app_matches_executable_name_case_insensitively(self):
        for request in ("code", "CODE.EXE"):
            with self.subTest(request=request):
                intended, unrelated = MagicMock(), MagicMock()
                intended.info, unrelated.info = {"name": "Code.EXE"}, {"name": "Code Helper.exe"}
                psutil = MagicMock()
                psutil.process_iter.return_value = [intended, unrelated]
                with patch.dict(sys.modules, {"psutil": psutil}):
                    self.assertIn("Closed 1", self.module.close_app(request))
                intended.terminate.assert_called_once()
                unrelated.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
