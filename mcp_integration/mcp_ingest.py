# mcp_integration/mcp_ingest.py

import hashlib
import sys
from pathlib import Path
from datetime import datetime, timedelta

import chromadb
from sentence_transformers import SentenceTransformer

# Allow imports from project root
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from privacy import minimize_calendar_event, minimize_email
from mcp_integration.mcp_client import call_tool


CHROMA_PATH = str(ROOT_DIR / "chroma_db")
COLLECTION_NAME = "personal_memory"

CALENDAR_SERVER_KEY = "google_calendar"
CALENDAR_TOOL_NAME = "list-events"

EMAIL_SERVER_KEY = "google_workspace"
EMAIL_TOOL_NAME = "search_emails"

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def event_to_text(minimized_event):
    return (
        f"Calendar event: {minimized_event.get('title', 'Untitled')} "
        f"on {minimized_event.get('date', '')} "
        f"from {minimized_event.get('start_time', '')} "
        f"to {minimized_event.get('end_time', '')} "
        f"({minimized_event.get('event_type', 'event')})"
    )


def email_to_text(minimized_email):
    return (
        f"Email from {minimized_email.get('sender_domain', 'unknown')} "
        f"on {minimized_email.get('date', '')}: "
        f"{minimized_email.get('subject', '')}. "
        f"{minimized_email.get('snippet', '')}"
    )


def store_chunk(collection, text, source_type, source_id, date_value=None):
    chunk_id = hashlib.md5(f"{source_type}_{source_id}".encode()).hexdigest()
    embedding = embedding_model.encode(text).tolist()

    now = datetime.now().isoformat()

    collection.upsert(
        ids=[chunk_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[
            {
                "source": f"mcp:{source_type}",
                "file_hash": chunk_id,
                "chunk_index": 0,
                "source_type": source_type,
                "date_ingested": now,
                "content_date": date_value or "",
            }
        ],
    )


def _extract_items(raw_result, likely_keys):
    if not raw_result:
        return []

    if isinstance(raw_result, list):
        first = raw_result[0] if raw_result else None

        if isinstance(first, list):
            return first

        if isinstance(first, dict):
            for key in likely_keys:
                if key in first and isinstance(first[key], list):
                    return first[key]

            return raw_result

    if isinstance(raw_result, dict):
        for key in likely_keys:
            if key in raw_result and isinstance(raw_result[key], list):
                return raw_result[key]

        return [raw_result]

    return []


def ingest_calendar_events(days_ahead=30):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    time_min = datetime.now().isoformat()
    time_max = (datetime.now() + timedelta(days=days_ahead)).isoformat()

    print(f"[MCP Ingest] Fetching calendar events via {CALENDAR_SERVER_KEY}...")

    raw_result = call_tool(
        CALENDAR_SERVER_KEY,
        CALENDAR_TOOL_NAME,
        {
            "timeMin": time_min,
            "timeMax": time_max,
        },
    )

    events = _extract_items(raw_result, ["events", "items"])

    if not events:
        print("[MCP Ingest] No calendar events returned.")
        return

    for event in events:
        minimized = minimize_calendar_event(event)
        text = event_to_text(minimized)
        event_id = event.get("id") or hashlib.md5(text.encode()).hexdigest()

        store_chunk(
            collection=collection,
            text=text,
            source_type="calendar_event",
            source_id=event_id,
            date_value=minimized.get("date"),
        )

    print(f"[MCP Ingest] Stored {len(events)} calendar event(s).")


def ingest_emails(query="newer_than:7d", max_results=20):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    print(f"[MCP Ingest] Fetching emails via {EMAIL_SERVER_KEY}...")

    raw_result = call_tool(
        EMAIL_SERVER_KEY,
        EMAIL_TOOL_NAME,
        {
            "query": query,
            "maxResults": max_results,
        },
    )

    emails = _extract_items(raw_result, ["emails", "messages", "items"])

    if not emails:
        print("[MCP Ingest] No emails returned.")
        return

    for email in emails:
        minimized = minimize_email(email)
        text = email_to_text(minimized)
        email_id = email.get("id") or hashlib.md5(text.encode()).hexdigest()

        store_chunk(
            collection=collection,
            text=text,
            source_type="email",
            source_id=email_id,
            date_value=minimized.get("date"),
        )

    print(f"[MCP Ingest] Stored {len(emails)} email(s).")


def main():
    print("===== MCP Data Ingestion =====\n")

    try:
        ingest_calendar_events()
    except Exception as e:
        print(f"[MCP Ingest] Calendar ingestion failed: {e}")

    try:
        ingest_emails()
    except Exception as e:
        print(f"[MCP Ingest] Email ingestion failed: {e}")


if __name__ == "__main__":
    main()