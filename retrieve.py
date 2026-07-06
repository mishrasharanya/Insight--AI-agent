# retrieve.py = search evidence via Supabase/pgvector

from supabase_client import get_client
from embedding_client import embed_text

COLLECTION_NAME = "personal_memory"


def retrieve_memories(question, top_k=3, collection_name=None):
    client = get_client()
    question_embedding = embed_text(question)

    response = client.rpc(
        "match_chunks",
        {
            "query_embedding": question_embedding,
            "match_collection": collection_name or COLLECTION_NAME,
            "match_count": top_k,
        },
    ).execute()

    memories = []

    for row in response.data or []:
        memories.append({
            "text": row["text"],
            "metadata": {
                "filename": row["filename"],
                "source": row.get("source"),
                "file_type": row.get("file_type"),
                "effective_date": row.get("effective_date"),
            },
            "distance": row["distance"],
        })

    return memories


def main():
    print("===== Insight Agent Search =====")
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        question = input("Ask a question: ").strip()

        if question.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        if not question:
            print("Please type a question.\n")
            continue

        memories = retrieve_memories(question)

        print("\nTop retrieved evidence:\n")

        for i, memory in enumerate(memories, start=1):
            print(f"{i}. {memory['text']}")
            print(f"   Source: {memory['metadata']['filename']}")
            print(f"   File type: {memory['metadata']['file_type']}")
            print(f"   Distance: {memory['distance']:.4f}")
            print()


if __name__ == "__main__":
    main()