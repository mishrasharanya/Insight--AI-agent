# google_sync.py = pulls Calendar + Drive content into each user's OWN
# scoped rows in Supabase - never shared ones.
#
# Every function here takes a user_id and writes only rows tagged with that
# user's collection_name (personal_memory_<hash of their Google sub>). This
# is the isolation boundary: nothing here ever reads or writes another
# user's data - same guarantee Chroma's separate collections gave before,
# just enforced via a WHERE/filter column instead of separate physical
# collections. Every query below MUST keep this filter.

import hashlib
import io
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from ingest import chunk_text
from supabase_client import get_client

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def collection_name_for(user_id):
    """
    Same role as before: a short, stable identifier derived from the
    Google sub, used as the collection_name filter value on every
    chunks/structured_rows query for this user.
    """
    safe_id = hashlib.md5(user_id.encode("utf-8")).hexdigest()[:16]
    return f"personal_memory_{safe_id}"


def _upsert_chunks(user_id, source_label, text, extra_metadata=None):
    if not text or not text.strip():
        return 0

    collection_name = collection_name_for(user_id)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    # Stable per-source hash (NOT a content hash) so re-syncing the same
    # calendar event or drive file overwrites its previous chunks instead
    # of accumulating duplicates each sync - mirrors the old Chroma id
    # scheme (md5(f"{user_id}_{source_label}_{index}")), just moved into
    # the file_hash column that the unique constraint keys off.
    file_hash = hashlib.md5(f"{user_id}_{source_label}".encode("utf-8")).hexdigest()

    extra_metadata = extra_metadata or {}
    file_type = extra_metadata.get("file_type")
    effective_date = extra_metadata.get("content_date") or datetime.now().isoformat()

    records = []

    for index, chunk in enumerate(chunks):
        embedding = embedding_model.encode(chunk).tolist()

        records.append({
            "collection_name": collection_name,
            "filename": source_label,
            "source": source_label,
            "file_type": file_type,
            "chunk_index": index,
            "file_hash": file_hash,
            "effective_date": effective_date,
            "text": chunk,
            "embedding": embedding,
        })

    client = get_client()
    client.table("chunks").upsert(
        records,
        on_conflict="collection_name,file_hash,chunk_index",
    ).execute()

    return len(records)


def sync_calendar(user_id, credentials, days_back=30, days_forward=90):
    service = build("calendar", "v3", credentials=credentials)

    time_min = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"
    time_max = (datetime.utcnow() + timedelta(days=days_forward)).isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            maxResults=250,
        )
        .execute()
    )

    events = events_result.get("items", [])
    total_chunks = 0

    for event in events:
        title = event.get("summary", "(no title)")
        start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
        end = event.get("end", {}).get("dateTime", event.get("end", {}).get("date", ""))
        description = event.get("description", "")
        location = event.get("location", "")

        text = (
            f"Event: {title}\n"
            f"Start: {start}\n"
            f"End: {end}\n"
            f"Location: {location}\n"
            f"Description: {description}"
        )

        total_chunks += _upsert_chunks(
            user_id,
            source_label=f"calendar:{event.get('id')}",
            text=text,
            extra_metadata={"file_type": "calendar_event", "content_date": start},
        )

    return {"events_synced": len(events), "chunks_added": total_chunks}


def _extract_drive_file_text(service, file_id, mime_type):
    if mime_type == "application/vnd.google-apps.document":
        # Google Docs aren't plain text internally - export as text.
        content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        return content.decode("utf-8") if isinstance(content, bytes) else str(content)

    if mime_type == "application/pdf":
        content = service.files().get_media(fileId=file_id).execute()
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    # text/plain and similar
    content = service.files().get_media(fileId=file_id).execute()
    return content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)


def sync_drive_files(user_id, credentials, picked_files):
    """
    picked_files: list of {"id": ..., "name": ..., "mimeType": ...} dicts,
    exactly as returned by the Google Picker selection on the frontend.

    With the drive.file scope, the app can only read files the user has
    explicitly selected via Picker (or created itself) - there's no
    "list everything matching a query" call available anymore, by design.
    This is the tradeoff for avoiding Drive's restricted-scope security
    assessment: narrower access, but no extra audit needed to go public.
    """
    service = build("drive", "v3", credentials=credentials)

    total_chunks = 0
    files_synced = 0

    for file in picked_files:
        file_id = file.get("id")
        name = file.get("name", "untitled")
        mime_type = file.get("mimeType", "")

        if not file_id:
            continue

        try:
            text = _extract_drive_file_text(service, file_id, mime_type)
        except Exception as error:
            print(f"[drive sync] skipped '{name}': {error}")
            continue

        chunks_added = _upsert_chunks(
            user_id,
            source_label=f"drive:{name}",
            text=text,
            extra_metadata={"file_type": mime_type},
        )

        if chunks_added:
            files_synced += 1
            total_chunks += chunks_added

    return {"files_synced": files_synced, "chunks_added": total_chunks}