import os
import platform
import subprocess
import time
from pathlib import Path


SYSTEM = platform.system()


def _run(command):
    subprocess.run(command, check=True)


def set_volume(level):
    try:
        level = max(0, min(100, int(level)))

        if SYSTEM == "Windows":
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMasterVolumeLevelScalar(level / 100, None)
        elif SYSTEM == "Darwin":
            _run(["osascript", "-e", f"set volume output volume {level}"])
        else:
            _run(["amixer", "sset", "Master", f"{level}%"])

        return f"Volume set to {level} percent."
    except Exception:
        return "I could not set the volume."


def mute():
    try:
        if SYSTEM == "Windows":
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(1, None)
        elif SYSTEM == "Darwin":
            _run(["osascript", "-e", "set volume output muted true"])
        else:
            _run(["amixer", "sset", "Master", "mute"])

        return "Muted the system volume."
    except Exception:
        return "I could not mute the system volume."


def unmute():
    try:
        if SYSTEM == "Windows":
            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = interface.QueryInterface(IAudioEndpointVolume)
            volume.SetMute(0, None)
        elif SYSTEM == "Darwin":
            _run(["osascript", "-e", "set volume output muted false"])
        else:
            _run(["amixer", "sset", "Master", "unmute"])

        return "Unmuted the system volume."
    except Exception:
        return "I could not unmute the system volume."


def _find_windows_app(name):
    """Try to locate an app by name on Windows."""
    import shutil

    name_lower = name.lower().removesuffix(".exe") + ".exe"

    # 1. PATH lookup
    found = shutil.which(name_lower)
    if found:
        return found

    # 2. Common install directories
    roots = [
        os.environ.get("ProgramFiles", "C:\\Program Files"),
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("LOCALAPPDATA", "") + "\\Programs",
        os.environ.get("APPDATA", "") + "\\..\\Local\\Microsoft\\WindowsApps",
        "C:\\Program Files\\WindowsApps",
    ]
    for root in roots:
        if not root:
            continue
        root = os.path.abspath(root)
        for dirpath, dirs, files in os.walk(root):
            for f in files:
                if f.lower() == name_lower:
                    return os.path.join(dirpath, f)
            # limit depth to avoid huge walks
            if dirpath.count(os.sep) > root.count(os.sep) + 3:
                dirs.clear()

    # 3. Known short names → full names
    known = {
        "chrome": "chrome.exe",
        "firefox": "firefox.exe",
        "edge": "msedge.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "cmd": "cmd.exe",
        "terminal": "wt.exe",
        "powershell": "powershell.exe",
        "explorer": "explorer.exe",
        "task manager": "Taskmgr.exe",
        "control panel": "control.exe",
        "settings": "ms-settings:",
        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",
        "outlook": "OUTLOOK.EXE",
        "teams": "Teams.exe",
        "code": "Code.exe",
        "spotify": "Spotify.exe",
        "discord": "Discord.exe",
        "whatsapp": "WhatsApp.exe",
        "vlc": "vlc.exe",
    }
    if name_lower.removesuffix(".exe") in known:
        exe = known[name_lower.removesuffix(".exe")]
        found = shutil.which(exe)
        if found:
            return found
        # also check full root paths
        for root in roots:
            if not root:
                continue
            root = os.path.abspath(root)
            for dirpath, dirs, files in os.walk(root):
                for f in files:
                    if f.lower() == exe.lower():
                        return os.path.join(dirpath, f)
                if dirpath.count(os.sep) > root.count(os.sep) + 3:
                    dirs.clear()

    return None


def _move_window_to_top(name_hint):
    """Try to move the app window to the top half of the screen."""
    try:
        import pygetwindow as gw
        import pyautogui

        screen_w, screen_h = pyautogui.size()
        target_w = screen_w
        target_h = screen_h // 2
        target_x = 0
        target_y = 0

        # wait briefly then try to find + move window
        time.sleep(0.6)
        name_lower = name_hint.lower()
        windows = gw.getWindowsWithTitle("")
        best = None
        best_score = 0
        for w in windows:
            if not w.title:
                continue
            title = w.title.lower()
            # score: exact match > contains > partial
            if name_lower in title:
                score = len(name_lower) / max(len(title), 1)
                if score > best_score:
                    best_score = score
                    best = w
        if best:
            best.moveTo(target_x, target_y)
            best.resizeTo(target_w, target_h)
    except Exception:
        pass


def open_app(name):
    try:
        if not name or not str(name).strip():
            return "Tell me which app to open."

        app_name = str(name).strip()

        if SYSTEM == "Windows":
            path = _find_windows_app(app_name)
            if path:
                subprocess.Popen([path], shell=True)
                _move_window_to_top(app_name)
                return f"Opening {app_name}."
            # fallback: try startfile (works for protocols, URIs, etc.)
            os.startfile(app_name)
        elif SYSTEM == "Darwin":
            subprocess.Popen(["open", "-a", app_name])
        else:
            subprocess.Popen([app_name])

        _move_window_to_top(app_name)
        return f"Opening {app_name}."
    except Exception:
        return f"I could not open {name}."


def close_app(name):
    try:
        import psutil

        if not name or not str(name).strip():
            return "Tell me which app to close."

        target = str(name).strip().casefold().removesuffix(".exe")
        closed = []

        for process in psutil.process_iter(["name"]):
            process_name = process.info.get("name") or ""
            if target == process_name.casefold().removesuffix(".exe"):
                process.terminate()
                closed.append(process_name)

        if not closed:
            return f"I could not find a running app named {name}."

        return f"Closed {len(closed)} process matching {name}."
    except Exception:
        return f"I could not close {name}."


def list_running_apps():
    try:
        import psutil

        names = sorted(
            {
                process.info.get("name")
                for process in psutil.process_iter(["name"])
                if process.info.get("name")
            }
        )

        if not names:
            return "I could not find any running apps."

        return "Running apps include: " + ", ".join(names) + "."
    except Exception:
        return "I could not list the running apps."


def lock_screen():
    try:
        if SYSTEM == "Windows":
            _run(["rundll32.exe", "user32.dll,LockWorkStation"])
        elif SYSTEM == "Darwin":
            _run(["/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession", "-suspend"])
        else:
            _run(["loginctl", "lock-session"])

        return "Locked the screen."
    except Exception:
        return "I could not lock the screen."


def take_screenshot():
    try:
        import pyautogui

        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        path = screenshots_dir / "screenshot.png"

        counter = 1
        while path.exists():
            path = screenshots_dir / f"screenshot_{counter}.png"
            counter += 1

        image = pyautogui.screenshot()
        image.save(path)
        return f"Screenshot saved to {path.resolve()}."
    except Exception:
        return "I could not take a screenshot."


def set_brightness(level):
    try:
        import screen_brightness_control as sbc

        level = max(0, min(100, int(level)))
        sbc.set_brightness(level)
        return f"Brightness set to {level} percent."
    except Exception:
        return "I could not set the brightness."


def click(x, y):
    try:
        import pyautogui

        pyautogui.click(int(x), int(y))
        return f"Clicked at {x}, {y}."
    except Exception:
        return "I could not click there."


def type_text(text):
    try:
        import pyautogui

        pyautogui.typewrite(str(text))
        return "Typed the text."
    except Exception:
        return "I could not type the text."


def hotkey(*keys):
    try:
        import pyautogui

        if not keys:
            return "Tell me which keys to press."

        pyautogui.hotkey(*(str(key) for key in keys))
        return "Pressed the hotkey."
    except Exception:
        return "I could not press that hotkey."


def shutdown(delay=60):
    try:
        delay = max(0, int(delay))

        if SYSTEM == "Windows":
            _run(["shutdown", "/s", "/t", str(delay)])
        elif SYSTEM == "Darwin":
            minutes = max(1, delay // 60)
            _run(["sudo", "shutdown", "-h", f"+{minutes}"])
        else:
            minutes = max(1, delay // 60)
            _run(["shutdown", "-h", f"+{minutes}"])

        return f"Shutdown scheduled in {delay} seconds."
    except Exception:
        return "I could not schedule shutdown."


def restart(delay=60):
    try:
        delay = max(0, int(delay))

        if SYSTEM == "Windows":
            _run(["shutdown", "/r", "/t", str(delay)])
        elif SYSTEM == "Darwin":
            minutes = max(1, delay // 60)
            _run(["sudo", "shutdown", "-r", f"+{minutes}"])
        else:
            minutes = max(1, delay // 60)
            _run(["shutdown", "-r", f"+{minutes}"])

        return f"Restart scheduled in {delay} seconds."
    except Exception:
        return "I could not schedule restart."


def cancel_shutdown():
    try:
        if SYSTEM == "Windows":
            _run(["shutdown", "/a"])
        elif SYSTEM == "Darwin":
            _run(["sudo", "killall", "shutdown"])
        else:
            _run(["shutdown", "-c"])

        return "Cancelled the scheduled shutdown or restart."
    except Exception:
        return "I could not cancel the scheduled shutdown or restart."


def sleep_mode():
    try:
        if SYSTEM == "Windows":
            _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
        elif SYSTEM == "Darwin":
            _run(["pmset", "sleepnow"])
        else:
            _run(["systemctl", "suspend"])

        return "Putting the system to sleep."
    except Exception:
        return "I could not put the system to sleep."
