# privacy.py = Privacy & Safety Layer for PI Agent
# Goal: use personal data temporarily, but never store raw sensitive data.

import re
import hashlib
from datetime import datetime


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