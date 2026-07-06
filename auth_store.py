# auth_store.py = per-user credential storage for Google-connected accounts
# Stores encrypted Google refresh tokens in Supabase users table.

import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet

from supabase_client import get_client


def _get_fernet():
    key = os.getenv("FERNET_KEY")

    if not key:
        raise ValueError(
            "FERNET_KEY is not set. Generate one with:\n"
            "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )

    return Fernet(key.encode() if isinstance(key, str) else key)


def save_user(user_id, email, refresh_token):
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
    client = get_client()

    response = (
        client.table("users")
        .select("user_id, email")
        .execute()
    )

    return [
        {
            "user_id": row["user_id"],
            "email": row["email"],
        }
        for row in (response.data or [])
    ]