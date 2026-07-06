# desktop.py = native desktop shell for PI Agent (macOS)
#
# Replaces app.py (Streamlit) as the frontend. Runs the existing FastAPI
# backend (api.py) in a background thread, then opens it inside a native
# pywebview window pointed at static/index.html.
#
# Why this exists instead of Streamlit: Streamlit runs in a browser tab and
# can't open a native OS folder-picker or get real filesystem permission
# scoping. This file adds that native folder picker via DesktopApi.pick_folder,
# which is exposed to the frontend JS as `window.pywebview.api.pick_folder()`.
#
# Nothing in api.py, Planner.py, chat.py, ingest.py, privacy.py, or
# workspace.py needs to change - this only replaces the frontend.
#
# Run with: python desktop.py

import threading
import time
from pathlib import Path

import requests
import uvicorn
import webview

from api import app as fastapi_app

API_HOST = "127.0.0.1"
API_PORT = 8000
API_URL = f"http://{API_HOST}:{API_PORT}"
STATIC_DIR = Path(__file__).parent / "static"


def run_api():
    # log_level="warning" keeps uvicorn's request-by-request access log out
    # of the terminal the user sees when double-clicking the packaged app.
    uvicorn.run(fastapi_app, host=API_HOST, port=API_PORT, log_level="warning")


def wait_for_api(timeout_seconds=15):
    """Blocks until /health responds, so the window doesn't open before the backend is ready."""
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            requests.get(f"{API_URL}/health", timeout=1)
            return True
        except requests.exceptions.ConnectionError:
            time.sleep(0.2)

    return False


class DesktopApi:
    """
    Exposed to the frontend as `window.pywebview.api`.

    Anything requiring real OS access - like a native folder picker - has to
    live here. Plain HTML/JS running inside the webview cannot open OS
    dialogs or read arbitrary paths on its own; this is the bridge.
    """

    def pick_folder(self):
        """
        Opens the native macOS folder picker. Returns the chosen folder path
        as a string, or None if the user cancelled.

        This is the "approved workspace" moment: the user explicitly chooses
        a folder via the OS's own dialog, rather than typing a path into a
        text box that might not exist or might be mistyped.
        """
        window = webview.windows[0]
        result = window.create_file_dialog(webview.FOLDER_DIALOG)

        if not result:
            return None

        return result[0]

    def api_base_url(self):
        """Lets the frontend JS know where the local FastAPI server is listening."""
        return API_URL


def main():
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()

    if not wait_for_api():
        print(
            "Warning: FastAPI backend did not respond on "
            f"{API_URL}/health within the timeout. The window will still "
            "open, but requests may fail until the backend catches up."
        )

    desktop_api = DesktopApi()

    webview.create_window(
        title="PI Agent",
        url=str(STATIC_DIR / "index.html"),
        js_api=desktop_api,
        width=1180,
        height=760,
        min_size=(860, 560),
    )

    webview.start()


if __name__ == "__main__":
    main()