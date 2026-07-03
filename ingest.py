# ingest.py = build memory database

import os
import re
import hashlib
from datetime import datetime
from pathlib import Path

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "personal_memory"
DATA_FOLDER = "data"
MAX_CHUNK_CHARS = 800  # rough cap so no single chunk is huge

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_file_hash(file_path):
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def read_csv_file(file_path):
    df = pd.read_csv(file_path)

    rows_as_text = []

    for _, row in df.iterrows():
        row_text = []

        for column in df.columns:
            row_text.append(f"{column}: {row[column]}")

        rows_as_text.append(" | ".join(row_text))

    return "\n\n".join(rows_as_text)


def load_document(file_path):
    extension = Path(file_path).suffix.lower()

    if extension in [".txt", ".md"]:
        return read_text_file(file_path)

    if extension == ".csv":
        return read_csv_file(file_path)

    print(f"Skipping unsupported file type: {file_path}")
    return None


def split_long_paragraph(paragraph, max_chars):
    """Break an oversized paragraph into smaller pieces on sentence boundaries."""
    sentences = paragraph.replace("\n", " ").split(". ")
    pieces = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        candidate = (current + ". " + sentence).strip() if current else sentence

        if len(candidate) > max_chars and current:
            pieces.append(current.strip())
            current = sentence
        else:
            current = candidate

    if current:
        pieces.append(current.strip())

    return pieces


def chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    paragraphs = text.split("\n\n")
    chunks = []

    for paragraph in paragraphs:
        clean_paragraph = paragraph.strip()

        if not clean_paragraph:
            continue

        if len(clean_paragraph) <= max_chars:
            chunks.append(clean_paragraph)
        else:
            chunks.extend(split_long_paragraph(clean_paragraph, max_chars))

    return chunks


def get_file_dates(file_path):
    """Returns (date_modified, date_ingested) as ISO strings."""
    modified_timestamp = os.path.getmtime(file_path)
    date_modified = datetime.fromtimestamp(modified_timestamp).isoformat()
    date_ingested = datetime.now().isoformat()

    return date_modified, date_ingested


MONTH_NAMES = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12
}


def extract_content_date(text):
    """
    Tries to find a real date mentioned inside the chunk's own text.
    Checks for ISO dates (YYYY-MM-DD) first, then "Month YYYY" headers.
    Returns an ISO date string, or None if no date is found.
    """
    iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
    if iso_match:
        try:
            found_date = datetime(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3)))
            return found_date.isoformat()
        except ValueError:
            pass  # invalid date like month 13, fall through

    month_match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        text,
        re.IGNORECASE
    )
    if month_match:
        month_num = MONTH_NAMES[month_match.group(1).lower()]
        year_num = int(month_match.group(2))
        return datetime(year_num, month_num, 1).isoformat()

    return None


def cleanup_deleted_files(collection, current_files):
    """Remove chunks for any source file no longer present in the data folder."""
    all_records = collection.get(include=["metadatas"])

    if not all_records["metadatas"]:
        return

    known_sources = set()
    for metadata in all_records["metadatas"]:
        known_sources.add(metadata["source"])

    for source in known_sources:
        if source not in current_files:
            collection.delete(where={"source": source})
            print(f"Removed chunks for deleted file: {source}")


def main():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    current_files = []

    for filename in os.listdir(DATA_FOLDER):
        file_path = os.path.join(DATA_FOLDER, filename)

        if not os.path.isfile(file_path):
            continue

        current_files.append(file_path)

        text = load_document(file_path)

        if text is None:
            continue

        file_hash = get_file_hash(file_path)

        existing = collection.get(where={"source": file_path})

        if existing["metadatas"]:
            old_hash = existing["metadatas"][0].get("file_hash")

            if old_hash == file_hash:
                print(f"Skipping unchanged file: {filename}")
                continue

            collection.delete(where={"source": file_path})
            print(f"Updated file detected. Re-indexing: {filename}")

        chunks = chunk_text(text)
        date_modified, date_ingested = get_file_dates(file_path)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{file_path}_chunk_{i}"
            embedding = embedding_model.encode(chunk).tolist()

            # Prefer a real date found inside the chunk's own text (e.g. CSV row date,
            # or a "January 2025" journal header) over the file's modification time.
            content_date = extract_content_date(chunk)
            effective_date = content_date if content_date else date_modified

            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": file_path,
                    "filename": filename,
                    "chunk_index": i,
                    "file_hash": file_hash,
                    "file_type": Path(file_path).suffix.lower(),
                    "date_modified": date_modified,
                    "date_ingested": date_ingested,
                    "content_date": content_date if content_date else "",
                    "effective_date": effective_date
                }]
            )

        print(f"Stored {len(chunks)} chunks from {filename}")

    cleanup_deleted_files(collection, current_files)

    print("Ingestion complete.")


if __name__ == "__main__":
    main()