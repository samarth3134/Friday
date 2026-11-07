import csv
import json
import os
import platform
import shutil
import subprocess
from pathlib import Path

from config import (
    ALLOWED_ROOTS,
    BLACKLISTED_PATHS,
    MAX_READ_CHARS,
    REQUIRE_CONFIRM_ON_DELETE,
    REQUIRE_CONFIRM_ON_WRITE,
)


PLAIN_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".py", ".js", ".html"}

# Holds a single write/move/delete request that awaits the user's confirmation.
_pending = None


def has_pending():
    return _pending is not None


def cancel_pending():
    global _pending
    if _pending is None:
        return "There is nothing to cancel."
    operation = _pending
    _pending = None
    if operation["action"] == "write":
        return f"Cancelled the write to {operation['path']}."
    if operation["action"] == "move":
        return f"Cancelled the move from {operation['source']} to {operation['destination']}."
    return f"Cancelled the delete of {operation['path']}."


def confirm_pending():
    global _pending
    if _pending is None:
        return "There is no action waiting for your confirmation."
    operation = _pending
    _pending = None
    if operation["action"] == "write":
        return _write_now(operation["path"], operation["content"], operation["mode"])
    if operation["action"] == "move":
        return _move_now(operation["source"], operation["destination"])
    return _delete_now(operation["path"])


def _write_now(resolved, content, mode="w"):
    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, mode, encoding="utf-8") as file:
            file.write(content)
        return f"I wrote to {resolved.name}."
    except Exception:
        return f"I could not write to {resolved.name}."


def _move_now(source, destination):
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        return f"I moved {source.name} to {destination}."
    except Exception:
        return f"I could not move {source.name}."


def _delete_now(resolved):
    try:
        from send2trash import send2trash

        send2trash(str(resolved))
        return f"I moved {resolved.name} to the trash."
    except Exception:
        return f"I could not delete {resolved.name}."


def _resolve(path):
    return Path(path).expanduser().resolve()


def _is_blacklisted(path):
    resolved = _resolve(path)
    for blacklisted in BLACKLISTED_PATHS:
        blocked = _resolve(blacklisted)
        if resolved == blocked or blocked in resolved.parents:
            return True
    return False


def _is_allowed(path):
    if not ALLOWED_ROOTS:
        return True

    resolved = _resolve(path)
    for root in ALLOWED_ROOTS:
        allowed = _resolve(root)
        if resolved == allowed or allowed in resolved.parents:
            return True
    return False


def _check_path(path):
    try:
        resolved = _resolve(path)
    except Exception:
        return None, "I could not understand that file path."

    if _is_blacklisted(resolved):
        return None, f"I cannot access {resolved}. That path is blacklisted."

    if not _is_allowed(resolved):
        return None, f"I cannot access {resolved}. It is outside the allowed folders."

    return resolved, None


def _cap_output(text):
    if len(text) <= MAX_READ_CHARS:
        return text

    half = max(1, MAX_READ_CHARS // 2)
    start = text[:half].strip()
    end = text[-half:].strip()
    return (
        f"The file is longer than {MAX_READ_CHARS} characters, so here is a shortened summary.\n\n"
        f"Start of file:\n{start}\n\n"
        f"End of file:\n{end}"
    )


def _read_plain(path):
    with open(path, "r", encoding="utf-8", errors="replace") as file:
        return file.read()


def _read_pdf(path):
    import fitz

    document = fitz.open(path)
    pages = []
    for page in document:
        pages.append(page.get_text())
    document.close()
    return "\n".join(pages)


def _read_docx(path):
    from docx import Document

    document = Document(path)
    return "\n".join(paragraph.text for paragraph in document.paragraphs)


def _read_xlsx(path):
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    sheets = []

    for sheet in workbook.worksheets:
        rows = [f"Sheet: {sheet.title}"]
        for row in sheet.iter_rows(values_only=True):
            values = ["" if value is None else str(value) for value in row]
            rows.append(", ".join(values).rstrip(", "))
        sheets.append("\n".join(rows))

    workbook.close()
    return "\n\n".join(sheets)


def find_file(name):
    if not ALLOWED_ROOTS:
        return "I cannot search yet because ALLOWED_ROOTS is empty."

    if not isinstance(name, str) or not name.strip():
        return "Tell me the file name to search for."

    matches = []
    target = name.strip().lower()

    for root in ALLOWED_ROOTS:
        root_path, error = _check_path(root)
        if error:
            continue

        for current_root, dirs, files in os.walk(root_path):
            safe_dirs = []
            for dirname in dirs:
                directory = Path(current_root) / dirname
                if not _is_blacklisted(directory):
                    safe_dirs.append(dirname)
            dirs[:] = safe_dirs

            for filename in files:
                if target in filename.lower():
                    matches.append(str(Path(current_root) / filename))

    if not matches:
        return f"I could not find any files matching {name}."

    return "I found these files: " + "; ".join(matches)


def open_file(path):
    resolved, error = _check_path(path)
    if error:
        return error

    if not resolved.exists():
        return f"I could not find {resolved}."

    try:
        system = platform.system()
        if system == "Windows":
            os.startfile(resolved)
        elif system == "Darwin":
            subprocess.Popen(["open", str(resolved)])
        else:
            subprocess.Popen(["xdg-open", str(resolved)])
        return f"Opening {resolved.name}."
    except Exception:
        return f"I could not open {resolved.name}."


def read_file(path):
    resolved, error = _check_path(path)
    if error:
        return error

    if not resolved.exists():
        return f"I could not find {resolved}."

    if resolved.is_dir():
        return f"{resolved} is a folder, not a file."

    try:
        extension = resolved.suffix.lower()
        if extension in PLAIN_EXTENSIONS:
            content = _read_plain(resolved)
        elif extension == ".pdf":
            content = _read_pdf(resolved)
        elif extension == ".docx":
            content = _read_docx(resolved)
        elif extension == ".xlsx":
            content = _read_xlsx(resolved)
        else:
            return f"I do not know how to read {extension or 'that'} files yet."

        return _cap_output(content)
    except Exception:
        return f"I could not read {resolved.name}."


def write_file(path, content, mode="w"):
    resolved, error = _check_path(path)
    if error:
        return error

    if REQUIRE_CONFIRM_ON_WRITE:
        global _pending
        _pending = {"action": "write", "path": resolved, "content": content, "mode": mode}
        return f"Please confirm before I write to {resolved}. Say yes or confirm to proceed, or cancel."

    return _write_now(resolved, content, mode)


def delete_file(path):
    resolved, error = _check_path(path)
    if error:
        return error

    if not resolved.exists():
        return f"I could not find {resolved}."

    if REQUIRE_CONFIRM_ON_DELETE:
        global _pending
        _pending = {"action": "delete", "path": resolved}
        return f"Please confirm before I delete {resolved}. Say yes or confirm to proceed, or cancel."

    return _delete_now(resolved)


def list_dir(path):
    resolved, error = _check_path(path)
    if error:
        return error

    if not resolved.exists():
        return f"I could not find {resolved}."

    if not resolved.is_dir():
        return f"{resolved} is not a folder."

    try:
        entries = []
        for item in sorted(resolved.iterdir(), key=lambda entry: (entry.is_file(), entry.name.lower())):
            kind = "folder" if item.is_dir() else "file"
            entries.append(f"{item.name} ({kind})")

        if not entries:
            return f"{resolved} is empty."

        return f"Here is what is inside {resolved}: " + "; ".join(entries)
    except Exception:
        return f"I could not list {resolved}."


def move_file(src, dst):
    source, error = _check_path(src)
    if error:
        return error

    destination, error = _check_path(dst)
    if error:
        return error

    if not source.exists():
        return f"I could not find {source}."

    if REQUIRE_CONFIRM_ON_WRITE:
        global _pending
        _pending = {"action": "move", "source": source, "destination": destination}
        return f"Please confirm before I move {source} to {destination}. Say yes or confirm to proceed, or cancel."

    return _move_now(source, destination)
