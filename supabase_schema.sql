-- Run this in the Supabase SQL editor (Database > SQL Editor) before touching any Python.

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Chunks table - replaces Chroma entirely.
-- `collection_name` plays the exact same role Chroma collection names did:
-- "personal_memory" for the shared/desktop case, or a per-user string
-- (from google_sync.collection_name_for) for logged-in users.
create table if not exists chunks (
    id uuid primary key default gen_random_uuid(),
    collection_name text not null,
    filename text not null,
    source text,
    file_type text,
    chunk_index int,
    file_hash text,
    effective_date timestamptz,
    text text not null,
    embedding vector(384),  -- all-MiniLM-L6-v2 output dimension
    created_at timestamptz default now(),

    -- mirrors the chunk_id hash dedup logic already in ingest.py, so
    -- re-running ingestion on an unchanged file doesn't create duplicates
    unique (collection_name, file_hash, chunk_index)
);

-- Index for fast approximate nearest-neighbor search.
-- NOTE: ivfflat indexes need data in the table before they're useful -
-- if this is a brand new table, you can create the index now, but run
-- `analyze chunks;` again after your first real ingestion batch.
create index if not exists chunks_embedding_idx
    on chunks using ivfflat (embedding vector_l2_ops)
    with (lists = 100);

create index if not exists chunks_collection_idx
    on chunks (collection_name);

-- 3. Structured rows table - for chart/tabular data extracted from
-- .csv and .xlsx files. Kept SEPARATE from `chunks` on purpose: chart
-- queries need exact typed values, not chunked/embedded text.
create table if not exists structured_rows (
    id uuid primary key default gen_random_uuid(),
    collection_name text not null,
    filename text not null,
    sheet_name text,
    row_index int not null,
    row_data jsonb not null,
    effective_date timestamptz,
    created_at timestamptz default now()
);

create index if not exists structured_rows_lookup_idx
    on structured_rows (collection_name, filename);

-- 4. Users table - replaces auth_store.py's local file storage.
-- user_id is the Google "sub" claim, matching what api.py already uses.
create table if not exists users (
    user_id text primary key,
    email text,
    refresh_token text not null,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- 5. Vector similarity search function.
-- Called via supabase.rpc("match_chunks", {...}) from Python - pgvector
-- similarity search isn't expressible through the plain REST/table API,
-- so it needs to be a SQL function exposed as an RPC.
create or replace function match_chunks(
    query_embedding vector(384),
    match_collection text,
    match_count int
)
returns table (
    id uuid,
    filename text,
    source text,
    file_type text,
    effective_date timestamptz,
    text text,
    distance float
)
language sql stable
as $$
    select
        id,
        filename,
        source,
        file_type,
        effective_date,
        text,
        embedding <-> query_embedding as distance
    from chunks
    where collection_name = match_collection
    order by embedding <-> query_embedding
    limit match_count;
$$;