from quality import annotate_memories
from confidence import annotate_confidence


def deduplicate_memories(memories):
    seen = set()
    unique = []

    for memory in memories:
        text = memory.get("text", "")
        source = memory.get("metadata", {}).get("source", "")
        key = (source, text)

        if key in seen:
            continue

        seen.add(key)
        unique.append(memory)

    return unique


def collect_evidence(memories):
    memories = deduplicate_memories(memories)
    memories = annotate_memories(memories)
    memories = annotate_confidence(memories)

    evidence = []

    for memory in memories:
        evidence.append({
            "text": memory["text"],
            "source": memory["metadata"].get("filename", "unknown"),
            "date": memory["metadata"].get("effective_date", "unknown"),
            "distance": memory["distance"],
            "quality": memory.get("quality", {}),
            "confidence_score": memory.get("confidence_score", 0),
            "confidence_tier": memory.get("confidence_tier", "low"),
        })

    print(f"[Evidence Collector] Collected {len(evidence)} evidence objects")

    return evidence