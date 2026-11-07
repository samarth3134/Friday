import sys

import requests


BOOT_ART = r"""
  ______ _____  _____ _____          __     __
 |  ____|  __ \|_   _|  __ \   /\    \ \   / /
 | |__  | |__) | | | | |  | | /  \    \ \_/ /
 |  __| |  _  /  | | | |  | |/ /\ \    \   /
 | |    | | \ \ _| |_| |__| / ____ \    | |
 |_|    |_|  \_\_____|_____/_/    \_\   |_|
"""


def print_boot_message():
    print(BOOT_ART)
    print("Friday is booting. Systems coming online.")


def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=3)
        response.raise_for_status()
        print("Ollama is running.")
        return True
    except Exception:
        print("Ollama is not running.")
        print("Setup instructions:")
        print("1. Install Ollama from https://ollama.com/download")
        print("2. Start Ollama.")
        print("3. Pull the required models:")
        print("   ollama pull llama3")
        print("   ollama pull llava")
        print("4. Run Friday again with: python main.py")
        return False


def initialize_tasks():
    try:
        import tasks
    except Exception:
        print("Tasks are unavailable. Check SQLite storage and folder permissions.")
        return None

    print("Task database initialized.")
    return tasks


def initialize_memory():
    try:
        import memory
    except Exception:
        print("Memory is unavailable. Check Chroma installation and storage permissions.")
        return None

    print("Chroma memory initialized.")
    return memory


def start_whatsapp():
    try:
        import whatsapp_desktop

        whatsapp_desktop._start()
        print("WhatsApp Desktop starting.")
    except Exception:
        print("WhatsApp Desktop could not start.")
        return None
    return whatsapp_desktop


def start_wakeword():
    try:
        import wakeword

        print(wakeword.start())
    except Exception:
        print("Wake word listener could not start. Check microphone and speech recognition setup.")
        return None
    return wakeword


def launch_dashboard():
    import ui

    app = ui.build_app()
    app.launch(server_port=7862)


def terminal_loop():
    import brain
    try:
        import voice
    except Exception:
        voice = None

    print("Terminal mode is active. Type 'exit' or 'quit' to stop Friday.")
    while True:
        try:
            user_text = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nFriday shutting down.")
            break

        if user_text.lower() in {"exit", "quit"}:
            print("Friday shutting down.")
            break

        if not user_text:
            continue

        response = brain.process(user_text)
        print(f"Friday: {response}")
        if voice is not None:
            voice.speak(response)


def main():
    print_boot_message()

    if not check_ollama():
        sys.exit(1)

    initialize_tasks()
    initialize_memory()
    start_whatsapp()
    start_wakeword()

    try:
        launch_dashboard()
    except Exception as error:
        print(f"Gradio dashboard failed to launch: {error}")
        terminal_loop()


if __name__ == "__main__":
    main()
