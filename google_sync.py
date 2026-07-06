# google_sync.py = pulls Calendar + Drive content into each user's OWN
# scoped rows in Supabase - never shared ones.

import hashlib
import io
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from pypdf import PdfReader

from embedding_client import embed_text
from ingest import chunk_text
from supabase_client import get_client


def collection_name_for(user_id):
    safe_id = hashlib.md5(user_id.encode("utf-8")).hexdigest()[:16]
    return f"personal_memory_{safe_id}"


def _already_synced(client, collection_name, file_hash):
    response = (
        client.table("chunks")
        .select("id")
        .eq("collection_name", collection_name)
        .eq("file_hash", file_hash)
        .limit(1)
        .execute()
    )

    return bool(response.data)


def _upsert_chunks(user_id, source_label, text, extra_metadata=None):
    if not text or not text.strip():
        return 0

    collection_name = collection_name_for(user_id)
    chunks = chunk_text(text)

    if not chunks:
        return 0

    file_hash = hashlib.md5(f"{user_id}_{source_label}".encode("utf-8")).hexdigest()

    client = get_client()

    if _already_synced(client, collection_name, file_hash):
        print(f"[sync] skipped unchanged source: {source_label}")
        return 0

    extra_metadata = extra_metadata or {}
    file_type = extra_metadata.get("file_type")
    effective_date = extra_metadata.get("content_date") or datetime.now().isoformat()

    records = []

    for index, chunk in enumerate(chunks):
        embedding = embed_text(chunk)

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
    skipped = 0

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

        chunks_added = _upsert_chunks(
            user_id=user_id,
            source_label=f"calendar:{event.get('id')}",
            text=text,
            extra_metadata={
                "file_type": "calendar_event",
                "content_date": start,
            },
        )

        if chunks_added == 0:
            skipped += 1
        else:
            total_chunks += chunks_added

    return {
        "events_synced": len(events),
        "events_skipped": skipped,
        "chunks_added": total_chunks,
    }


def _extract_drive_file_text(service, file_id, mime_type):
    if mime_type == "application/vnd.google-apps.document":
        content = service.files().export(
            fileId=file_id,
            mimeType="text/plain",
        ).execute()

        return content.decode("utf-8") if isinstance(content, bytes) else str(content)

    if mime_type == "application/pdf":
        content = service.files().get_media(fileId=file_id).execute()
        reader = PdfReader(io.BytesIO(content))

        return "\n".join((page.extract_text() or "") for page in reader.pages)

    content = service.files().get_media(fileId=file_id).execute()

    return content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)

def sync_drive_files(user_id, credentials, picked_files):
    import traceback

    service = build("drive", "v3", credentials=credentials)
    total_chunks = 0
    files_synced = 0
    files_skipped = 0

    for file in picked_files:
        file_id = file.get("id")
        name = file.get("name", "untitled")
        mime_type = file.get("mimeType", "")
        if not file_id:
            continue

        try:
            text = _extract_drive_file_text(service, file_id, mime_type)
            chunks_added = _upsert_chunks(
                user_id=user_id,
                source_label=f"drive:{name}",
                text=text,
                extra_metadata={"file_type": mime_type},
            )
        except Exception as error:
            print(f"[drive sync] failed on '{name}' ({mime_type}): {error}")
            traceback.print_exc()
            files_skipped += 1
            continue

        if chunks_added:
            files_synced += 1
            total_chunks += chunks_added
        else:
            files_skipped += 1

    return {
        "files_synced": files_synced,
        "files_skipped": files_skipped,
        "chunks_added": total_chunks,
    }
