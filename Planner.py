import os
import time
from typing import TypedDict, Literal, Optional

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
import privacy

from research.personal_research_agent import run_personal_research

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)
BROAD_TOP_K = 5
INVENTORY_KEYWORDS = (
    "what file",
    "which file",
    "files did i",
    "file did i",
    "synced file",
    "sync file",
    "uploaded file",
    "upload file",
    "added file",
    "most chunks",
    "mostly",
)


class PlannerState(TypedDict):
    question: str
    route: str
    answer: str
    confidence_tier: str
    collection_name: str
    chart: Optional[dict]


def safe_groq_chat(messages, temperature=0.2, max_tokens=300):
    try:
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
    except RateLimitError:
        time.sleep(8)
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )


def classify_question(state):
    prompt = f"""
You are the main planner for an Insight Agent. Classify the question into exactly one route.

memory: single stored fact lookup from documents.
personal_research: multi-doc synthesis, comparison, or explanation.
reflection: patterns, themes, changes over time.
broad: general overview or summary.
sql_insight: numeric aggregation from tabular data (top X by Y, sums, counts, breakdowns).

Question: {state["question"]}

Reply ONLY one word: memory, personal_research, reflection, broad, or sql_insight
"""
    r = safe_groq_chat([{"role": "user", "content": prompt}], temperature=0, max_tokens=10)
    route = r.choices[0].message.content.strip().lower()
    if route not in ["memory", "personal_research", "reflection", "broad", "sql_insight"]:
        route = "memory"
    print(f"[Planner] routed to: {route}")
    return {"route": route}


def route_decision(state) -> Literal["memory", "personal_research", "reflection", "broad", "sql_insight"]:
    return state["route"]


def memory_node(state):
    answer, memories, tier = chat.answer_question(
        state["question"], route_reflection=False,
        collection_name=state.get("collection_name"),
    )
    if NOT_FOUND_MESSAGE in answer:
        tier = "low"
    return {"answer": answer, "confidence_tier": tier, "chart": None}


def personal_research_node(state):
    try:
        answer, evidence, tier = run_personal_research(
            state["question"], collection_name=state.get("collection_name"),
        )
    except RateLimitError:
        time.sleep(8)
        answer, evidence, tier = run_personal_research(
            state["question"], collection_name=state.get("collection_name"),
        )
    if NOT_FOUND_MESSAGE in answer:
        tier = "low"
    return {"answer": answer, "confidence_tier": tier, "chart": None}


def reflection_node(state):
    coll = state.get("collection_name")
    if coll and coll != chat.COLLECTION_NAME:
        answer, tier = reflection.generate_reflection_for_collection(coll, state["question"])
    else:
        answer = reflection.generate_reflection(state["question"])
        tier = "medium"
    if not answer or NOT_FOUND_MESSAGE in answer:
        tier = "low"
    return {"answer": answer, "confidence_tier": tier, "chart": None}


def broad_node(state):
    question = state["question"]
    memories = chat.retrieve_memories(question, top_k=BROAD_TOP_K, collection_name=state.get("collection_name"))
    memories = annotate_memories(memories)
    memories = annotate_confidence(memories)
    if not memories:
        return {"answer": NOT_FOUND_MESSAGE, "confidence_tier": "low", "chart": None}

    context = chat.build_context(memories)
    q_for_llm = redact_sensitive_text(question)
    prompt = f"""
You are an Insight Agent. Synthesize a broad overview from the evidence.
Be direct. Don't invent facts. Be honest if sparse.

Evidence:
{context[:5000]}

Question:
{q_for_llm}
"""
    r = safe_groq_chat(
        [{"role": "system", "content": "Summarize retrieved evidence into a broad overview."},
         {"role": "user", "content": prompt}],
        temperature=0.3, max_tokens=250,
    )
    tier, _ = overall_response_tier(memories)
    if tier == "low":
        tier = "broad"
    return {"answer": r.choices[0].message.content, "confidence_tier": tier, "chart": None}


def sql_insight_node(state):
    import json
    import pandas as pd
    from supabase_client import get_client

    resp = get_client().table("tabular_rows").select("data").eq(
        "collection_name", state["collection_name"]
    ).limit(2000).execute()

    if not resp.data:
        return {"answer": NOT_FOUND_MESSAGE, "chart": None, "confidence_tier": "low"}

    df = pd.DataFrame([r["data"] for r in resp.data])
    numeric = df.select_dtypes("number").columns.tolist()
    categorical = [c for c in df.columns if c not in numeric]

    plan_raw = safe_groq_chat([{"role": "user", "content":
        f"Question: {state['question']}\nColumns: numeric={numeric}, categorical={categorical}\n"
        f'Reply ONLY JSON: {{"group_by":"<col>","measure":"<col>","agg":"sum|avg|count","top":10}}'
    }], temperature=0, max_tokens=120).choices[0].message.content

    try:
        plan = json.loads(plan_raw)
        grouped = getattr(df.groupby(plan["group_by"])[plan["measure"]], plan["agg"])() \
                    .sort_values(ascending=False).head(plan.get("top", 10))
        chart = {
            "type": "bar",
            "title": f'{plan["agg"]}({plan["measure"]}) by {plan["group_by"]}',
            "data": [{"label": str(k)[:15], "value": float(v)} for k, v in grouped.items()],
        }
        narrative = safe_groq_chat([{"role": "user", "content":
            f"Summarize in 2 sentences. Do NOT invent numbers.\nQ: {state['question']}\nData: {chart['data']}"
        }], max_tokens=150).choices[0].message.content
        return {"answer": narrative, "chart": chart, "confidence_tier": "high"}
    except Exception as e:
        print(f"[sql_insight] failed: {e}")
        return {"answer": "Couldn't build a chart from that question.", "chart": None, "confidence_tier": "low"}


def build_planner_graph():
    b = StateGraph(PlannerState)
    b.add_node("classify", classify_question)
    b.add_node("memory", memory_node)
    b.add_node("personal_research", personal_research_node)
    b.add_node("reflection", reflection_node)
    b.add_node("broad", broad_node)
    b.add_node("sql_insight", sql_insight_node)
    b.add_edge(START, "classify")
    b.add_conditional_edges("classify", route_decision, {
        "memory": "memory",
        "personal_research": "personal_research",
        "reflection": "reflection",
        "broad": "broad",
        "sql_insight": "sql_insight",
    })
    for n in ["memory", "personal_research", "reflection", "broad", "sql_insight"]:
        b.add_edge(n, END)
    return b.compile()


graph = build_planner_graph()


def should_answer_inventory(question):
    q = question.lower()
    return any(keyword in q for keyword in INVENTORY_KEYWORDS) and any(
        word in q for word in ("file", "files", "sync", "synced", "upload", "uploaded", "chunks")
    )


def answer_inventory_question(question, collection_name=None):
    inventory = privacy.get_data_inventory(collection_name=collection_name)
    sources = inventory.get("sources", [])

    if inventory.get("error"):
        return {
            "route": "inventory",
            "answer": inventory["error"],
            "confidence_tier": "low",
            "chart": None,
        }

    if not sources:
        return {
            "route": "inventory",
            "answer": "You have not added any files yet. Use the + button in Chat or Add files on Sync to upload a local file.",
            "confidence_tier": "high",
            "chart": None,
        }

    ordered = sorted(
        sources,
        key=lambda item: (item.get("chunk_count") or 0, item.get("last_ingested") or ""),
        reverse=True,
    )
    top = ordered[0]
    lines = [
        f"You have indexed {len(ordered)} file(s) with {inventory.get('total_chunks', 0)} total chunk(s).",
        f"The file with the most chunks is **{top['filename']}** with {top.get('chunk_count', 0)} chunk(s).",
        "",
        "Indexed files:",
    ]

    for source in ordered[:10]:
        lines.append(f"- **{source['filename']}**: {source.get('chunk_count', 0)} chunk(s)")

    if len(ordered) > 10:
        lines.append(f"- ...and {len(ordered) - 10} more")

    return {
        "route": "inventory",
        "answer": "\n".join(lines),
        "confidence_tier": "high",
        "chart": None,
    }


def answer_with_planner(question, collection_name=None):
    g = greeting.respond(question)
    if g is not None:
        return {"route": "greeting", "answer": g, "confidence_tier": "high", "chart": None}

    active_collection = collection_name or chat.COLLECTION_NAME
    if should_answer_inventory(question):
        return answer_inventory_question(question, collection_name=active_collection)

    try:
        result = graph.invoke({
            "question": question, "route": "", "answer": "",
            "confidence_tier": "", "collection_name": active_collection,
            "chart": None,
        })
    except RateLimitError:
        return {"route": "error", "answer": "Rate limit. Try again in a few seconds.",
                "confidence_tier": "low", "chart": None}

    print("[Safe audit log]", build_safe_audit_log(
        question=question, route=result["route"], tool_used=result["route"],
        confidence_tier=result["confidence_tier"], data_type_accessed=result["route"],
    ))
    return result
