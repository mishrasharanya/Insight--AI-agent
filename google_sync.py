# google_sync.py = pulls Calendar + Drive content into each user's OWN
# scoped rows in Supabase - never shared ones.

import csv
import hashlib
import io
from datetime import datetime, timedelta

from googleapiclient.discovery import build
from pypdf import PdfReader

from embedding_client import embed_text
from ingest import chunk_text
from supabase_client import get_client


CSV_MIME = "text/csv"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
GSHEET_MIME = "application/vnd.google-apps.spreadsheet"

TABULAR_MIME_TYPES = {CSV_MIME, XLSX_MIME, GSHEET_MIME}


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

    if mime_type == GSHEET_MIME:
        content = service.files().export(
            fileId=file_id,
            mimeType="text/csv",
        ).execute()

        return content.decode("utf-8") if isinstance(content, bytes) else str(content)

    if mime_type == "application/pdf":
        content = service.files().get_media(fileId=file_id).execute()
        reader = PdfReader(io.BytesIO(content))

        return "\n".join((page.extract_text() or "") for page in reader.pages)

    content = service.files().get_media(fileId=file_id).execute()

    return content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)


def _extract_tabular_rows(service, file_id, mime_type):
    """
    Returns a list of (sheet_name, rows) tuples for CSV / XLSX / Google Sheets
    files, where rows is a list of {column_name: value} dicts.
    Returns [] for non-tabular mime types.
    """
    if mime_type == GSHEET_MIME:
        # Google Sheets export only pulls the first sheet as CSV via this API,
        # so sheet_name is left as None here.
        content = service.files().export(
            fileId=file_id,
            mimeType="text/csv",
        ).execute()

        text = content.decode("utf-8") if isinstance(content, bytes) else str(content)
        reader = csv.DictReader(io.StringIO(text))

        return [(None, list(reader))]

    if mime_type == CSV_MIME:
        content = service.files().get_media(fileId=file_id).execute()
        text = content.decode("utf-8", errors="ignore") if isinstance(content, bytes) else str(content)
        reader = csv.DictReader(io.StringIO(text))

        return [(None, list(reader))]

    if mime_type == XLSX_MIME:
        import openpyxl

        content = service.files().get_media(fileId=file_id).execute()
        workbook = openpyxl.load_workbook(io.BytesIO(content), data_only=True)

        results = []

        for sheet in workbook.worksheets:
            rows_iter = sheet.iter_rows(values_only=True)

            try:
                header_row = next(rows_iter)
            except StopIteration:
                continue

            header = [
                str(cell) if cell is not None else f"column_{i}"
                for i, cell in enumerate(header_row)
            ]

            sheet_rows = []

            for row_values in rows_iter:
                if row_values is None or all(v is None for v in row_values):
                    continue

                row_dict = {
                    header[i]: row_values[i]
                    for i in range(len(header))
                    if i < len(row_values)
                }
                sheet_rows.append(row_dict)

            results.append((sheet.title, sheet_rows))

        return results

    return []


def sync_drive_files(user_id, credentials, picked_files):
    import traceback

    service = build("drive", "v3", credentials=credentials)
    collection_name = collection_name_for(user_id)
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

            if mime_type in TABULAR_MIME_TYPES:
                try:
                    sheets = _extract_tabular_rows(service, file_id, mime_type)

                    for sheet_name, rows in sheets:
                        _insert_tabular_rows(
                            collection_name=collection_name,
                            filename=name,
                            rows=rows,
                            sheet_name=sheet_name,
                        )
                except Exception as tabular_error:
                    print(f"[drive sync] tabular parse failed on '{name}': {tabular_error}")
                    traceback.print_exc()

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


def _insert_tabular_rows(collection_name, filename, rows, sheet_name=None):
    if not rows:
        return

    payload = [{
        "collection_name": collection_name,
        "filename": filename,
        "sheet_name": sheet_name,
        "row_index": i,
        "data": row,
    } for i, row in enumerate(rows)]

    get_client().table("tabular_rows").insert(payload).execute()