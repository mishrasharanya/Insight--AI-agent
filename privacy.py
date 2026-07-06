# privacy.py = Privacy & Safety Layer for the Insight Agent
# Goal: use personal data temporarily, never store raw sensitive data beyond
# the stored data itself, and give the user full visibility into and
# control over what's actually stored - nothing hidden, nothing they can't
# inspect or delete themselves.

import re
import hashlib
from datetime import datetime

from supabase_client import get_client

DEFAULT_COLLECTION_NAME = "personal_memory"


SENSITIVE_PATTERNS = {
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "phone": r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
    "address_like": r"\b\d{1,5}\s+[A-Za-z0-9.\s]+(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr)\b",

    # Government / identity-like IDs
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "aadhaar": r"\b\d{4}\s\d{4}\s\d{4}\b",
    "passport_like": r"\b[A-Z][0-9]{7,8}\b",

    # Finance
    "credit_card": r"\b(?:\d[ -]*?){13,19}\b",
    "bank_account_like": r"\b\d{9,18}\b",
    "routing_number_like": r"\b\d{9}\b",

    # API keys / tokens
    "openai_key": r"\bsk-[A-Za-z0-9_\-]{20,}\b",
    "groq_key": r"\bgsk_[A-Za-z0-9_\-]{20,}\b",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b",
    "google_api_key": r"\bAIza[0-9A-Za-z_\-]{20,}\b",
    "generic_secret": r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*[A-Za-z0-9_\-]{8,}\b",
}


def redact_sensitive_text(text):
    """
    Redacts common personal identifiers before text is sent to the LLM
    or stored in logs.

    LIMITATION: this is regex-based, so it only catches structured/patterned
    identifiers (emails, phone numbers, etc). It does NOT catch names,
    employers, health details, or other personal info written in free-form
    prose. Don't treat this as "nothing sensitive reaches the LLM" - the
    stored content itself is sent unredacted, by design, since that's what
    the agent needs to function.
    """
    if not text:
        return ""

    redacted = str(text)

    for label, pattern in SENSITIVE_PATTERNS.items():
        redacted = re.sub(
            pattern,
            f"[REDACTED_{label.upper()}]",
            redacted,
            flags=re.IGNORECASE,
        )

    return redacted


def safe_question_hash(question):
    """
    Stores a hash of the question instead of the raw question.
    This lets you track repeated/eval questions without storing private text.
    """
    return hashlib.sha256(str(question).encode("utf-8")).hexdigest()[:16]


def build_safe_audit_log(
    question,
    route,
    tool_used=None,
    confidence_tier=None,
    data_type_accessed=None,
):
    """
    Safe log record. Does NOT store raw question, raw email, calendar text,
    file contents, contacts, or private descriptions.
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "question_hash": safe_question_hash(question),
        "route": route,
        "tool_used": tool_used,
        "confidence_tier": confidence_tier,
        "data_type_accessed": data_type_accessed,
        "raw_personal_data_stored": False,
    }


def minimize_calendar_event(event):
    """
    Convert a raw calendar event into a minimal safe summary.
    Use this before sending calendar data to the LLM.
    """
    return {
        "date": event.get("date"),
        "start_time": event.get("start_time"),
        "end_time": event.get("end_time"),
        "title": redact_sensitive_text(event.get("title", "")),
        "event_type": event.get("event_type", "calendar_event"),
    }


def minimize_email(email):
    """
    Convert a raw email into a minimal safe summary.
    Avoid storing/sending full email bodies.
    """
    return {
        "date": email.get("date"),
        "sender_domain": extract_domain(email.get("sender", "")),
        "subject": redact_sensitive_text(email.get("subject", "")),
        "snippet": redact_sensitive_text(email.get("snippet", ""))[:250],
    }


def extract_domain(email_address):
    """
    Keeps only the email domain, not the full personal email address.
    Example: person@gmail.com -> gmail.com
    """
    if not email_address or "@" not in email_address:
        return "unknown"

    return email_address.split("@")[-1].lower()


def requires_user_confirmation(action_type):
    """
    Read actions are allowed.
    Write/delete/send actions require explicit user confirmation.
    """
    write_actions = {
        "send_email",
        "delete_email",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
        "edit_drive_file",
        "delete_drive_file",
    }

    return action_type in write_actions


# ---------- Transparency & control: see and delete what's actually stored ----------

def get_data_inventory(collection_name=None):
    """
    Returns exactly what personal data is currently stored, so nothing about
    what's in Supabase is hidden or has to be taken on faith. Reads the
    `chunks` table directly, filtered by collection_name, rather than
    summarizing from memory.

    collection_name: pass the logged-in user's own collection (see
    google_sync.collection_name_for) in multi-user hosted mode, so this only
    reports THAT user's data - never another tester's. Defaults to the
    shared "personal_memory" collection for desktop/single-user use.

    NOTE: the "chroma_db_exists" key name is kept as-is even though Chroma
    is gone - index.html's frontend JS checks this exact key
    (inventory.chroma_db_exists), and renaming it here without also editing
    the frontend would silently break the inventory display. Read it as
    "stored data is reachable", not literally about Chroma.
    """
    target_collection = collection_name or DEFAULT_COLLECTION_NAME
    client = get_client()

    try:
        response = (
            client.table("chunks")
            .select("filename, created_at")
            .eq("collection_name", target_collection)
            .execute()
        )
    except Exception as error:
        return {
            "chroma_db_exists": True,
            "error": f"Could not read stored data: {error}",
            "sources": [],
            "total_chunks": 0,
        }

    rows = response.data or []

    if not rows:
        return {
            "chroma_db_exists": False,
            "sources": [],
            "total_chunks": 0,
        }

    sources = {}
    for row in rows:
        filename = row.get("filename", "unknown")
        sources.setdefault(filename, {"chunk_count": 0, "last_ingested": None})
        sources[filename]["chunk_count"] += 1

        created = row.get("created_at")
        if created and (
            sources[filename]["last_ingested"] is None
            or created > sources[filename]["last_ingested"]
        ):
            sources[filename]["last_ingested"] = created

    return {
        "chroma_db_exists": True,
        "sources": [{"filename": name, **info} for name, info in sources.items()],
        "total_chunks": len(rows),
    }


def print_data_inventory(collection_name=None):
    """Human-readable version of get_data_inventory(), for the user to run anytime."""
    inventory = get_data_inventory(collection_name=collection_name)

    if not inventory["chroma_db_exists"]:
        print("No stored data found. Nothing is stored.")
        return

    if "error" in inventory:
        print(f"Could not read stored data: {inventory['error']}")
        return

    if inventory["total_chunks"] == 0:
        print("Nothing is stored yet.")
        return

    print(f"Total stored chunks: {inventory['total_chunks']}\n")
    print("Sources:")
    for source in inventory["sources"]:
        print(
            f"  - {source['filename']}: {source['chunk_count']} chunk(s), "
            f"last ingested {source['last_ingested']}"
        )


def purge_all_local_data(confirm=False, collection_name=None):
    """
    Deletes stored data for one collection. Irreversible. Requires
    confirm=True so this can't be triggered accidentally by an LLM call or
    a stray function call.

    collection_name: THE CRITICAL PARAMETER IN MULTI-USER MODE. Pass the
    logged-in user's own collection (see google_sync.collection_name_for)
    to delete only that user's rows.

    IMPORTANT BEHAVIOR CHANGE from the old Chroma-backed version: when
    collection_name is omitted, this used to wipe the ENTIRE local
    chroma_db/ folder - safe back when that folder only ever held one
    person's data on their own machine. On a shared Supabase backend there
    is no "just my folder" equivalent, so omitting collection_name now
    scopes the delete to the DEFAULT_COLLECTION_NAME ("personal_memory")
    specifically - NOT every row in the table. Do not change this to an
    unscoped delete, or one purge call could remove every user's data.
    """
    if not confirm:
        return {
            "purged": False,
            "message": "Purge not run - call purge_all_local_data(confirm=True) to actually delete data.",
        }

    target_collection = collection_name or DEFAULT_COLLECTION_NAME
    client = get_client()

    try:
        client.table("chunks").delete().eq("collection_name", target_collection).execute()
        client.table("structured_rows").delete().eq("collection_name", target_collection).execute()
    except Exception as error:
        return {"purged": False, "message": f"Could not delete your data: {error}"}

    return {
        "purged": True,
        "message": "Deleted your stored data. Re-sync Calendar/Drive, or re-run ingest.py, to rebuild it.",
    }


if __name__ == "__main__":
    # Run this file directly anytime to see or wipe exactly what's stored -
    # no need to trust a description of it, check it yourself.
    print("===== Insight Agent Privacy Check =====\n")
    print_data_inventory()

    print("\nTo delete ALL stored data for the default collection, run this in Python:")
    print("  from privacy import purge_all_local_data")
    print("  purge_all_local_data(confirm=True)")