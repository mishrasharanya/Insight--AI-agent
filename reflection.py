# reflection.py = Phase 4 Reflection Agent
# Combines structured habit data (habits.csv) with LLM-extracted signals from prose
# files (notes.txt, journal.md, etc.) into one honest reflection summary.
# If the question mentions a specific habit/topic, filters to just that slice
# instead of always dumping the full dataset summary.

import os
import json
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq

from ingest import chunk_text, load_document, DATA_FOLDER

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

HABITS_FILE = "habits.csv"
MIN_OVERLAP_FOR_ANY_PATTERN = 3
MIN_OVERLAP_FOR_CONFIDENT_PATTERN = 15
MAX_QUOTED_MENTIONS = 3

TOPIC_CATEGORIES = [
    "health/fitness", "food/diet", "work", "relationships/social",
    "mood/emotional", "goals/plans", "pets", "other"
]


# ---------- CSV habit analysis ----------

def load_habits():
    file_path = os.path.join(DATA_FOLDER, HABITS_FILE)
    if not os.path.exists(file_path):
        return None
    return pd.read_csv(file_path)


def build_habit_matrix(df):
    df = df.copy()
    df["completed_binary"] = df["completed"].str.lower().map({"yes": 1, "no": 0})
    return df.pivot_table(index="date", columns="habit", values="completed_binary")


def calculate_cooccurrence(matrix, habit_a, habit_b):
    paired = matrix[[habit_a, habit_b]].dropna()
    if paired.empty:
        return None, 0
    agreement = (paired[habit_a] == paired[habit_b]).mean()
    return round(agreement, 3), len(paired)


def find_strongest_pattern(matrix):
    habits = matrix.columns.tolist()
    results = []
    for habit_a, habit_b in combinations(habits, 2):
        agreement, n = calculate_cooccurrence(matrix, habit_a, habit_b)
        if agreement is None or n < MIN_OVERLAP_FOR_ANY_PATTERN:
            continue
        results.append({"habit_a": habit_a, "habit_b": habit_b, "agreement_rate": agreement, "n_days": n})
    if not results:
        return None
    results.sort(key=lambda r: r["agreement_rate"], reverse=True)
    return results[0]


def completion_rate_summary(df):
    df = df.copy()
    df["completed_binary"] = df["completed"].str.lower().map({"yes": 1, "no": 0})
    rates = df.groupby("habit")["completed_binary"].agg(["mean", "count"]).reset_index()
    rates = rates.sort_values("mean", ascending=False)

    lines = []
    for _, row in rates.iterrows():
        pct = int(round(row["mean"] * 100))
        lines.append(f"- {row['habit']}: completed {pct}% of the time ({int(row['count'])} days logged)")

    best = rates.iloc[0]
    worst = rates.iloc[-1]

    return (
        "Habit tracking (from habits.csv):\n"
        "Not enough overlapping days yet to check whether two habits move together. "
        "Here's completion rate per habit instead:\n\n"
        + "\n".join(lines)
        + f"\n\nMost consistent: '{best['habit']}'. Least consistent: '{worst['habit']}'. "
        "Based on a small sample - early signal, not a firm conclusion."
    )


def habit_reflection():
    df = load_habits()
    if df is None or df.empty:
        return None

    matrix = build_habit_matrix(df)
    top_result = find_strongest_pattern(matrix)

    if top_result is None:
        return completion_rate_summary(df)

    habit_a, habit_b = top_result["habit_a"], top_result["habit_b"]
    rate, n = top_result["agreement_rate"], top_result["n_days"]

    confidence_note = (
        "Based on a small number of overlapping days - a loose observation, not a proven pattern."
        if n < MIN_OVERLAP_FOR_CONFIDENT_PATTERN
        else "Based on a reasonable number of overlapping days."
    )

    return (
        f"Habit tracking (from habits.csv):\n"
        f"'{habit_a}' and '{habit_b}' tend to move together {int(rate * 100)}% of the time "
        f"across {n} days you tracked both.\n{confidence_note}"
    )


# ---------- Prose loading ----------

def load_prose_chunks():
    """Loads and chunks every non-CSV file in data/. Returns list of {filename, text}."""
    chunks = []

    if not os.path.isdir(DATA_FOLDER):
        return chunks

    for filename in os.listdir(DATA_FOLDER):
        file_path = os.path.join(DATA_FOLDER, filename)

        if not os.path.isfile(file_path):
            continue
        if Path(file_path).suffix.lower() == ".csv":
            continue

        text = load_document(file_path)
        if text is None:
            continue

        for chunk in chunk_text(text):
            chunks.append({"filename": filename, "text": chunk})

    return chunks


def extract_topics_and_sentiment(chunks):
    """
    Sends prose chunks to the LLM in one batch call, classifying each into a
    topic category and sentiment. Returns list of {filename, text, topic, sentiment}.
    """
    if not chunks:
        return []

    numbered = "\n".join(f"{i}: {c['text']}" for i, c in enumerate(chunks))
    topic_list = ", ".join(TOPIC_CATEGORIES)

    prompt = f"""Classify each numbered snippet below into exactly one topic category
and one sentiment.

Topic categories (pick the closest fit): {topic_list}
Sentiment options: positive, neutral, negative

Snippets:
{numbered}

Respond ONLY with a JSON array, no other text, in this exact format:
[{{"index": 0, "topic": "...", "sentiment": "..."}}, {{"index": 1, "topic": "...", "sentiment": "..."}}]
"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You classify short personal text snippets by topic and sentiment. Respond only with valid JSON, nothing else."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        max_tokens=2000
    )

    raw_output = response.choices[0].message.content.strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        raw_output = raw_output.replace("json", "", 1).strip()

    try:
        classifications = json.loads(raw_output)
    except json.JSONDecodeError:
        return []

    results = []
    for item in classifications:
        try:
            index = item["index"]
            topic = item["topic"]
            sentiment = item["sentiment"]
        except (KeyError, TypeError):
            continue

        if not isinstance(index, int) or index >= len(chunks) or index < 0:
            continue

        results.append({
            "filename": chunks[index]["filename"],
            "text": chunks[index]["text"],
            "topic": topic,
            "sentiment": sentiment
        })

    return results


def prose_reflection():
    """Full-dataset topic-frequency and sentiment summary (used for broad questions)."""
    chunks = load_prose_chunks()
    if not chunks:
        return None

    classified = extract_topics_and_sentiment(chunks)
    if not classified:
        return "Journal/notes analysis: could not classify content this time (LLM extraction failed) - try again."

    topic_counts = Counter(item["topic"] for item in classified)
    sentiment_by_topic = defaultdict(Counter)
    for item in classified:
        sentiment_by_topic[item["topic"]][item["sentiment"]] += 1

    total = len(classified)
    top_topics = topic_counts.most_common(3)

    lines = [f"Journal/notes analysis (from {total} entries across your notes and journal):"]
    for rank, (topic, count) in enumerate(top_topics):
        pct = int(round((count / total) * 100))
        sentiments = sentiment_by_topic[topic]
        dominant_sentiment = sentiments.most_common(1)[0][0]
        label = "comes up most" if rank == 0 else "next most common"
        lines.append(
            f"- '{topic}' {label} ({count} mentions, {pct}% of entries), tone leans {dominant_sentiment}"
        )

    overall_sentiment = Counter(item["sentiment"] for item in classified)
    dominant_overall = overall_sentiment.most_common(1)[0][0]
    lines.append(f"\nOverall tone across your notes leans {dominant_overall}.")
    lines.append(f"(Based on {total} entries - a small sample, treat as an early signal.)")

    return "\n".join(lines)


# ---------- Topic-specific (filtered) reflection ----------

def get_habit_keywords(habit_name):
    """Pulls distinctive words (3+ letters, not pure numbers) out of a habit name to match against questions."""
    words = habit_name.lower().split()
    return [w for w in words if len(w) >= 3 and not w.isdigit()]


def find_matching_habit(question, habit_names):
    """Returns the first habit whose keywords appear in the question, or None."""
    question_lower = question.lower()
    for habit in habit_names:
        keywords = get_habit_keywords(habit)
        if any(kw in question_lower for kw in keywords):
            return habit
    return None


def habit_specific_stats(df, habit_name):
    rows = df[df["habit"] == habit_name].copy()
    rows["completed_binary"] = rows["completed"].str.lower().map({"yes": 1, "no": 0})
    total = len(rows)
    completed = int(rows["completed_binary"].sum())
    pct = int(round((completed / total) * 100)) if total else 0
    dates = rows["date"].tolist()
    return pct, total, dates


def generate_topic_reflection(matched_habit):
    """Reflection filtered to one specific habit/topic, instead of the full dataset."""
    df = load_habits()
    lines = [f"Reflection on '{matched_habit}':"]

    if df is not None and matched_habit in df["habit"].values:
        pct, total, dates = habit_specific_stats(df, matched_habit)
        date_list = ", ".join(dates)
        lines.append(f"- Habit log: completed {pct}% of the time ({total} day(s) logged: {date_list}).")
    else:
        lines.append("- No structured habit-log entries found for this.")

    keywords = get_habit_keywords(matched_habit)
    prose_chunks = load_prose_chunks()
    matching_chunks = [
        c for c in prose_chunks
        if any(kw in c["text"].lower() for kw in keywords)
    ]

    if matching_chunks:
        lines.append(f"- Found {len(matching_chunks)} related mention(s) in your notes/journal:")
        for c in matching_chunks[:MAX_QUOTED_MENTIONS]:
            snippet = c["text"][:150]
            lines.append(f'  - ({c["filename"]}): "{snippet}"')
        if len(matching_chunks) > MAX_QUOTED_MENTIONS:
            lines.append(f"  - ...and {len(matching_chunks) - MAX_QUOTED_MENTIONS} more not shown.")
    else:
        lines.append("- No related mentions found in your notes/journal.")

    lines.append("\nBased on a small sample - early signal, not a firm conclusion.")
    return "\n".join(lines)


# ---------- Combined / routed reflection ----------

def has_habit_reference(question):
    """True if the question mentions a specific tracked habit by name/keyword."""
    df = load_habits()
    if df is None:
        return False
    habit_names = df["habit"].unique().tolist()
    return find_matching_habit(question, habit_names) is not None


def generate_reflection(question=None):
    """
    If the question names a specific habit/topic, returns a filtered reflection
    for just that. Otherwise (or if no question given), returns the full summary.
    """
    df = load_habits()
    habit_names = df["habit"].unique().tolist() if df is not None else []

    if question:
        matched_habit = find_matching_habit(question, habit_names)
        if matched_habit:
            return generate_topic_reflection(matched_habit)

    sections = []
    habit_section = habit_reflection()
    if habit_section:
        sections.append(habit_section)

    prose_section = prose_reflection()
    if prose_section:
        sections.append(prose_section)

    if not sections:
        return "No data found yet to reflect on."

    return "\n\n".join(sections)


def main():
    print("===== PI Agent Reflection =====\n")
    print(generate_reflection())


if __name__ == "__main__":
    main()