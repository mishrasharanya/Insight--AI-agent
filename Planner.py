import os
import time
from typing import TypedDict, Literal

from dotenv import load_dotenv
from groq import Groq, RateLimitError
from langgraph.graph import StateGraph, START, END

from privacy import build_safe_audit_log, redact_sensitive_text
from constants import NOT_FOUND_MESSAGE
from quality import annotate_memories
from confidence import annotate_confidence, overall_response_tier

import chat
import reflection
import greeting

from research.personal_research_agent import run_personal_research


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)

BROAD_TOP_K = 5


class PlannerState(TypedDict):
    question: str
    route: str
    answer: str
    confidence_tier: str
    collection_name: str


def safe_groq_chat(messages, temperature=0.2, max_tokens=300):
    try:
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RateLimitError:
        print("[Groq] Rate limit hit. Waiting 8 seconds and retrying...")
        time.sleep(8)
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )


def classify_question(state: PlannerState) -> dict:
    # NOTE: route KEYS below (memory / personal_research / reflection / broad)
    # are unchanged - route_decision, the graph edges, and valid_routes all
    # depend on these exact strings. What changed is the *examples* under each
    # route: they used to be personal-memory questions ("What is my favorite
    # food?"), which actively mis-trains the classifier for an Insight Agent
    # that's meant to analyze documents/reports rather than recall personal
    # facts. The examples now match the kinds of questions the Insight Agent
    # product is meant to answer.
    prompt = f"""
You are the main planner for an Insight Agent.

Classify the user's question into exactly one route.

Available routes:

memory:
Use this when the user asks for one specific stored fact from their synced
documents or data - a direct lookup, not analysis.
Examples:
- What did the Q3 report say about churn?
- When is my meeting with the design team?
- What deadline did the project plan mention?
- What did I write in my notes about the vendor contract?

personal_research:
Use this when the user asks a deeper question that needs multiple pieces of
evidence, synthesis across documents, comparison, explanation, or uncertainty
handling.
Examples:
- What assumptions show up repeatedly across these documents?
- What evidence supports the conclusion in this report?
- How do these projects connect to each other?
- What does the evidence suggest about why this metric changed?
- What should I investigate next based on what's here?

reflection:
Use this when the user asks about patterns, themes, changes over time,
recurring decisions or assumptions, or wants a synthesized insight rather
than a single fact.
Examples:
- What patterns do you notice across my documents?
- What are the strongest insights from this corpus?
- What changed over time in these reports?
- What seems uncertain in what I have so far?
- What decisions or assumptions keep coming up?

broad:
Use this when the user asks for a general overview, profile, or summary
rather than a specific insight or fact.
Examples:
- What do you know based on everything synced so far?
- Summarize what's in my documents.
- Give me an overview of my synced data.
- What's the big picture here?

Question:
{state["question"]}

Respond with ONLY one word:
memory, personal_research, reflection, or broad
"""

    response = safe_groq_chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=10,
    )

    route = response.choices[0].message.content.strip().lower()

    valid_routes = ["memory", "personal_research", "reflection", "broad"]

    if route not in valid_routes:
        route = "memory"

    print(f"[Planner] routed to: {route}")

    return {"route": route}


def route_decision(
    state: PlannerState,
) -> Literal["memory", "personal_research", "reflection", "broad"]:
    return state["route"]


def memory_node(state: PlannerState) -> dict:
    answer, memories, tier = chat.answer_question(
        state["question"],
        route_reflection=False,
        collection_name=state.get("collection_name"),
    )

    if NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def personal_research_node(state: PlannerState) -> dict:
    try:
        answer, evidence, tier = run_personal_research(
            state["question"],
            collection_name=state.get("collection_name"),
        )
    except RateLimitError:
        print("[Personal Research] Groq rate limit hit. Waiting and retrying once...")
        time.sleep(8)
        answer, evidence, tier = run_personal_research(
            state["question"],
            collection_name=state.get("collection_name"),
        )

    if NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def reflection_node(state: PlannerState) -> dict:
    collection_name = state.get("collection_name")

    if collection_name and collection_name != chat.COLLECTION_NAME:
        answer, tier = reflection.generate_reflection_for_collection(
            collection_name,
            state["question"],
        )
    else:
        answer = reflection.generate_reflection(state["question"])
        tier = "medium"

    if not answer or NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def broad_node(state: PlannerState) -> dict:
    question = state["question"]

    memories = chat.retrieve_memories(
        question,
        top_k=BROAD_TOP_K,
        collection_name=state.get("collection_name"),
    )

    memories = annotate_memories(memories)
    memories = annotate_confidence(memories)

    if not memories:
        return {
            "answer": NOT_FOUND_MESSAGE,
            "confidence_tier": "low",
        }

    context = chat.build_context(memories)
    question_for_llm = redact_sensitive_text(question)

    prompt = f"""
You are an Insight Agent. The user asked a broad, general question. Synthesize
an overview using the evidence snippets below.

Rules:
- Be clear and direct.
- Do not make up facts beyond what's in the snippets.
- If the snippets are too sparse to say much, be honest about that.
- Keep the answer concise.

Retrieved Evidence:
{context[:5000]}

User Question:
{question_for_llm}
"""

    response = safe_groq_chat(
        messages=[
            {
                "role": "system",
                "content": "You summarize a user's retrieved evidence into a broad overview.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.3,
        max_tokens=250,
    )

    tier, _ = overall_response_tier(memories)

    if tier == "low":
        tier = "broad"

    return {
        "answer": response.choices[0].message.content,
        "confidence_tier": tier,
    }


def build_planner_graph():
    builder = StateGraph(PlannerState)

    builder.add_node("classify", classify_question)
    builder.add_node("memory", memory_node)
    builder.add_node("personal_research", personal_research_node)
    builder.add_node("reflection", reflection_node)
    builder.add_node("broad", broad_node)

    builder.add_edge(START, "classify")

    builder.add_conditional_edges(
        "classify",
        route_decision,
        {
            "memory": "memory",
            "personal_research": "personal_research",
            "reflection": "reflection",
            "broad": "broad",
        },
    )

    builder.add_edge("memory", END)
    builder.add_edge("personal_research", END)
    builder.add_edge("reflection", END)
    builder.add_edge("broad", END)

    return builder.compile()


graph = build_planner_graph()


def answer_with_planner(question, collection_name=None):
    greeting_answer = greeting.respond(question)

    if greeting_answer is not None:
        return {
            "route": "greeting",
            "answer": greeting_answer,
            "confidence_tier": "high",
        }

    try:
        result = graph.invoke(
            {
                "question": question,
                "route": "",
                "answer": "",
                "confidence_tier": "",
                "collection_name": collection_name or chat.COLLECTION_NAME,
            }
        )
    except RateLimitError:
        return {
            "route": "error",
            "answer": "Groq hit its free-tier rate limit. Please wait a few seconds and try again.",
            "confidence_tier": "low",
        }

    audit_log = build_safe_audit_log(
        question=question,
        route=result["route"],
        tool_used=result["route"],
        confidence_tier=result["confidence_tier"],
        data_type_accessed=result["route"],
    )

    print("[Safe audit log]", audit_log)

    return result


def main():
    print("===== Insight Agent Planner =====")
    print("Type 'quit' or 'exit' to leave.\n")

    while True:
        question = input("Ask a question: ").strip()

        if question.lower() in ["quit", "exit"]:
            print("Goodbye!")
            break

        if not question:
            print("Please type a question.\n")
            continue

        result = answer_with_planner(question)

        print(
            f"\nInsight Agent [route: {result['route']} | confidence: {result['confidence_tier']}]:\n"
        )
        print(result["answer"])
        print()


if __name__ == "__main__":
    main()