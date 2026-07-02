import os
import hashlib
from pathlib import Path

import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "personal_memory"
DATA_FOLDER = "data"

model = SentenceTransformer("all-MiniLM-L6-v2")


def get_file_hash(file_path):
    with open(file_path, "rb") as file:
        return hashlib.md5(file.read()).hexdigest()


def read_text_file(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def read_csv_file(file_path):
    df = pd.read_csv(file_path)

    rows_as_text = []

    for index, row in df.iterrows():
        row_text = []

        for column in df.columns:
            value = row[column]
            row_text.append(f"{column}: {value}")

        rows_as_text.append(" | ".join(row_text))

    return "\n".join(rows_as_text)


def load_document(file_path):
    extension = Path(file_path).suffix.lower()

    if extension in [".txt", ".md"]:
        return read_text_file(file_path)

    elif extension == ".csv":
        return read_csv_file(file_path)

    else:
        print(f"Skipping unsupported file type: {file_path}")
        return None


def chunk_text(text, chunk_size=100, overlap=20):
    words = text.split()
    chunks = []

    step = chunk_size - overlap

    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def main():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    for filename in os.listdir(DATA_FOLDER):
        file_path = os.path.join(DATA_FOLDER, filename)

        if not os.path.isfile(file_path):
            continue

        text = load_document(file_path)

        if text is None:
            continue

        file_hash = get_file_hash(file_path)

        existing = collection.get(
            where={"source": file_path}
        )

        if existing["metadatas"]:
            old_hash = existing["metadatas"][0].get("file_hash")

            if old_hash == file_hash:
                print(f"Skipping unchanged file: {filename}")
                continue

            collection.delete(
                where={"source": file_path}
            )

            print(f"Updated file detected. Re-indexing: {filename}")

        chunks = chunk_text(text)

        for i, chunk in enumerate(chunks):
            chunk_id = f"{file_path}_chunk_{i}"
            embedding = model.encode(chunk).tolist()

            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk],
                metadatas=[{
                    "source": file_path,
                    "filename": filename,
                    "chunk_index": i,
                    "file_hash": file_hash,
                    "file_type": Path(file_path).suffix.lower()
                }]
            )

        print(f"Stored {len(chunks)} chunks from {filename}")

    print("Ingestion complete.")


if __name__ == "__main__":
    main()