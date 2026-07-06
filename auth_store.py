# auth_store.py = per-user credential storage for Google-connected accounts
#
# Stores one record per Google account: their email (for display) and their
# OAuth refresh token (encrypted at rest with Fernet - a refresh token is a
# long-lived credential to someone's real Calendar/Drive, so it must never
# sit in plaintext).
#
# Storage is now the Supabase `users` table instead of a local JSON file -
# this is what actually persists across Render restarts/deploys, since local
# disk doesn't. The encrypt/decrypt behavior below is unchanged; only where
# the encrypted blob is stored changed.

import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from supabase_client import get_client


def _get_fernet():
    key = os.getenv("FERNET_KEY")

    if not key:
        raise ValueError(
            "FERNET_KEY is not set. Generate one with:\n"
            "  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
            "and set it as an environment variable (keep it secret, back it up - "
            "losing it means every stored refresh token becomes unreadable)."
        )

    return Fernet(key.encode() if isinstance(key, str) else key)


def save_user(user_id, email, refresh_token):
    """
    user_id: Google's stable subject id ("sub" from the userinfo endpoint) -
    NOT the email, since emails can change; the sub never does.
    """
    fernet = _get_fernet()
    encrypted_token = fernet.encrypt(refresh_token.encode()).decode()

    client = get_client()
    client.table("users").upsert(
        {
            "user_id": user_id,
            "email": email,
            "refresh_token": encrypted_token,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()


def get_user(user_id):
    client = get_client()
    response = (
        client.table("users")
        .select("email, refresh_token")
        .eq("user_id", user_id)
        .execute()
    )

    if not response.data:
        return None

    record = response.data[0]
    fernet = _get_fernet()

    return {
        "email": record["email"],
        "refresh_token": fernet.decrypt(record["refresh_token"].encode()).decode(),
    }


def delete_user(user_id):
    client = get_client()
    response = client.table("users").delete().eq("user_id", user_id).execute()
    return bool(response.data)


def list_users():
    """For an admin view - never exposes refresh tokens, only emails."""
    client = get_client()
    response = client.table("users").select("user_id, email").execute()
    return [{"user_id": r["user_id"], "email": r["email"]} for r in (response.data or [])]