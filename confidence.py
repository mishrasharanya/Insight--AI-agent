# confidence.py = blend retrieval distance + quality scores into confidence tiers

HIGH_CONFIDENCE_THRESHOLD = 0.65
MEDIUM_CONFIDENCE_THRESHOLD = 0.35


def distance_to_similarity(distance):
    """
    Converts raw retrieval distance into a bounded 0-1 similarity score.
    Lower distance means better match.
    """
    try:
        distance = float(distance)
    except (TypeError, ValueError):
        return 0.0

    return round(1 / (1 + distance), 3)


def calculate_memory_confidence(memory):
    """
    Confidence for one memory.

    Relevance comes first.
    Quality can scale relevance, but cannot fully rescue irrelevant retrieval.
    """
    similarity = distance_to_similarity(memory.get("distance", 999))
    quality_overall = memory.get("quality", {}).get("overall", 0.5)

    quality_multiplier = 0.5 + (0.5 * quality_overall)

    confidence = similarity * quality_multiplier
    return round(confidence, 3)


def get_confidence_tier(confidence_score):
    """
    Maps 0-1 confidence score to behavior tier.
    """
    if confidence_score >= HIGH_CONFIDENCE_THRESHOLD:
        return "high"

    if confidence_score >= MEDIUM_CONFIDENCE_THRESHOLD:
        return "medium"

    return "low"


def annotate_confidence(memories):
    """
    Adds confidence_score and confidence_tier to each memory.
    Call after annotate_memories().
    """
    for memory in memories:
        score = calculate_memory_confidence(memory)
        memory["confidence_score"] = score
        memory["confidence_tier"] = get_confidence_tier(score)

    return memories


def overall_response_tier(memories):
    """
    Overall response tier based on best supported memory.
    """
    if not memories:
        return "low", 0.0

    best_memory = max(
        memories,
        key=lambda m: m.get("confidence_score", 0)
    )

    return (
        best_memory.get("confidence_tier", "low"),
        best_memory.get("confidence_score", 0.0),
    )


def evidence_confidence_tier(evidence):
    """
    Used by Personal Research Agent.
    Determines confidence from collected evidence objects.
    """
    if not evidence:
        return "low"

    tiers = [item.get("confidence_tier", "low") for item in evidence]

    if "high" in tiers:
        return "high"

    if "medium" in tiers:
        return "medium"

    return "low"


# ---------- Diagnostic helper (temporary - not called anywhere by default) ----------
#
# Run this against a batch of retrieved memories to see the RAW numbers behind
# every confidence score - distance, similarity, quality_overall, and the
# final blended confidence. This is what you need before touching the
# thresholds above: guessing new threshold values without seeing the actual
# distribution of distances your embeddings produce risks overcorrecting in
# the other direction (e.g. everything becomes "high").
#
# Usage from a Python shell or a quick script:
#
#   import chat, confidence
#   memories = chat.retrieve_memories("your test question here")
#   from quality import annotate_memories
#   memories = annotate_memories(memories)
#   confidence.print_confidence_breakdown(memories)

def print_confidence_breakdown(memories):
    print(f"\n{'FILE':<28} {'DISTANCE':<10} {'SIMILARITY':<12} {'QUALITY':<10} {'CONFIDENCE':<12} {'TIER':<8}")
    print("-" * 82)

    for memory in memories:
        filename = memory.get("metadata", {}).get("filename", "unknown")
        distance = memory.get("distance", "n/a")
        similarity = distance_to_similarity(memory.get("distance", 999))
        quality_overall = memory.get("quality", {}).get("overall", "n/a")
        confidence_score = calculate_memory_confidence(memory)
        tier = get_confidence_tier(confidence_score)

        print(
            f"{filename[:26]:<28} "
            f"{str(distance)[:8]:<10} "
            f"{similarity:<12} "
            f"{str(quality_overall)[:8]:<10} "
            f"{confidence_score:<12} "
            f"{tier:<8}"
        )