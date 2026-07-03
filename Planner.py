import os
from typing import TypedDict, Literal

from dotenv import load_dotenv
from groq import Groq
from langgraph.graph import StateGraph, START, END

from privacy import build_safe_audit_log
import chat
import reflection
import greeting

from research.personal_research_agent import run_personal_research
from research.synthesizer import NOT_FOUND_MESSAGE


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)


class PlannerState(TypedDict):
    question: str
    route: str
    answer: str
    confidence_tier: str


def classify_question(state: PlannerState) -> dict:
    prompt = f"""
You are the main planner for PI Agent.

Classify the user's question into exactly one route.

Available routes:

memory:
Use this when the user asks for one specific stored fact or personal memory.
Examples:
- What is my favorite food?
- Where do I work?
- What city did I mention?
- What project did I say I was building?

personal_research:
Use this when the user asks a deeper question that needs multiple pieces of personal memory,
evidence synthesis, comparison, explanation, or uncertainty handling.
Examples:
- What AI projects have I worked on?
- What evidence shows I am interested in data science?
- How do my projects connect to AI?
- What skills do my past experiences suggest?
- Why have I been stressed recently?
- What patterns exist across my memories?

reflection:
Use this when the user asks about habits, routines, progress, consistency,
emotions over time, goals, trends, or self-reflection.
Examples:
- How have my habits been recently?
- Am I making progress?
- What patterns do you notice in my journal?
- Have I been consistent with reading?
- What should I reflect on?

broad:
Use this when the user asks for a general overview, profile, or summary.
Examples:
- What do you know about me?
- Summarize my background.
- Give me an overview of my personal memory.
- Who am I based on my saved data?

Question:
{state["question"]}

Respond with ONLY one word:
memory, personal_research, reflection, or broad
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
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
    answer, memories, tier = chat.answer_question(state["question"])

    if NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def personal_research_node(state: PlannerState) -> dict:
    answer, evidence, tier = run_personal_research(state["question"])

    if NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def reflection_node(state: PlannerState) -> dict:
    answer = reflection.generate_reflection(state["question"])

    if not answer or NOT_FOUND_MESSAGE in answer:
        tier = "low"
    else:
        tier = "reflection"

    return {
        "answer": answer,
        "confidence_tier": tier,
    }


def broad_node(state: PlannerState) -> dict:
    broad_question = (
        state["question"]
        + "\nAnswer as a broad personal overview using only stored memory. "
        + "Keep it concise. Do not make up facts."
    )

    answer, memories, tier = chat.answer_question(broad_question)

    if NOT_FOUND_MESSAGE in answer:
        tier = "low"

    return {
        "answer": answer,
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


def answer_with_planner(question):
    greeting_answer = greeting.respond(question)

    if greeting_answer is not None:
        return {
            "route": "greeting",
            "answer": greeting_answer,
            "confidence_tier": "high",
        }

    result = graph.invoke(
        {
            "question": question,
            "route": "",
            "answer": "",
            "confidence_tier": "",
        }
    )

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
    print("===== PI Agent Planner =====")
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
            f"\nPI Agent [route: {result['route']} | confidence: {result['confidence_tier']}]:\n"
        )
        print(result["answer"])
        print()


if __name__ == "__main__":
    main()