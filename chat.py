# chat.py = conversational PI Agent using retrieved memory + Groq Llama

import os

import chromadb
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer

from quality import annotate_memories
from confidence import annotate_confidence, overall_response_tier
import reflection


CHROMA_PATH = "chroma_db"
COLLECTION_NAME = "personal_memory"

NOT_FOUND_MESSAGE = "Information not recorded. Can you give more information?"

# Phrases that route the question to the Reflection Agent instead of normal
# memory retrieval. Simple substring match - deliberately simple for now,
# real intent classification is Phase 5 (Planner) territory.
REFLECTION_TRIGGERS = [
    "how am i doing",
    "my habits",
    "my patterns",
    "reflect on",
    "give me a reflection",
    "my progress",
    "any trends",
    "what patterns",
    "how consistent",
]

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
groq_client = Groq(api_key=GROQ_API_KEY)


def is_reflection_question(question):
    question_lower = question.lower()
    if any(trigger in question_lower for trigger in REFLECTION_TRIGGERS):
        return True
    return reflection.has_habit_reference(question)


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


def build_context(memories):
    context_parts = []

    for i, memory in enumerate(memories, start=1):
        quality = memory.get("quality", {})
        conflict_note = " (CONFLICTS WITH ANOTHER MEMORY)" if quality.get("has_conflict") else ""

        context_parts.append(
            f"Memory {i} [quality score: {quality.get('overall', 'unknown')}, "
            f"confidence: {memory.get('confidence_score', 'unknown')} "
            f"({memory.get('confidence_tier', 'unknown')})]{conflict_note}:\n"
            f"Text: {memory['text']}\n"
            f"Source: {memory['metadata']['filename']}\n"
            f"Date: {memory['metadata'].get('date_modified', 'unknown')}"
        )

    return "\n\n".join(context_parts)


def get_tone_instruction(tier):
    if tier == "high":
        return "You have strong, relevant memory support. Answer directly and confidently."

    if tier == "medium":
        return (
            "Your memory support is moderate - it's likely relevant but not a strong match, "
            "or the data is somewhat old or thin. Answer, but clearly hedge "
            "(e.g. 'it looks like...', 'based on what I have, it seems...') "
            "rather than stating it as certain fact."
        )

    return "low"


def answer_question(question):
    # Route reflection-style questions to the Reflection Agent, bypassing
    # normal single-question retrieval entirely - it needs the whole dataset,
    # not just the top-k chunks closest to this one question.
    if is_reflection_question(question):
        reflection_text = reflection.generate_reflection(question)
        return reflection_text, [], "reflection"

    memories = retrieve_memories(question)
    memories = annotate_memories(memories)
    memories = annotate_confidence(memories)

    tier, best_score = overall_response_tier(memories)

    if tier == "low":
        return NOT_FOUND_MESSAGE, memories, tier

    context = build_context(memories)
    tone_instruction = get_tone_instruction(tier)

    prompt = f"""
You are PI Agent, a personal intelligence assistant.

Answer the user's question using only the retrieved memory context below.

Confidence guidance: {tone_instruction}

Rules:
- Be conversational and clear.
- Do not make up facts.
- If the memory does not contain enough information, say exactly: "{NOT_FOUND_MESSAGE}"
- Weigh memories by their quality and confidence scores - trust higher-scored memories more.
- If two memories conflict, mention the conflict rather than picking one silently.
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

    return response.choices[0].message.content, memories, tier


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

        answer, memories, tier = answer_question(question)

        print(f"\nPI Agent [overall confidence: {tier}]:\n")
        print(answer)

        if memories:
            print("\nSources used:")
            for memory in memories:
                quality = memory.get("quality", {})
                print(
                    f"- {memory['metadata']['filename']} "
                    f"| distance: {memory['distance']:.4f} "
                    f"| quality: {quality.get('overall', 'unknown')} "
                    f"| confidence: {memory.get('confidence_score', 'unknown')} ({memory.get('confidence_tier', 'unknown')}) "
                    f"| conflict: {quality.get('has_conflict', False)}"
                )
        else:
            print("\n(Reflection Agent - analyzed full dataset, not individual retrieved memories.)")

        print()


if __name__ == "__main__":
    main()