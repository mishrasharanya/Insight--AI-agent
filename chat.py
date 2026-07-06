# chat.py = conversational Insight Agent using retrieved evidence + Groq Llama

import os

from dotenv import load_dotenv
from groq import Groq

from quality import annotate_memories
from confidence import annotate_confidence, overall_response_tier
from constants import NOT_FOUND_MESSAGE
from privacy import redact_sensitive_text
from retrieve import retrieve_memories, COLLECTION_NAME
import reflection


# Phrases that route the question to the Insight Agent's reflection/insight path
# when chat.py is run standalone (python chat.py). When called FROM Planner.py,
# this internal routing is bypassed via route_reflection=False, since Planner
# already made the routing decision - having two routers disagree was causing
# conflicts.
#
# NOTE: kept the original habit/reflection phrasing (e.g. "my habits") alongside
# new insight-oriented phrasing, since existing users' questions may still use
# the old wording and we don't want to regress standalone routing.
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
    "main themes",
    "what changed over time",
    "what should i investigate",
    "strongest insights",
    "what's uncertain",
    "what seems uncertain",
]

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)


def is_reflection_question(question):
    question_lower = question.lower()
    if any(trigger in question_lower for trigger in REFLECTION_TRIGGERS):
        return True
    return reflection.has_habit_reference(question)


def build_context(memories):
    context_parts = []

    for i, memory in enumerate(memories, start=1):
        quality = memory.get("quality", {})
        conflict_note = " (CONFLICTS WITH OTHER EVIDENCE)" if quality.get("has_conflict") else ""

        context_parts.append(
            f"Evidence {i} [quality score: {quality.get('overall', 'unknown')}, "
            f"confidence: {memory.get('confidence_score', 'unknown')} "
            f"({memory.get('confidence_tier', 'unknown')})]{conflict_note}:\n"
            f"Text: {memory['text']}\n"
            f"Source: {memory['metadata']['filename']}\n"
            f"Date: {memory['metadata'].get('date_modified', 'unknown')}"
        )

    return "\n\n".join(context_parts)


def get_tone_instruction(tier):
    if tier == "high":
        return "You have strong, relevant evidence. Answer directly and confidently, citing what supports it."

    if tier == "medium":
        return (
            "Your evidence support is moderate - it's likely relevant but not a strong match, "
            "or the data is somewhat old or thin. Answer, but clearly hedge "
            "(e.g. 'the evidence suggests...', 'based on what's available, it looks like...') "
            "rather than stating it as certain fact."
        )

    return "low"


def answer_question(question, route_reflection=True, collection_name=None):
    """
    route_reflection: when True (default, e.g. running chat.py standalone),
    this function does its own reflection/insight-question detection. When
    called from Planner.py, pass route_reflection=False - Planner already
    decided the route via its LLM classifier, and letting chat.py re-decide
    independently can send a question down a different path than Planner
    intended.

    collection_name: per-user scoping (see retrieve_memories docstring).
    """
    if route_reflection and is_reflection_question(question):
        reflection_text = reflection.generate_reflection(question)
        return reflection_text, [], "reflection"

    memories = retrieve_memories(question, collection_name=collection_name)
    memories = annotate_memories(memories)
    memories = annotate_confidence(memories)

    tier, best_score = overall_response_tier(memories)

    if tier == "low":
        return NOT_FOUND_MESSAGE, memories, tier

    context = build_context(memories)
    tone_instruction = get_tone_instruction(tier)

    # Redact PII from the question before it goes into the LLM prompt text.
    # NOTE: we redact only the copy sent to the LLM, not the original `question`
    # used above for embedding/retrieval - redacting that would replace things
    # like an email address with "[REDACTED_EMAIL]" and break the semantic match.
    question_for_llm = redact_sensitive_text(question)

    prompt = f"""
You are an Insight Agent. You analyze the user's documents, notes, and synced
data to produce evidence-grounded insights - not just answers.

Answer the user's question using only the retrieved evidence below.

Confidence guidance: {tone_instruction}

Rules:
- Be clear and direct, not just conversational filler.
- Do not make up facts.
- If the evidence does not contain enough information, say exactly: "{NOT_FOUND_MESSAGE}"
- Weigh evidence by its quality and confidence scores - trust higher-scored evidence more.
- If two pieces of evidence conflict, mention the conflict rather than picking one silently.
- Where relevant, note what the evidence supports vs. what you are inferring.
- Keep the answer concise.

Retrieved Evidence:
{context}

User Question:
{question_for_llm}
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You are an Insight Agent that answers using retrieved evidence only, and is explicit about confidence and uncertainty."
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
    print("===== Insight Agent Chat =====")
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

        print(f"\nInsight Agent [overall confidence: {tier}]:\n")
        print(answer)

        if memories:
            print("\nEvidence used:")
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
            print("\n(Insight Agent - analyzed full dataset, not individual retrieved evidence.)")

        print()


if __name__ == "__main__":
    main()