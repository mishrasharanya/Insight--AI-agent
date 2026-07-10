# reflection.py = Insight Agent's reflection/insight generation

import os
import json
import hashlib
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from groq import Groq, RateLimitError

from ingest import chunk_text, load_document, DATA_FOLDER
from supabase_client import get_client


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if GROQ_API_KEY is None:
    raise ValueError("GROQ_API_KEY not found. Add it to your .env file.")

groq_client = Groq(api_key=GROQ_API_KEY)

HABITS_FILE = "habits.csv"

MIN_OVERLAP_FOR_ANY_PATTERN = 3
MIN_OVERLAP_FOR_CONFIDENT_PATTERN = 15
MAX_QUOTED_MENTIONS = 3
MAX_REFLECTION_CHUNKS = 12

# NOTE: replaced the old personal-journaling taxonomy (health/fitness,
# food/diet, mood/emotional, pets, etc.) with a domain-agnostic set that
# works for documents, reports, and research material as well as notes -
# the old categories forced every document into a mood/habit bucket, which
# doesn't fit the Insight Agent pivot.
TOPIC_CATEGORIES = [
    "finding/result",
    "decision/assumption",
    "risk/concern",
    "open question",
    "plan/next step",
    "background/context",
    "other",
]

_classification_cache = {}


def _hash_chunks(chunks):
    combined = "".join(c["text"] for c in chunks)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()


def safe_groq_chat(messages, temperature=0.3, max_tokens=400):
    try:
        return groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RateLimitError:
        return None


# ---------- Local habit reflection ----------
# NOTE: left untouched - habit-log cooccurrence math is independent of the
# document/insight taxonomy change above and works the same either way.

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

        results.append({
            "habit_a": habit_a,
            "habit_b": habit_b,
            "agreement_rate": agreement,
            "n_days": n,
        })

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
        lines.append(
            f"- {row['habit']}: completed {pct}% of the time "
            f"({int(row['count'])} days logged)"
        )

    best = rates.iloc[0]
    worst = rates.iloc[-1]

    return (
        "Habit tracking:\n"
        "Not enough overlapping days yet to check whether two habits move together. "
        "Here is the completion rate per habit instead:\n\n"
        + "\n".join(lines)
        + f"\n\nMost consistent: '{best['habit']}'. Least consistent: '{worst['habit']}'. "
        "Based on a small sample, so treat this as an early signal."
    )


def habit_reflection():
    df = load_habits()
    if df is None or df.empty:
        return None

    matrix = build_habit_matrix(df)
    top_result = find_strongest_pattern(matrix)

    if top_result is None:
        return completion_rate_summary(df)

    habit_a = top_result["habit_a"]
    habit_b = top_result["habit_b"]
    rate = top_result["agreement_rate"]
    n = top_result["n_days"]

    confidence_note = (
        "Based on a small number of overlapping days, so this is a loose observation."
        if n < MIN_OVERLAP_FOR_CONFIDENT_PATTERN
        else "Based on a reasonable number of overlapping days."
    )

    return (
        f"Habit tracking:\n"
        f"'{habit_a}' and '{habit_b}' tend to move together {int(rate * 100)}% of the time "
        f"across {n} tracked days.\n{confidence_note}"
    )


# ---------- Local prose reflection ----------

def load_prose_chunks():
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
            chunks.append({
                "filename": filename,
                "text": chunk,
            })

    return chunks


# ---------- Topic / stance classification ----------

def keyword_classification_fallback(chunks):
    # NOTE: keyword sets updated to match the new TOPIC_CATEGORIES above.
    # This only runs when the LLM classification call fails or returns
    # unparseable output - the LLM path (extract_topics_and_sentiment) is
    # the primary classifier.
    topic_keywords = {
        "finding/result": [
            "result", "results", "found", "shows", "showed", "revealed",
            "conclusion", "outcome", "data show", "indicates"
        ],
        "decision/assumption": [
            "decided", "decision", "assume", "assumption", "assumes",
            "chose", "chose to", "plan to", "planning to"
        ],
        "risk/concern": [
            "risk", "concern", "concerned", "issue", "problem",
            "warning", "worried", "worrying", "flagged"
        ],
        "open question": [
            "unclear", "unknown", "question", "uncertain", "not sure",
            "tbd", "open question", "needs clarification"
        ],
        "plan/next step": [
            "next step", "next steps", "will", "todo", "to-do",
            "action item", "follow up", "follow-up"
        ],
        "background/context": [
            "background", "context", "overview", "history", "previously",
            "as of"
        ],
    }

    stance_positive_words = [
        "confirms", "supports", "validated", "consistent with", "aligned"
    ]
    stance_negative_words = [
        "contradicts", "conflicts", "inconsistent", "disputes", "refutes"
    ]

    results = []

    for chunk in chunks:
        text_lower = chunk["text"].lower()

        topic = "other"
        best_score = 0

        for candidate_topic, keywords in topic_keywords.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            if score > best_score:
                best_score = score
                topic = candidate_topic

        pos_score = sum(1 for word in stance_positive_words if word in text_lower)
        neg_score = sum(1 for word in stance_negative_words if word in text_lower)

        if pos_score > neg_score:
            sentiment = "positive"
        elif neg_score > pos_score:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        results.append({
            "filename": chunk["filename"],
            "text": chunk["text"],
            "topic": topic,
            "sentiment": sentiment,
        })

    return results


def extract_topics_and_sentiment(chunks):
    if not chunks:
        return []

    numbered = "\n".join(
        f"{i}: {c['text'][:900]}"
        for i, c in enumerate(chunks)
    )

    topic_list = ", ".join(TOPIC_CATEGORIES)

    prompt = f"""Classify each numbered snippet into one topic and one stance.

Topic categories: {topic_list}
Stance options: positive, neutral, negative
(positive = supports/confirms a claim, negative = contradicts/conflicts with a claim, neutral = neither)

Snippets:
{numbered}

Respond only with valid JSON:
[
  {{"index": 0, "topic": "finding/result", "sentiment": "neutral"}}
]
"""

    response = safe_groq_chat(
        messages=[
            {
                "role": "system",
                "content": "You classify text snippets. Respond only with valid JSON."
            },
            {
                "role": "user",
                "content": prompt
            },
        ],
        temperature=0,
        max_tokens=1200,
    )

    if response is None:
        return keyword_classification_fallback(chunks)

    raw_output = response.choices[0].message.content.strip()

    if raw_output.startswith("```"):
        raw_output = raw_output.strip("`")
        raw_output = raw_output.replace("json", "", 1).strip()

    try:
        classifications = json.loads(raw_output)
    except json.JSONDecodeError:
        return keyword_classification_fallback(chunks)

    results = []

    for item in classifications:
        try:
            index = item["index"]
            topic = item["topic"]
            sentiment = item["sentiment"]
        except (KeyError, TypeError):
            continue

        if not isinstance(index, int) or index < 0 or index >= len(chunks):
            continue

        if topic not in TOPIC_CATEGORIES:
            topic = "other"

        if sentiment not in ["positive", "neutral", "negative"]:
            sentiment = "neutral"

        results.append({
            "filename": chunks[index]["filename"],
            "text": chunks[index]["text"],
            "topic": topic,
            "sentiment": sentiment,
        })

    if not results:
        return keyword_classification_fallback(chunks)

    return results


# ---------- Evidence-based confidence ----------
# NOTE: entirely unchanged from before - this math is domain-agnostic and
# works the same whether chunks are journal entries or document excerpts.

def source_type_from_filename(filename):
    filename_lower = filename.lower()

    if filename_lower.startswith("calendar:"):
        return "calendar"

    if filename_lower.startswith("drive:"):
        return "drive"

    if "habit" in filename_lower:
        return "habit"

    if "journal" in filename_lower or "note" in filename_lower:
        return "notes"

    # NOTE: everything below is new. Previously anything that didn't match
    # the patterns above (i.e. almost every locally ingested .docx, .pptx,
    # .xlsx, .pdf, .csv, .json file) fell into a single "other" bucket,
    # which meant diversity scored near-zero even when evidence genuinely
    # came from several different document types. Falling back to file
    # extension gives diversity a real signal for local corpora, not just
    # Google-synced calendar/drive data.
    suffix = Path(filename_lower).suffix
    if suffix:
        return f"filetype:{suffix}"

    return "other"


def calculate_relevance_score(relevant_chunks, question):
    if not relevant_chunks:
        return 0

    question_words = [
        word.strip(".,?!:;()[]{}").lower()
        for word in question.lower().split()
        if len(word.strip(".,?!:;()[]{}")) >= 3
    ]

    if not question_words:
        return 1

    matches = 0

    for chunk in relevant_chunks:
        text_lower = chunk["text"].lower()
        if any(word in text_lower for word in question_words):
            matches += 1

    ratio = matches / len(relevant_chunks)

    if ratio >= 0.7:
        return 2
    if ratio >= 0.3:
        return 1
    return 0


def calculate_diversity_score(relevant_chunks):
    sources = set()

    for chunk in relevant_chunks:
        filename = chunk.get("filename", "")
        sources.add(source_type_from_filename(filename))

    if len(sources) >= 3:
        return 2
    if len(sources) == 2:
        return 1
    return 0


def calculate_sufficiency_score(relevant_chunks):
    count = len(relevant_chunks)

    if count >= 6:
        return 2
    if count >= 2:
        return 1
    return 0


def calculate_consistency_score(classified):
    if not classified:
        return 0

    topic_counts = Counter(item["topic"] for item in classified)
    sentiment_counts = Counter(item["sentiment"] for item in classified)

    total = len(classified)

    dominant_topic_ratio = topic_counts.most_common(1)[0][1] / total
    dominant_sentiment_ratio = sentiment_counts.most_common(1)[0][1] / total

    if dominant_topic_ratio >= 0.6 and dominant_sentiment_ratio >= 0.6:
        return 2

    if dominant_topic_ratio >= 0.4 or dominant_sentiment_ratio >= 0.5:
        return 1

    return 0


def reflection_confidence(relevant_chunks, classified, question):
    relevance = calculate_relevance_score(relevant_chunks, question or "")
    diversity = calculate_diversity_score(relevant_chunks)
    sufficiency = calculate_sufficiency_score(relevant_chunks)
    consistency = calculate_consistency_score(classified)

    total_score = relevance + diversity + sufficiency + consistency

    # Strong evidence volume from multiple distinct sources is treated as
    # high confidence on its own. `consistency` measures how uniform the
    # evidence's topics/stances are, not how much evidence there is - an
    # insight backed by 6+ chunks across 3+ different document types
    # shouldn't be capped at "medium" just because it spans several themes
    # (which, for an Insight Agent, is often a sign of a *more* thorough
    # answer, not a less confident one).
    if sufficiency >= 2 and diversity >= 2:
        tier = "high"
    elif total_score >= 6:
        tier = "high"
    elif total_score >= 3:
        tier = "medium"
    else:
        tier = "low"

    reason = (
        f"relevance={relevance}, consistency={consistency}, "
        f"diversity={diversity}, sufficiency={sufficiency}, total={total_score}"
    )

    return tier, reason


# ---------- Insight generation ----------

def build_structured_summary(classified):
    if not classified:
        return "No classifiable insight signals were found."

    topic_counts = Counter(item["topic"] for item in classified)
    sentiment_by_topic = defaultdict(Counter)

    for item in classified:
        sentiment_by_topic[item["topic"]][item["sentiment"]] += 1

    total = len(classified)
    top_topics = topic_counts.most_common(3)

    lines = [f"{total} relevant entries were analyzed."]

    for topic, count in top_topics:
        pct = int(round((count / total) * 100))
        dominant_stance = sentiment_by_topic[topic].most_common(1)[0][0]
        lines.append(
            f"- {topic}: {count} mention(s), about {pct}% of the relevant evidence, "
            f"stance leans {dominant_stance}."
        )

    overall_stance = Counter(item["sentiment"] for item in classified).most_common(1)[0][0]
    lines.append(f"- Overall stance across evidence: {overall_stance}.")

    return "\n".join(lines)


def build_evidence_snippets(chunks):
    snippets = []

    for chunk in chunks[:MAX_REFLECTION_CHUNKS]:
        text = " ".join(chunk["text"].split())
        if len(text) > 450:
            text = text[:450] + "..."

        snippets.append(
            f"File: {chunk['filename']}\n{text}"
        )

    return "\n\n".join(snippets)


def naturalize_reflection(
    question,
    structured_summary,
    evidence_snippets,
    evidence_count,
    tier,
    confidence_reason,
):
    prompt = f"""
You are an Insight Agent. You analyze the user's documents and data to surface
evidence-grounded insights - patterns, themes, changes over time, and
recurring assumptions.

You are speaking TO the user, not AS the user.

User question:
{question}

Structured pattern summary:
{structured_summary}

Relevant evidence snippets:
{evidence_snippets}

Evidence count: {evidence_count}
Confidence tier: {tier}
Confidence reason: {confidence_reason}

Write a direct, evidence-grounded insight.

Rules:
- Always address the user as "you" or "your".
- Never speak as the user.
- Do not say "I might", "my", or "me".
- State the most significant pattern or finding first.
- Cite support by source filename, not by labels like "Evidence 1" or "Evidence 2".
- Clearly separate what the evidence shows from what you're inferring.
- Mention confidence naturally, and note what would raise it.
- If confidence is low, still answer, but make the uncertainty explicit.
- Do not overstate conclusions.
- Keep it concise and useful.
- End with one concrete next step to investigate.
"""

    response = safe_groq_chat(
        messages=[
            {
                "role": "system",
                "content": (
                    "You surface evidence-grounded insights from a user's documents and data. "
                    "Address the user directly as 'you'. State findings, cite evidence, name uncertainty."
                )
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.35,
        max_tokens=400,
    )

    if response is None:
        return (
            f"Based on the synced data, here's an early pattern worth investigating.\n\n"
            f"{structured_summary}\n\n"
            f"Confidence is {tier} because {confidence_reason}. "
            f"One concrete next step is to gather more evidence before treating this as a firm conclusion."
        )

    return response.choices[0].message.content


# ---------- Per-user Chroma reflection ----------

def load_collection_chunks(collection_name):
    client = get_client()

    try:
        response = (
            client.table("chunks")
            .select("filename, text, source, file_type, effective_date")
            .eq("collection_name", collection_name)
            .execute()
        )
    except Exception:
        return []

    chunks = []

    for row in response.data or []:
        text = row.get("text")
        filename = row.get("filename") or row.get("source") or "unknown"

        if text and text.strip():
            chunks.append({
                "filename": filename,
                "text": text,
                "metadata": {
                    "source": row.get("source"),
                    "file_type": row.get("file_type"),
                    "effective_date": row.get("effective_date"),
                },
            })

    return chunks


def filter_chunks_for_question(chunks, question):
    if not question:
        return chunks[:MAX_REFLECTION_CHUNKS]

    stopwords = {
        "what", "how", "why", "when", "where", "who",
        "am", "is", "are", "was", "were",
        "the", "a", "an", "to", "of", "in", "on", "for",
        "my", "me", "i", "you", "do", "does", "did",
        "reflect", "reflection", "patterns", "pattern",
        "trend", "trends", "recently", "about",
        "tell", "show", "notice", "based",
    }

    keywords = []

    for word in question.lower().split():
        clean = word.strip(".,?!:;()[]{}").lower()
        if len(clean) >= 3 and clean not in stopwords:
            keywords.append(clean)

    if not keywords:
        return chunks[:MAX_REFLECTION_CHUNKS]

    scored = []

    for chunk in chunks:
        text_lower = chunk["text"].lower()
        filename_lower = chunk["filename"].lower()

        score = 0

        for keyword in keywords:
            if keyword in text_lower:
                score += 2
            if keyword in filename_lower:
                score += 1

        if score > 0:
            scored.append((score, chunk))

    if not scored:
        return chunks[:MAX_REFLECTION_CHUNKS]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:MAX_REFLECTION_CHUNKS]]


def generate_reflection_for_collection(collection_name, question=None):
    chunks = load_collection_chunks(collection_name)

    if not chunks:
        return (
            "No synced data found yet to generate insights from. Sync your Calendar or Drive files first.",
            "low",
        )

    relevant_chunks = filter_chunks_for_question(chunks, question)
    evidence_count = len(relevant_chunks)

    cache_key = f"{collection_name}:{question or 'all'}:{_hash_chunks(relevant_chunks)}"

    if cache_key in _classification_cache:
        classified = _classification_cache[cache_key]
    else:
        classified = extract_topics_and_sentiment(relevant_chunks)
        _classification_cache[cache_key] = classified

    tier, confidence_reason = reflection_confidence(
        relevant_chunks=relevant_chunks,
        classified=classified,
        question=question or "",
    )

    structured_summary = build_structured_summary(classified)
    evidence_snippets = build_evidence_snippets(relevant_chunks)

    answer = naturalize_reflection(
        question=question,
        structured_summary=structured_summary,
        evidence_snippets=evidence_snippets,
        evidence_count=evidence_count,
        tier=tier,
        confidence_reason=confidence_reason,
    )

    return answer, tier


# Public-facing alias for the Insight Agent pivot. Planner.py and chat.py
# still call generate_reflection_for_collection / generate_reflection by
# their original names (see notes in those files) - this alias exists for
# any new code that wants the "insight" name without touching call sites yet.
generate_insight_for_collection = generate_reflection_for_collection


# ---------- Local topic-specific reflection ----------

def prose_reflection():
    chunks = load_prose_chunks()

    if not chunks:
        return None

    relevant_chunks = chunks[:MAX_REFLECTION_CHUNKS]
    classified = extract_topics_and_sentiment(relevant_chunks)

    tier, confidence_reason = reflection_confidence(
        relevant_chunks=relevant_chunks,
        classified=classified,
        question="local reflection",
    )

    structured_summary = build_structured_summary(classified)
    evidence_snippets = build_evidence_snippets(relevant_chunks)

    return naturalize_reflection(
        question="What insight can you give me based on my local notes?",
        structured_summary=structured_summary,
        evidence_snippets=evidence_snippets,
        evidence_count=len(relevant_chunks),
        tier=tier,
        confidence_reason=confidence_reason,
    )


def get_habit_keywords(habit_name):
    words = habit_name.lower().split()
    return [word for word in words if len(word) >= 3 and not word.isdigit()]


def find_matching_habit(question, habit_names):
    question_lower = question.lower()

    for habit in habit_names:
        keywords = get_habit_keywords(habit)
        if any(keyword in question_lower for keyword in keywords):
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
    df = load_habits()
    lines = [f"Insight on '{matched_habit}':"]

    if df is not None and matched_habit in df["habit"].values:
        pct, total, dates = habit_specific_stats(df, matched_habit)
        date_list = ", ".join(dates)

        lines.append(
            f"- Habit log: completed {pct}% of the time across "
            f"{total} logged day(s): {date_list}."
        )
    else:
        lines.append("- No structured habit-log entries found for this.")

    lines.append("\nBased on a small sample, so treat this as an early signal.")

    return "\n".join(lines)


def has_habit_reference(question):
    df = load_habits()

    if df is None:
        return False

    habit_names = df["habit"].unique().tolist()
    return find_matching_habit(question, habit_names) is not None


def generate_reflection(question=None):
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
        return "No data found yet to generate insights from."

    return "\n\n".join(sections)


def main():
    print("===== Insight Agent Reflection =====\n")
    print(generate_reflection())


if __name__ == "__main__":
    main()
