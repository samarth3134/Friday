# Friday AI Assistant

Friday is a Python desktop assistant with Ollama, a Gradio UI, voice input, persistent memory, and tools for files, system controls, tasks, weather, music, Gmail, WhatsApp, Calendar, and vision.

## Read this first

Read this README and AGENTS.md before working on the project. Update the relevant sections and change log whenever code, configuration, dependencies, setup, or important decisions change. Keep unfinished work and actual test results here so future sessions can resume quickly. Never include credential values or private conversation content.

Last source review: **2026-11-06**. All 18 Python modules and the previous README were read. Binary models, audio, database contents, and OAuth token values were not reviewed. The live app and external integrations have not been run. The 23 failing test methods recorded on 2026-11-07 were fixed in source on 2026-11-07 and further improvements landed the same day; the offline suite was re-run afterwards: 124 test methods, all passing; see the test record below.

## Architecture and source map

Flow: main.py checks Ollama, initializes tasks and memory, starts WhatsApp Desktop and the wake listener, then launches Gradio. Dashboard launch failures fall back to terminal input.

Text or voice -> brain.process/respond -> keyword intent classification -> Chroma memory retrieval -> feature module or Ollama -> save conversation.

The model does not select tools. Routing uses word-boundary keyword matching plus regex extraction, in a fixed priority order. Most tools return results directly; casual replies and search-backed research use Ollama.

| File | Responsibility |
| --- | --- |
| main.py | Startup, Ollama check, services, Gradio launch, terminal fallback |
| brain.py | Classification, argument parsing, routing, memory context, Ollama; respond/process/handle/chat aliases |
| config.py | Models, paths, file restrictions, weather, user name, music quality |
| ui.py | Dashboard and Chat tabs, styling, mic button, voice-message polling |
| dashboard.py | Collects service status and recent memories |
| voice.py | faster-whisper offline transcription + local pyttsx3 output |
| wakeword.py | openWakeWord offline detection of "friday" (bundled friday.onnx) |
| memory.py | Chroma facts, preferences, conversation pairs, similarity search, recent history |
| tasks.py | SQLite task CRUD, filters, overdue queries |
| filesystem.py | Restricted-path search/open/read/list/write/move/trash |
| system_control.py | Apps, volume, brightness, screenshots, keyboard/mouse, power |
| search.py | DuckDuckGo web/news results for Ollama |
| weather.py | Open-Meteo current weather, forecast, jacket advice (open-source, no API key) |
| music.py | YouTube Music search, yt-dlp downloads, pygame playback and queue helpers |
| messaging.py | Gmail OAuth/read/search/send and WhatsApp delegation |
| whatsapp_desktop.py | Windows WhatsApp window and keyboard automation |
| calendar_integration.py | Calendar OAuth, list/create/delete events, free slots |
| vision.py | Screenshots, llava image analysis, Tesseract OCR |

## Setup and launch

Python 3.10+ is the intended baseline. Windows is the primary target. A `requirements.txt` manifest derived from the imports now exists, but it is **unpinned and has not been validated against a clean install**; use the import-based list below as a reference, with the same caveat:

```powershell
python -m pip install -r requirements.txt
# or the original list:
python -m pip install requests chromadb duckduckgo-search pymupdf python-docx openpyxl send2trash psutil pyautogui pygetwindow screen-brightness-control pyttsx3 faster-whisper openwakeword numpy sounddevice gradio pytesseract ytmusicapi yt-dlp pygame google-api-python-client google-auth-oauthlib google-auth-httplib2
python -m pip install pycaw comtypes
```

Install and start [Ollama](https://ollama.com/download), then:

```powershell
ollama pull llama3
ollama pull llava
```

### Source control (git / GitHub)

Friday is developed in `D:\projects\Friday`, a git repository published at **https://github.com/samarth3134/Friday** (public, owned by samarth3134; pushed 2026-11-07). Secrets, runtime data, model binaries and bytecode caches are gitignored; `.gitattributes` normalizes text to LF.

Git and the GitHub CLI are installed **portable on D:** (installed 2026-11-07) because the machine had no git:

- `D:\tools\mingit` — MinGit 2.56.0.windows.4 (git); call `D:\tools\mingit\cmd\git.exe` or add `D:\tools\mingit\cmd` to PATH.
- `D:\tools\gh` — GitHub CLI 2.103.3, authenticated as `samarth3134` (HTTPS device flow).
- `D:\tools\mingit-global.gitconfig` — global config holding a `safe.directory` exception for `D:/projects/Friday` (this folder's ownership record differs from the current SID). Every git invocation in this setup needs `GIT_CONFIG_GLOBAL=D:\tools\mingit-global.gitconfig` set first (e.g. `$env:GIT_CONFIG_GLOBAL = 'D:\tools\mingit-global.gitconfig'`). Git also fails to be found by gh unless `D:\tools\mingit\cmd` is on PATH.
- Commits in this repo are authored as `samarth3134 <108995242+samarth3134@users.noreply.github.com>` (repo-local config).

Contributing flow: edit on a branch or `main`, run `& D:\python_3.12\python.exe -B tests/run_tests.py`, keep this README synchronized, commit and push with the environment variables above.

### Machine layout and paths (this machine, verified 2026-11-07)

| What | Location |
| --- | --- |
| Repository / working tree | `D:\projects\Friday` → public repo https://github.com/samarth3134/Friday |
| Python interpreter + site-packages | `D:\python_3.12\python.exe` (3.12.10); its `Scripts` is **not** on PATH |
| Git and GitHub CLI (portable) | `D:\tools\mingit\cmd\git.exe`; `D:\tools\gh` (gh.exe under `gh_2.103.3_windows_amd64\bin`) |
| Global git exception | `D:\tools\mingit-global.gitconfig` (`safe.directory` for `D:/projects/Friday`) — required for every git/gh call |
| Ollama (portable, D:-only) | `D:\tools\ollama\ollama.exe` (v0.40.15); not on PATH. `ollama serve` running as hidden process on localhost:11434; both models pulled and tagged (llama3:latest 4.66 GB, llava:latest 4.73 GB); OLLAMA_MODELS=`D:\ollama\models` |
| Ollama model store | `D:\ollama\models` (user-level `OLLAMA_MODELS`) |
| faster-whisper base (int8) | `D:\tools\voice_models\whisper\models--Systran--faster-whisper-base\snapshots\<hash>\` (model.bin etc.; loaded and transcribed a pyttsx3-generated "Hello world." fixture correctly on 2026-11-07) |
| OpenWakeWord ONNX assets | `D:\python_3.12\Lib\site-packages\openwakeword\resources\models\` (feature/VAD models auto-downloaded; `friday.onnx` at repo root is the custom wake classifier — [1,16,96] float → [1,1] probability; loads and predicts via openWakeWord) |
| Tesseract OCR 5.4.0 | `C:\Program Files\Tesseract-OCR\tesseract.exe` — installed on C: by the official installer which ignored the D: redirect; owner approved keeping it on C: (2026-11-07). `config.TESSERACT_CMD` uses it (D: path preferred if present). OCR verified end-to-end offline |
| FFmpeg | `D:\tools\ffmpeg\bin\ffmpeg.exe` / `ffprobe.exe` — BtbN master-latest win64-gpl build, installed and verified 2026-11-07 (lavfi sine encode → ffprobe round-trip succeeded; `config.FFMPEG_LOCATION` resolves to it; `--ffmpeg-location` wired for yt-dlp) |
| yt-dlp | `D:\python_3.12\Scripts\yt-dlp.exe` (version 2026.03.17, verified 2026-11-07); not on PATH — `config.YT_DLP_PATH` resolves it absolutely (override with the `YT_DLP_PATH` env var) |
| App data (gitignored) | `memory.db` (tasks), `friday_memory/` (Chroma), `friday_data/`, `temp_audio/`, `screenshots/` |
| Test output (tracked) | `tests/results/latest.{txt,json}`, `tests/RESULTS.md` |
| OpenCode temp workspace | `C:\Users\Samarth\AppData\Local\Temp\opencode` |
| Language/session | Windows account `DESKTOP-GQN46T5/Samarth`; WINDOWS_USER=`Samarth`; ALLOWED_ROOTS=`D:/projects`, `C:/Users/Samarth` |

### Owner instructions and standing constraints

These were explicitly set by the project owner and take precedence:

- **Install everything on D:** whenever possible (Ollama, tools, models). Ask before installing anything on C: or changing system-wide settings. (Exception granted 2026-11-07: Tesseract remains on `C:\Program Files\Tesseract-OCR` at the owner's request.)
- **Weather uses open-source tooling** — now Open-Meteo (no key); do not reintroduce a key-gated weather API.
- **Never commit secrets** (credentials.json, tokens, keys). The repo is public; the OpenWeather key was removed from source entirely and survives only in the unused `OPENWEATHER_API_KEY` user environment variable.
- **Never reproduce keys or token values** in this README or any file.
- **Keep this README synchronized** with project status: what was done, where things live, what the owner said to do or not do, and test results — update it in the same task as the change.
- **Tests:** offline suite must stay green before committing; use mocks/temp fixtures; live/desktop/OAuth actions need explicit deliberate verification and owner participation.
- **Dependencies:** install only into `D:\python_3.12` unless told otherwise; `D:\tools` for machine tooling.
- **git identity:** commits authored as `samarth3134 <108995242+samarth3134@users.noreply.github.com>`; the remote requires the `GIT_CONFIG_GLOBAL` exception (see source control).

Music needs FFmpeg and yt-dlp, both resolved to absolute D: paths by the app (`config.FFMPEG_LOCATION` for yt-dlp's conversion step, `config.YT_DLP_PATH` for the playback CLI); neither needs to be on PATH. OCR needs Tesseract (installed at `C:\Program Files\Tesseract-OCR`). WhatsApp needs the Windows Desktop app signed in. Voice and the wake listener are fully offline (faster-whisper + openWakeWord; no internet needed — just a microphone).

For Google integrations, enable Gmail and Calendar APIs, provide Desktop App OAuth credentials in credentials.json, and complete authorization. Gmail requests readonly/send/modify scopes; Calendar requests calendar access.

Run from the project directory because storage paths are relative:

```powershell
cd D:\projects\Friday
python main.py
```

The main app launches at **http://localhost:7862**. Running ui.py directly uses Gradio defaults and skips the full startup sequence. Startup starts the microphone listener and WhatsApp. Dashboard refresh does not activate WhatsApp or other apps; Google services may open an OAuth flow.

### Current machine: dependencies

Metadata and imports were checked with **D:\python_3.12\python.exe (Python 3.12.10)** on 2026-11-07. On 2026-11-07 at ~10:20 `screen-brightness-control` and `google-auth-oauthlib` were installed into that interpreter, closing the gap from the morning audit. All 28 directly listed distributions now import cleanly (including gradio, pygame-ce, chromadb, pyaudio, and pytesseract). Import verification proves the modules load; it does not prove live functionality (Ollama models, OAuth, microphone, WhatsApp Desktop), which remains unverified.

`D:\python_3.12` and `D:\python_3.12\Scripts` are absent from this session's PATH; `yt-dlp.exe` exists there (verified 2026-11-07, version 2026.03.17). The app resolves yt-dlp and FFmpeg itself (`config.YT_DLP_PATH` → `D:\python_3.12\Scripts\yt-dlp.exe`, overridable via the `YT_DLP_PATH` environment variable; FFmpeg via `config.FFMPEG_LOCATION`). Adding both folders to PATH is only needed for calling the tools directly from a shell, not for Friday to run.

Ollama was **not installed** on 2026-11-07; a D:-only portable build (**v0.40.15**, `D:\tools\ollama\ollama.exe`) was installed the same day after confirming no existing installation anywhere on the machine. Models live on D: via the user-level `OLLAMA_MODELS=D:\ollama\models` environment variable (set 2026-11-07). A hidden `ollama serve` is running on localhost:11434. Both required models are pulled and visible via `GET http://localhost:11434/api/tags` (llama3:latest, 8.0B Q4_0, 4.66 GB; llava:latest, 7B clip, 4.73 GB) on 2026-11-07. The portable build is not on PATH and does not spawn a desktop app; Ollama must be started explicitly (`D:\tools\ollama\ollama.exe serve`, or just run `ollama` commands, which talk to localhost:11434). A live generate smoke test has not been run (deliberately, per the owner's live-testing rule). FFmpeg (BtbN master-latest win64-gpl build, `D:\tools\ffmpeg\bin`) installed and verified 2026-11-07: an offline lavfi sine encode and an ffprobe round-trip both succeeded; `yt-dlp` 2026.03.17 is present at `D:\python_3.12\Scripts\yt-dlp.exe` (that folder is not on PATH, so adding it or launching Friday with the full path is required for music's CLI path). Tesseract 5.4.0 is installed at `C:\Program Files\Tesseract-OCR` (owner-approved). WhatsApp Desktop was not returned by the current-user app package check. OAuth validity and microphone access remain unverified.

External prerequisites: Ollama (on this machine, the D:-only portable build at `D:\tools\ollama`; otherwise [Ollama for Windows](https://ollama.com/download/windows)) with `llama3` and `llava`; [FFmpeg/ffprobe binaries](https://ffmpeg.org/download.html) for MP3 conversion; [Tesseract engine](https://pypi.org/project/pytesseract/) for OCR; signed-in WhatsApp Desktop; Google OAuth/API configuration. Weather needs **no API key** (it uses [Open-Meteo](https://open-meteo.com/), open-source). [yt-dlp documents its external dependencies](https://pypi.org/project/yt-dlp/); current YouTube support may also require its JavaScript runtime setup.

## Configuration and stored assets

- Ollama endpoint: localhost:11434; models: llama3 and llava.
- User name: Boss. Weather city: Bengaluru. Weather currently uses Fahrenheit and miles per hour.
- Allowed file roots: D:/projects and C:/Users/Samarth (updated for the current Windows account on 2026-11-07). Natural-language user-folder defaults now resolve to the Samarth profile via WINDOWS_USER.
- File output limit: 50,000 characters; long files return beginning/end excerpts.
- Write/move/delete confirmation flags are enabled; a confirmation-resume flow exists (ask Friday to do the operation, then answer yes/confirm or cancel; pending state lives in filesystem._pending).
- memory.db stores tasks; friday_memory/ stores Chroma memories and vectors.
- credentials.json, gmail_token.json, calendar_token.json contain private Google credentials/tokens and are gitignored.
- Weather provider: [Open-Meteo](https://open-meteo.com/) (open-source, no API key); city: Bengaluru; Fahrenheit and miles per hour. The OpenWeather key has been removed from config.py and source; the old key survives only in the unused `OPENWEATHER_API_KEY` user-level environment variable on this machine (harmless; delete it manually if you want it gone).
- temp_audio/current_track.mp3 is the music playback file. screenshots/ is created on demand.
- friday.onnx, friday.tflite, and five friday_sample WAV files exist but are not used by the current wake listener.
- __pycache__/ contains generated files, including an old training-module cache without corresponding source.

### Dependency licenses and cost

Owner decision (2026-11-07): everything used must be open-source or free — nothing may cost money. The stack was audited against this:

- **Open-source:** Python 3.12, Ollama (llama3, llava), ChromaDB, Gradio, pygame, pyttsx3, pyautogui/PyGetWindow/pycaw/pytesseract/send2trash, yt-dlp/ytmusicapi, Open-Meteo (weather, no key), SQLite, **faster-whisper** and **openWakeWord** (voice + wake listener, fully offline since 2026-11-07), all internal modules.
- **Free tier, proprietary (accepted by owner 2026-11-07 — no payment ever required):** Gmail and Google Calendar APIs (OAuth, read/send/modify + calendar), DuckDuckGo web search, WhatsApp Desktop automation. Google Speech Recognition was removed from the stack on 2026-11-07.

## Known gaps and next work

1. New Google Cloud project **friday** (project number 754753940977) created 2026-11-07; Gmail API and Calendar API enabled; `credentials.json` swapped to that project's Desktop client (new `client_secret_754753940977-...json`). The old client (project …681978, different client) and the May-2026 tokens are backed up locally as `*.bak-2026-11-07` (gitignored) and will be superseded on first consent — Friday must be restarted and both consents clicked (`unread email`, then `calendar today`); expect an unverified-app warning (click Advanced → continue). If any call returns `403 access_blocked`, the project's OAuth consent screen needs your email under Test users (or the app Published to Production).
2. First live run (2026-11-07): Ollama, Chroma memory, task DB, Gradio and the wake listener all came up on localhost:7862. A raw `The system cannot find the path specified.` line printed during WhatsApp startup — WhatsApp Desktop appears to be absent on this machine; it does not stop the app, but the message should be a clean "WhatsApp not installed" note (cosmetic). WhatsApp reading/unread counts remain honest placeholders (no passive unread API exists for desktop automation), and sending is unverified.
3. Voice and wake detection are now fully offline (faster-whisper `base` + openWakeWord `friday.onnx`; no internet required, all open-source). Command handling and speech still block the wake loop, limiting interruption support. `friday.onnx` scores below `WAKE_WORD_THRESHOLD` (0.5) do not fire; false-positive profile on real mic input is unmeasured.
4. Music queue routing (add/clear) is implemented and offline-tested; queue order, concurrent enqueue and failed-track skip behavior remain unverified.
5. File mutations are now confirmation-gated with a pending-operation flow (yes/confirm executes once, cancel aborts); send2trash failure paths and moves onto existing destinations remain unverified paths — mutation errors do not falsely report success in the covered cases.
6. `requirements.txt` exists but is unpinned and clean installation is unverified. Broad exception handling hides diagnostic details.
7. Dashboard status is cached for 60 seconds (dashboard.STATUS_CACHE_TTL_SECONDS), so the dashboard can lag live state by up to a minute; external services are no longer hit every second.
8. Ollama prerequisites are met (server running; llama3 and llava both pulled and verified on localhost:11434). FFmpeg installed and verified offline at `D:\tools\ffmpeg\bin`, wired into the app (`config.FFMPEG_LOCATION`, `--ffmpeg-location`). A live generate smoke test and any live integration checks remain deliberately unrun (per the owner's rule).
9. Previously reproduced defects (intent collisions, calendar timezone/pagination/duration handling, task due-date/priority parsing, duplicate preferences, microphone failure reporting, OCR double captures, WhatsApp timeout/failsafe/report-hygiene, missing pending-confirmation workflow, dashboard per-second external calls) are fixed and covered by regression tests in tests/RESULTS.md. The weather system no longer depends on a key-gated API; Open-Meteo day grouping is city-local via `timezone=auto`.

## Function and acceptance-test checklist

Checked items passed offline tests on 2026-11-07. External services, devices, OAuth, process launches, and Chroma are mocked; checks establish code behavior, not live integration readiness. SQLite and plain-file tests use real temporary fixtures. Unchecked means failed, partly covered, or not verified; consult tests/RESULTS.md and the detailed test log. Check a box only after recording the test and result. Known bugs remain unchecked until fixed and verified. Use mocks and temporary storage for automated tests; desktop/external actions need deliberate integration tests.

### Startup and configuration — main.py, config.py

- [x] check_ollama: healthy endpoint proceeds; timeout, refused connection, and HTTP errors give useful setup guidance.
- [x] main/initializers: missing optional dependencies do not prevent usable text mode; required failures are clearly reported.
- [x] launch_dashboard: mocked launch requests port 7862; simulated occupied-port/Gradio failure enters terminal fallback. Actual browser rendering remains unverified.
- [x] terminal_loop: blank input is ignored; exit, quit, EOF, and Ctrl+C terminate cleanly.
- [x] Configuration: paths resolve for the current Windows user; missing keys/models are reported without revealing secrets.

### Intent classification and routing — brain.py

- [x] classify_intent: canonical examples cover all 22 currently reachable intents and uppercase/punctuation variants. Collision handling is tested separately below.
- [x] Collision regressions: list tasks -> task; show weather -> weather; show calendar -> calendar; playlist request -> music; music volume -> intended music control.
- [x] File intent regressions: list folder, find file, read file, open file, create file, and delete file remain distinct.
- [x] Extractors: quoted paths, spaces, Windows drive paths, natural folder names, and missing arguments produce correct values or clarification.
- [x] respond/process/handle/chat: empty/non-string input is safe; aliases behave consistently; tool exceptions produce useful failures.
- [x] _ollama: valid response, empty response, malformed JSON, timeout, missing model, and HTTP errors are handled.
- [x] Memory context and conversation saving: retrieval/save failures do not break replies; one exchange is saved per request.
- [ ] _route_*: each handler calls the intended function with correct parsed arguments, using mocked modules and no real side effects.

### Files — filesystem.py

- [ ] _check_path: allow valid roots; reject outside roots, blacklisted directories, traversal, and symlink/junction escapes.
- [x] find_file/list_dir: match names, sort folders/files, handle empty/missing/unreadable paths and nested folders.
- [ ] read_file: fixtures for text, JSON, CSV, PDF, DOCX, XLSX, unsupported extensions, invalid encoding, and directories.
- [x] _cap_output: short files remain intact; long output includes expected start/end excerpts and accurate labeling.
- [x] write_file/move_file/delete_file: request approval, preserve pending arguments, execute once after confirmation, and cancel cleanly. Pending requests store resolved path/content/destination in filesystem._pending; brain routes yes/confirm/cancel to it. Verified by offline tests.
- [ ] Mutation errors: permission failures, existing destinations, missing sources, and trash failures do not falsely report success; use temporary fixtures.
- [x] open_file: platform command dispatch is correct with process launch mocked.

### Tasks — tasks.py

- [x] _init_db/add_task: fresh temporary database initializes; blank titles fail; valid titles, due dates, priorities persist.
- [x] list_tasks: all/pending/done/today filters and ordering match seeded records, including empty results.
- [x] complete_task/delete_task: numeric ID and exact title work; missing and already-completed tasks respond correctly.
- [x] get_overdue: yesterday is overdue, today/future are not, completed tasks are excluded.
- [x] Router integration: add task with date/priority, complete task 1, delete task 1, and list tasks reach correct operations.

### Memory — memory.py

- [x] save_memory: correct text, ID, timestamp and fact/preference metadata sent to mocked Chroma; empty input ignored. Real embedding/storage remains unverified.
- [x] search_memory: mocked result mapping includes text/metadata/distance; empty results and invalid queries are safe.
- [ ] search_memory: verify real Chroma embeddings, relevance and empty-collection behavior.
- [x] save_conversation/get_recent: mocked records pair roles correctly, preserve chronology and return the last N pairs.
- [ ] save_conversation/get_recent: verify real persistent storage survives restart.
- [x] Remember requests: avoid duplicate preference records; Chroma failures degrade gracefully. Use an isolated collection.

### Voice and wake listener — voice.py, wakeword.py

- [x] listen: transcription, silence timeout, microphone failure and transcription failure. Offline engine: capture via sounddevice + energy threshold; decode via faster-whisper `base` (int8, CPU).
- [ ] speak/stop_speaking: playback completes, cancellation works, repeated calls and concurrent requests do not deadlock.
- [x] _heard_friday: openWakeWord inference of the bundled `friday.onnx`; scores below `WAKE_WORD_THRESHOLD` (0.5) do not fire; device failures degrade to no wake (not a crash); inline startup highlights and false-positive profile still to be measured live.
- [ ] start: repeated calls create only one listener; failed device initialization reports a useful state.
- [x] _handle_detection: idle -> listening -> thinking -> speaking -> idle; no-command and exception paths recover.
- [x] Voice/UI handoff: each recognized command/response appears once, without stale or mismatched pairs.
- [ ] Interruption and shutdown: test wake during speech and clean thread/device release; implement missing lifecycle support as needed.

### UI and dashboard — ui.py, dashboard.py

- [ ] build_app: supported Gradio version renders tabs, CSS, chat, buttons, and timers.
- [x] _append_response/_mic_response: mocked submits preserve history, empty input adds no messages, and successful microphone input is routed.
- [x] _mic_response: explain microphone failure visibly (previously returned only a generic handler label; the fix shows a "could not hear" explanation).
- [x] _format_status: escapes service content and handles unavailable services/missing memory.
- [x] get_status: slow/failing integrations do not block the entire UI; refreshes use caching and avoid unintended desktop focus changes. (Status is cached for 60 seconds in dashboard.STATUS_CACHE_TTL_SECONDS; the timer can serve data up to one minute old.)
- [ ] _chat_tick: concurrent submissions/timers do not lose or duplicate chat messages; separate browser sessions stay consistent.
- [ ] Unread email display: distinguish actual total from the maximum five fetched previews.

### Search and weather — search.py, weather.py

- [x] web_search/news_search: format up to five title/snippet/URL results; clean markup; handle empty results and network errors.
- [ ] Search routing: expected query is extracted and results reach Ollama; failure is represented honestly.
- [x] get_weather: valid city, geocoding failure, timeout, and malformed response.
- [x] get_forecast: groups days correctly and reports units; city-local day grouping is requested via Open-Meteo `timezone=auto` (verified offline with the request parameters).
- [x] should_bring_jacket: cold, warm/dry, and wet (rain/drizzle/thunderstorm) cases via WMO weather codes with explicit unit assumptions.
- [x] City parsing: lowercase and multiword city names work.

### Music — music.py

- [x] _search_track/play: found song, no result, missing video ID, absent dependencies, failed download, and missing FFmpeg.
- [x] Successful play updates now_playing with correct title/artist; replacing a track handles locked files safely.
- [x] pause/resume: resume preserves position; pausing does not accidentally advance the queue.
- [ ] add_to_queue/clear_queue/skip: queue order, empty queue, failed track, and concurrent enqueue behave correctly. (Routing from brain is implemented and covered by offline tests; queue order, empty queue and pause/clear dispatch are verified; failed-track skip and concurrent enqueue remain unverified.)
- [x] set_volume: clamps 0-100 and handles invalid input; play_mood maps supported moods and rejects unknown ones.
- [x] previous returns an honest unsupported response; failures never falsely announce successful playback.

### Gmail and WhatsApp — messaging.py, whatsapp_desktop.py

- [x] OAuth: missing credentials, first authorization, refresh, revoked token, and API failure; automated tests use fake credentials/services.
- [x] gmail_get_unread/gmail_search: empty/multiple results, limits, sender/subject/snippet extraction, and query forwarding.
- [x] gmail_read/_extract_body: plain text, nested multipart, HTML-only, base64 padding, and non-ASCII content.
- [x] gmail_send: mocked request contains correct recipient/subject/body and handles API errors without claiming success.
- [x] Gmail functions remain available when WhatsApp dependencies are missing.
- [x] WhatsApp startup: missing app/window and activation failure time out accurately without endless waits.
- [x] wa_read_chat/wa_get_unread: clearly state current limitations; do not claim to have retrieved unread counts or text.
- [ ] wa_send: verify intended recipient, Unicode text, focus, and actual send outcome; mock keystrokes by default and use only a deliberately chosen test chat for live validation.

### Calendar — calendar_integration.py

- [ ] get_today/get_upcoming: correct local-day boundaries, timezone offsets, empty results, recurring events, and pagination.
- [x] create_event: valid date/time/duration, invalid input, correct IANA timezone, and API error handling.
- [x] delete_event: exact title/date lookup, no match, duplicate titles, and failed deletion.
- [x] find_free_slots: empty day, overlapping events, all-day events, events outside work hours, fully booked days, and timezone conversion.
- [ ] Router: create/delete commands with today or other overlapping keywords do not accidentally become list requests.

### Vision — vision.py

- [ ] analyze_image/identify_object: valid fixture, missing path, directory, unsupported/corrupt image, and Ollama errors.
- [x] _ask_ollama: correct model, base64 image and prompt; empty response, timeout, and HTTP errors.
- [x] analyze_screen/explain_error: capture mocked screenshot, use intended prompt, and recover from capture failure.
- [x] read_text_from_screen: readable text, blank image, absent Tesseract, and OCR failure; avoid duplicate unnecessary captures.

### System controls — system_control.py

- [ ] open_app/_find_windows_app: known aliases, PATH discovery, missing app, protocol launch, and window positioning with mocks.
- [x] close_app/list_running_apps: exact intended targets, unavailable process metadata, permission failures, and no matches.
- [x] set_volume/mute/unmute/set_brightness: supported platform dispatch, bounds, missing dependencies, and device failures.
- [x] take_screenshot: unique filenames and clear permission/capture errors.
- [x] click/type_text/hotkey: validate arguments; test dispatch with mocked desktop APIs.
- [x] lock_screen/shutdown/restart/cancel_shutdown/sleep_mode: validate command construction and delays using mocks only; never execute power actions incidentally during tests.

### Project-wide acceptance

- [ ] Add a reproducible dependency manifest and verify clean installation. (requirements.txt added 2026-11-07; it is unpinned and clean installation is still unverified.)
- [x] Add focused automated tests with isolated databases, mocked network/desktop APIs, and deterministic dates.
- [ ] Verify unavailable integrations leave chat usable and expose diagnostic errors without leaking secrets.
- [ ] Verify startup/shutdown and concurrent voice/chat/dashboard behavior in a deliberate manual smoke test.
- [x] Keep this checklist, setup notes, known gaps, and change log synchronized with every meaningful change.

## Test record

Run on **2026-11-07** with the user's Python 3.12.10:

```powershell
& D:\python_3.12\python.exe -B tests/run_tests.py
```

**124 test methods: 124 passed, 0 failed, 0 errors, 0 skipped.** The 23 methods that failed earlier the same day (27 failing assertions) were fixed in source and now pass, along with 6 new regression tests (task-router integration, music queue routing, pending-file-confirmation interception, filesystem pending flow, forecast city timezone, dashboard status cache). Exit code 0 is expected while the documented regressions stay fixed.

See [tests/RESULTS.md](tests/RESULTS.md), [full test output](tests/results/latest.txt), and [machine-readable results](tests/results/latest.json). Tests use stdlib unittest and mocks, plus temporary SQLite/file fixtures. The runner blocks real socket connections and subprocess/app launches. Application source, real databases, credentials, and user files were not changed by the test run.

Live OAuth, message delivery, audio hardware, rendered Gradio UI, Chroma embeddings/persistence, full document fixtures, symlink/junction restrictions, concurrency and clean installation remain unverified. Checked items have the offline scope stated above; partially tested broad requirements remain unchecked.


## Change log

### 2026-11-07 — Voice and wake listener rebuilt fully offline (open-source)

- Owner replaced Google Speech Recognition with a fully offline, open-source stack; decision supersedes the earlier "keep Google STT" choice.
- `voice.py`: `listen()` now captures from the microphone via sounddevice (energy-threshold VAD, stops after configurable silence) and transcribes with **faster-whisper** `base` (int8, CPU, model in `D:\tools\voice_models\whisper`, downloaded 2026-11-07). Verified end-to-end offline: a pyttsx3-synthesized "hello world." wav round-trips through `faster-whisper` → transcript "Hello world."
- `wakeword.py`: the STT-window hunting loop is replaced with **openWakeWord** streaming inference of the bundled custom `friday.onnx` ([1,16,96] float input → [1,1] probability; verified to load and predict in `openwakeword.Model(inference_framework="onnx")`), threshold `WAKE_WORD_THRESHOLD=0.5`. Online only to warm the beep (synthesized locally with numpy + sounddevice).
- `requirements.txt`: removed `SpeechRecognition` and `pyaudio`; added `faster-whisper` and `openwakeword`.
- Note: `av` 19.0.2 removed the `metadata_errors` kwarg that faster-whisper 1.2.1 passes on the file-path decode path; the app always passes raw float32 numpy audio, which bypasses that code path. Revisit pins when doing the clean-install verification.
- Tests rewritten for the offline engines (`tests/test_interactions.py` VoiceTests/WakeTests mock `_record_until_silence`, `_get_whisper_model`, `_ensure_oww`, and `sounddevice.InputStream` instead of `speech_recognition`). Suite re-verified: **124 test methods, all passing**.
- README synchronized (architecture, prerequisites, machine layout, audit table, gaps, checklist items, this entry).
- Known follow-ups: live mic test, `friday.onnx` false-positive rate on real input, interruption support (still blocked wake loop).

### 2026-11-07 — New Google Cloud project "friday"; credentials swapped

- Owner created a new Google Cloud project **friday** (project number **754753940977**) with a Desktop OAuth client and downloaded its JSON to `C:\Users\Samarth\Downloads\`. `credentials.json` was backed up (`credentials.json.bak-2026-11-07`) and swapped for the new client; the May-2026 tokens (bound to the old client) were backed up (`gmail_token.json.bak-2026-11-07`, `calendar_token.json.bak-2026-11-07`). All backups are gitignored via the new `*.bak-*` rule; `.gitignore` was updated before any staging so these never entered history.
- Friday must be restarted and both consents re-clicked (`unread email`, `calendar today`). The consent screen will show an "unverified app" warning → Advanced → continue (personal use, one account).
- README synchronized; no secrets in source, docs or history (credentials are gitignored and were never committed).

### 2026-11-07 — OAuth re-authorization fallback; owner licensing audit

- First live boot succeeded (Ollama, memory, tasks, Gradio, wake listener). Both Google tokens (stored in May) are revoked (`invalid_grant`); the Gmail and Calendar auth paths now fall back to the browser consent flow automatically when refresh fails, instead of failing with the misleading "put your client credentials at ./credentials.json" guidance, which also no longer prints when a stored token exists (it now says to approve the consent screen).
- `tests/test_services.py` OAuthTests updated to the new semantics (refresh mocks mark the creds valid as real refreshes do; revoked-refresh falls back to a fresh flow; added a post-fallback flow-failure sub-scenario). Suite re-verified: **124 test methods, all passing**.
- Owner decisions recorded: all components must be open-source or free ($0). Audit table added under "Dependency licenses and cost"; voice (Google STT), Gmail/Calendar APIs, WhatsApp automation, and DuckDuckGo search were all kept by the owner as free-tier/proprietary choices; open-source replacements were declined (self-host CalDAV/IMAP+SMTP, openWakeWord + faster-whisper, SearXNG). Nothing in the stack costs money.
- WhatsApp Desktop appears absent on this machine (raw path error at startup; app continued; noted as known gap).
- Committed and pushed alongside.

### 2026-11-07 — yt-dlp path resolved in-app

- `music.py` no longer assumes `yt-dlp` is on PATH; `config.YT_DLP_PATH` resolves it absolutely (D:\python_3.12\Scripts\yt-dlp.exe; verified 2026-11-07, version 2026.03.17) with a `YT_DLP_PATH` environment-variable override and a `yt-dlp` PATH fallback. PATH additions are now optional for direct CLI use only.
- Suite after `config.py`/`music.py` edits: **124 test methods: 124 passed, 0 failed**. README synchronized (setup PATH note, music prerequisites, machine-layout table).

### 2026-11-07 — Tesseract verified end-to-end; FFmpeg install started; tooling wired into the app

- Tesseract OCR 5.4.0 installed (`C:\Program Files\Tesseract-OCR\tesseract.exe` — the official installer ignored the D: redirect; owner approved keeping it on C: on 2026-11-07). `config.TESSERACT_CMD` prefers `D:\tools\tesseract\tesseract.exe`, then the C: path, then PATH (all overridable via the `TESSERACT_CMD` env var).
- `vision.py` now sets the module-global on `pytesseract.pytesseract` (setting `pytesseract.tesseract_cmd` only rebinds the package namespace and had no effect — the worker module reads its own `tesseract_cmd` global).
- OCR verified end-to-end offline: tesseract v5.4.0 spawns through the app's config and reads a fixture image created with PIL ("FRIDAY 2026" read back as "rRupay 2026" at the tiny default font size — the engine is fine; use normal-sized UI text for decent OCR).
- FFmpeg essentials build (~115 MB) download/install to `D:\tools\ffmpeg\bin` in progress 2026-11-07; upon completion `config.FFMPEG_LOCATION` (verified by its own existence check) exposes the directory to `music.py`, which passes it as yt-dlp's `ffmpeg_location` option and as `--ffmpeg-location` on the CLI path; `_ffmpeg_available()` checks the same path first, then PATH.
- Suite re-run after `config.py`/`music.py`/`vision.py` edits: **124 test methods: 124 passed, 0 failed**.
- Note: a hidden `ollama serve` is running on localhost:11434; `llama3` and `llava` pulls completed **2026-11-07** (llama3 4.66 GB, llava 4.73 GB, both verified via `GET /api/tags`). Earlier pull attempts were interrupted by a shell restart; the final attempt resumed from the cached blob.
- Both required Ollama models are available locally; FFmpeg install to D:\tools\ffmpeg was completed from the GitHub BtbN builds after the gyan.dev download stalled, and verified offline (sine → MP3 round-trip through ffmpeg/ffprobe) on 2026-11-07 — yt-dlp CLI (used by music's playback path) additionally needs `D:\python_3.12\Scripts` on PATH or the full yt-dlp path; `yt-dlp 2026.03.17` is present there.

### 2026-11-07 — Weather migrated to Open-Meteo (open-source, no API key)

- `weather.py` rewritten for [Open-Meteo](https://open-meteo.com/): geocoding-api.open-meteo.com resolves the city (lat/lon, city name, timezone); api.open-meteo.com returns current conditions and the 5-day forecast in one pair of requests. WMO weather codes are mapped to text; temperature is Fahrenheit, wind in mph (as before); forecast days are city-local via the API's `timezone=auto` parameter (replacing the manual UTC-offset grouping).
- `OPENWEATHER_API_KEY` is no longer read anywhere; the constant and configuration surface are gone from the source tree. The user-level `OPENWEATHER_API_KEY` environment variable was left untouched (it is the only copy of the old key and is now unused).
- `tests/test_services.py` WeatherTests rewritten for the new provider (success + units/parameters, blank-city/timeout/geocode-miss/malformed paths, jacket logic via WMO codes, forecast grouping and units, and the `timezone=auto` request contract). Suite re-run: **124 test methods: 124 passed, 0 failed**.
- README updated: machine layout/paths section, owner instructions section, source control, dependencies, configuration, prerequisites (weather needs no key), checklist items re-worded, known gaps and this entry kept in sync.
- Committed and pushed to https://github.com/samarth3134/Friday (public) as the changes land; see git log for revisions.

### 2026-11-07 — Git repository, GitHub remote, and Ollama install (D:-only)

- Created public repository **https://github.com/samarth3134/Friday** from this directory (branch `main`); initial import c5d7e28 (34 files, no secrets — verified by pattern scan; `.gitattributes` LF normalization added; `.gitignore` now effective because the folder is a repository).
- Moved the OpenWeather key out of `config.py` into the `OPENWEATHER_API_KEY` user-level environment variable (extracted from the stale compiled cache; value never printed or committed). The key is absent from source and history.
- Installed MinGit 2.56.0.windows.4 and GitHub CLI 2.103.3 portable in `D:\tools`; gh authenticated as `samarth3134`. `GIT_CONFIG_GLOBAL=D:\tools\mingit-global.gitconfig` carries a `safe.directory` exception for this folder's ownership/SID mismatch; git is not on PATH, call `D:\tools\mingit\cmd\git.exe` or add it to PATH.
- Confirmed Ollama was not installed anywhere, then installed the D:-only portable build **v0.40.15** (`D:\tools\ollama`); set user-level `OLLAMA_MODELS=D:\ollama\models`; started `ollama serve` and began `llama3`/`llava` pulls on 2026-11-07 — verify with `ollama list` before live tests.
- This entry was committed and pushed; tests remain 124/124 green (no source behavior changes in this round).

### 2026-11-07 — Regression fixes, documentation sync, and gap implementations

- Morning run recorded 23 failing methods; those were fixed in source (word-boundary intent matching with file/service priority rules, calendar IANA timezone creation/local-day bounds/pagination/negative-duration and all-day free-slot handling, task due-date/priority extraction and identifier parsing, music now_playing after playback and locked-file replacement, bounded WhatsApp startup with immediate cause reporting and preserved PyAutoGUI failsafe, lazy WhatsApp import in messaging.py, single OCR capture, visible mic failure explanation, one preference per remember request, dashboard no longer drives WhatsApp UI, honest unverified-send reporting). Re-run: 124 methods, all passing.
- Full offline suite re-verified at 10:14 and 11:00 (124 methods, 0 failures). README checklist items covered by passing tests were checked; partially covered or unverified items remain unchecked.
- Installed `screen-brightness-control` and `google-auth-oauthlib` into D:\python_3.12; all 28 listed distributions import cleanly in that interpreter (verified directly, not just metadata).
- Implemented and tested the file-mutation confirmation workflow: pending write/move/delete requests are stored (resolved path/content/destination) and executed exactly once on `yes`/`confirm`; `cancel` discards them; `brain` intercepts plain yes/no answers before intent classification.
- Dashboard `get_status` is cached for 60 seconds (dashboard.STATUS_CACHE_TTL_SECONDS) with an explicit `clear_status_cache()`; the 1-second UI timer no longer calls external services every tick.
- Music queue routing: `add X to (the) queue` / `put X on (the) queue` / `add to queue X` → `add_to_queue`; `clear (the) queue` → `clear_queue`. `skip`/`previous` were already routed.
- Weather forecast day grouping now uses the city's UTC offset from OpenWeather's `city.timezone` field (server-local time remains the fallback when the field is absent); covered by an offline test.
- Task-router integration tests added (delete task 1, list tasks, list overdue tasks); forecast and cache behavior covered by new regression tests.
- Configuration for the current Windows account: `ALLOWED_ROOTS` is now `D:/projects` and `C:/Users/Samarth`; `WINDOWS_USER` = `Samarth`.
- Added unpinned `requirements.txt` (import-derived; clean install unverified) and `.gitignore` (no effect until this directory is a git repository).
- Ollama is **not** installed; a D:-only portable installation was started 2026-11-07 (see known gaps). No FFmpeg/Tesseract locations were found. Live OAuth, WhatsApp delivery, audio hardware, rendered Gradio UI, and Chroma persistence remain unverified.
- Next work: finish the Ollama installation and pull llama3/llava (started 2026-11-07; verify with `ollama list`), then perform deliberate live integration checks once configuration is ready; keep this README synchronized with test results.

### 2026-11-07 — Offline tests and installed-package audit

- Added 103 offline test methods across all feature areas; checked passing acceptance items and left failures/partial coverage unchecked.
- Recorded 80 passing methods and 23 failing methods (27 failure assertions); no harness errors or skips.
- Added an isolated test runner and detailed result files. No application behavior was changed or bugs fixed.
- Inspected distribution metadata in D:\python_3.12: screen-brightness-control and google-auth-oauthlib are missing; documented PATH/external-tool limits and installation commands.
- Next work: fix reproduced regressions, rerun the suite, then perform deliberate live integration checks once dependencies/configuration are ready.

### 2026-11-06 — Project context and acceptance checklist

- Read all 18 source modules and mapped startup, routing, storage, and integrations.
- Replaced stale Spotify, Picovoice, WhatsApp Web, and port instructions with current source-based descriptions.
- Documented known implementation gaps and a feature-by-feature acceptance-test checklist.
- Added AGENTS.md instructions to read this file first and update it alongside future changes.
- Validation: documentation compared against source; application code unchanged; no app launch or integration tests performed.
