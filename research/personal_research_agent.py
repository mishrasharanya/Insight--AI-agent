from retrieve import retrieve_memories
from research.research_planner import create_research_plan
from research.evidence_collector import collect_evidence
from research.gap_detector import detect_gap
from research.synthesizer import synthesize_answer, NOT_FOUND_MESSAGE


def deduplicate_evidence(evidence):
    seen = set()
    unique = []

    for item in evidence:
        key = (
            item.get("source", "unknown"),
            item.get("text", "")
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique


def calculate_overall_confidence(evidence, has_gap, answer=None):
    if has_gap:
        return "low"

    if answer and NOT_FOUND_MESSAGE in answer:
        return "low"

    high_count = sum(
        item.get("confidence_tier") == "high"
        for item in evidence
    )

    medium_count = sum(
        item.get("confidence_tier") == "medium"
        for item in evidence
    )

    if high_count >= 2:
        return "high"

    if high_count == 1 or medium_count >= 2:
        return "medium"

    return "low"


def run_personal_research(question, top_k_per_question=3):
    sub_questions = create_research_plan(question)

    all_memories = []

    for sub_question in sub_questions:
        print(f"[Personal Research] Searching: {sub_question}")
        memories = retrieve_memories(
            sub_question,
            top_k=top_k_per_question
        )
        all_memories.extend(memories)

    evidence = collect_evidence(all_memories)
    evidence = deduplicate_evidence(evidence)

    has_gap, gap_reason = detect_gap(evidence)

    if has_gap:
        second_pass_query = question + " " + " ".join(sub_questions)
        print(f"[Personal Research] Second-pass search: {second_pass_query}")

        second_pass_memories = retrieve_memories(
            second_pass_query,
            top_k=5
        )

        second_pass_evidence = collect_evidence(second_pass_memories)

        evidence.extend(second_pass_evidence)
        evidence = deduplicate_evidence(evidence)

        has_gap, gap_reason = detect_gap(evidence)

    answer = synthesize_answer(
        question=question,
        sub_questions=sub_questions,
        evidence=evidence,
        gap_reason=gap_reason,
    )

    overall_confidence = calculate_overall_confidence(
        evidence=evidence,
        has_gap=has_gap,
        answer=answer,
    )

    return answer, evidence, overall_confidence