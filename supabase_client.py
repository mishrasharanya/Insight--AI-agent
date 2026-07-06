# supabase_client.py = shared Supabase connection, used everywhere Chroma
# used to be instantiated directly (ingest.py, retrieve.py, reflection.py, api.py)

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# NOTE: this must be the SERVICE ROLE key, not the anon/public key - the
# backend needs to bypass row-level security to filter by collection_name
# itself. Never expose this key to the frontend or commit it to git.
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in your .env file. "
        "Find these in your Supabase project under Settings > API."
    )

_client: Client = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client