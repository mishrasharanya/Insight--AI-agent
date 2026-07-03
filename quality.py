# quality.py = score retrieved memories for freshness, completeness, and conflicts

import os
from datetime import datetime

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

FRESHNESS_HALF_LIFE_DAYS = 180
MIN_WORDS_FOR_FULL_COMPLETENESS = 15


def calculate_freshness_score(date_str):
    """
    1.0 = new, decays toward 0 as content ages.
    Uses effective_date when available.
    """
    try:
        date_value = datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        return 0.5

    age_days = (datetime.now() - date_value).days
    age_days = max(age_days, 0)

    score = 0.5 ** (age_days / FRESHNESS_HALF_LIFE_DAYS)
    return round(score, 3)


def calculate_completeness_score(text):
    """
    Penalizes very short chunks that likely lack context.
    """
    word_count = len(str(text).split())

    if word_count >= MIN_WORDS_FOR_FULL_COMPLETENESS:
        return 1.0

    return round(word_count / MIN_WORDS_FOR_FULL_COMPLETENESS, 3)


def detect_conflicts(memories):
    """
    Uses the LLM to check retrieved memories against each other for contradictions.
    Conservative: only clear, direct contradictions are flagged.
    """
    if len(memories) < 2:
        return {}

    numbered_memories = "\n".join(
        f"{i}: {m['text']}" for i, m in enumerate(memories)
    )

    prompt = f"""
Below are numbered memory snippets retrieved for the same question.

Identify pairs that factually CONTRADICT each other.

Do NOT flag:
- normal routine variation
- changed preferences over time
- partial vs fuller detail
- approximate numbers
- vague or incomplete snippets
- unrelated snippets sharing a keyword

Only flag clear direct contradictions.

Memories:
{numbered_memories}

Respond ONLY in this exact format, one line per conflicting pair:
INDEX,INDEX

If there are no conflicts, respond exactly:
NONE
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": "You detect factual contradictions between short text snippets. Be conservative."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0,
        max_tokens=200,
    )

    raw_output = response.choices[0].message.content.strip()

    if raw_output == "NONE" or not raw_output:
        return {}

    conflicts = {}

    for line in raw_output.splitlines():
        line = line.strip()

        if "," not in line:
            continue

        try:
            a_str, b_str = line.split(",", 1)
            a = int(a_str.strip())
            b = int(b_str.strip())
        except ValueError:
            continue

        if a < 0 or b < 0 or a >= len(memories) or b >= len(memories):
            continue

        conflicts.setdefault(a, []).append(b)
        conflicts.setdefault(b, []).append(a)

    return conflicts


def calculate_source_diversity(memories):
    """
    Rewards evidence coming from multiple files/sources.
    Useful for Personal Research Agent.
    """
    if not memories:
        return 0.0

    sources = set(
        memory["metadata"].get("filename", "unknown")
        for memory in memories
    )

    if len(sources) == 1:
        return 0.5

    if len(sources) == 2:
        return 0.75

    return 1.0


def annotate_memories(memories):
    """
    Adds a quality dict to each memory:
    freshness, completeness, source_diversity, conflict info, overall.
    """
    conflicts = detect_conflicts(memories)
    source_diversity = calculate_source_diversity(memories)

    for i, memory in enumerate(memories):
        metadata = memory.get("metadata", {})

        date_to_use = (
            metadata.get("effective_date")
            or metadata.get("content_date")
            or metadata.get("date_modified")
        )

        freshness = calculate_freshness_score(date_to_use)
        completeness = calculate_completeness_score(memory.get("text", ""))
        has_conflict = i in conflicts

        overall = (
            freshness * 0.35
            + completeness * 0.35
            + source_diversity * 0.30
        )

        if has_conflict:
            overall *= 0.5

        memory["quality"] = {
            "freshness": freshness,
            "completeness": completeness,
            "source_diversity": source_diversity,
            "has_conflict": has_conflict,
            "conflicts_with": conflicts.get(i, []),
            "overall": round(overall, 3),
        }

    return memories