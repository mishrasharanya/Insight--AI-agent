# retrieve.py = search memory from database

import chromadb
from sentence_transformers import SentenceTransformer


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "personal_memory"

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def retrieve_memories(question, top_k=3):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(name=COLLECTION_NAME)

    question_embedding = embedding_model.encode(question).tolist()

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    memories = []

    for i in range(len(results["documents"][0])):
        memories.append({
            "text": results["documents"][0][i],
            "metadata": results["metadatas"][0][i],
            "distance": results["distances"][0][i]
        })

    return memories


def main():
    print("===== Personal Memory Search =====")
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

        print("\nTop retrieved memories:\n")

        for i, memory in enumerate(memories, start=1):
            print(f"{i}. {memory['text']}")
            print(f"   Source: {memory['metadata']['filename']}")
            print(f"   File type: {memory['metadata']['file_type']}")
            print(f"   Distance: {memory['distance']:.4f}")
            print()


if __name__ == "__main__":
    main()