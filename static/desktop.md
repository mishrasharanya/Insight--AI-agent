# Running PI Agent as a native macOS app (pywebview)

This replaces `app.py` (Streamlit) as the frontend. `api.py` (FastAPI) and
everything it imports (`Planner.py`, `chat.py`, `ingest.py`, `privacy.py`,
`workspace.py`, etc.) stay exactly as they are.

## 1. Install the one new dependency

```
pip install pywebview
```

(You already have `fastapi`, `uvicorn`, and `requests` from the existing project.)

## 2. Drop these two new files into your project root

- `desktop.py` - next to `api.py`
- `static/index.html` - in a new `static/` folder next to `desktop.py`

Your project folder should look like:

```
your-project/
  api.py
  Planner.py
  chat.py
  ...
  desktop.py        <- new
  static/
    index.html       <- new
```

## 3. Run it

```
python desktop.py
```

This starts FastAPI on `127.0.0.1:8000` in a background thread and opens a
native window pointed at `static/index.html`. No terminal instructions for
uvicorn/Streamlit needed anymore - this one command does both.

## 4. What changed vs. app.py

- **Add workspace** now opens a real macOS folder picker (via
  `desktop.py`'s `DesktopApi.pick_folder`) instead of a text box you type a
  path into. The chosen folder is then sent to the same `/workspaces`
  endpoint `workspace.py` already exposes - no backend changes needed.
- Chat, re-index, and privacy (inventory + purge) all call the same FastAPI
  endpoints as before, just from plain JS instead of Streamlit widgets.
- Confidence tier is now a small 3-segment meter next to each answer instead
  of a caption string, so it's readable at a glance.

## 5. Packaging as a double-click `.app` (optional next step)

Once you're happy with the behavior, `pyinstaller` can bundle this into a
real `PI Agent.app`:

```
pip install pyinstaller
pyinstaller --windowed --name "PI Agent" --add-data "static:static" desktop.py
```

The `.app` will appear in `dist/`. This isn't required to use the app locally
today - `python desktop.py` is enough - but it's the step that gets you to
"double-click icon, no terminal at all," like Cursor.