# chat.py = conversational PI Agent using retrieved memory + Groq Llama

import os

import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from quality import annotate_memories


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "personal_memory"

# If the closest memory's distance is above this, we treat it as "not found"
# rather than risk the LLM answering from outside knowledge.
# Lower distance = closer match. Tune this based on what you see in testing.
DISTANCE_THRESHOLD = 0.9

NOT_FOUND_MESSAGE = "Information not recorded. Can you give more information?"

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=GROQ_API_KEY)


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


def has_relevant_memory(memories):
    """Returns False if even the closest memory is too weak a match to trust."""
    if not memories:
        return False

    best_distance = min(m["distance"] for m in memories)
    return best_distance <= DISTANCE_THRESHOLD


def build_context(memories):
    context_parts = []

    for i, memory in enumerate(memories, start=1):
        quality = memory.get("quality", {})
        conflict_note = " (CONFLICTS WITH ANOTHER MEMORY)" if quality.get("has_conflict") else ""

        context_parts.append(
            f"Memory {i} [quality score: {quality.get('overall', 'unknown')}]{conflict_note}:\n"
            f"Text: {memory['text']}\n"
            f"Source: {memory['metadata']['filename']}\n"
            f"Date: {memory['metadata'].get('date_modified', 'unknown')}"
        )

    return "\n\n".join(context_parts)


def answer_question(question):
    memories = retrieve_memories(question)

    # Hard check BEFORE calling the LLM at all — if nothing relevant was
    # retrieved, don't give the model a chance to answer from outside knowledge.
    if not has_relevant_memory(memories):
        return NOT_FOUND_MESSAGE, memories

    memories = annotate_memories(memories)

    context = build_context(memories)

    prompt = f"""
You are PI Agent, a personal intelligence assistant.

Answer the user's question using only the retrieved memory context below.

Rules:
- Be conversational and clear.
- Do not make up facts.
- If the memory does not contain enough information, say exactly: "{NOT_FOUND_MESSAGE}"
- Weigh memories by their quality score - trust higher-scored memories more.
- If two memories conflict, mention the conflict rather than picking one silently.
- Mention uncertainty when evidence is thin.
- Keep the answer concise.

Retrieved Memory:
{context}

User Question:
{question}
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful personal intelligence assistant that answers using retrieved memory only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
        max_tokens=500
    )

    return response.choices[0].message.content, memories


def main():
    print("===== PI Agent Chat =====")
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        question = input("Ask a question: ").strip()

        if question.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        if not question:
            print("Please type a question.\n")
            continue

        answer, memories = answer_question(question)

        print("\nPI Agent:\n")
        print(answer)

        print("\nSources used:")
        for memory in memories:
            quality = memory.get("quality", {})
            print(
                f"- {memory['metadata']['filename']} "
                f"| distance: {memory['distance']:.4f} "
                f"| quality: {quality.get('overall', 'unknown')} "
                f"| conflict: {quality.get('has_conflict', False)}"
            )

        print()


if __name__ == "__main__":
    main()