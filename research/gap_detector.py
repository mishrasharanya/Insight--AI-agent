def detect_gap(evidence):
    if not evidence:
        return True, "No evidence found."

    high_or_medium = [
        item for item in evidence
        if item.get("confidence_tier") in ["high", "medium"]
    ]

    if not high_or_medium:
        return True, "Only low-confidence evidence found."

    if len(high_or_medium) < 2:
        return True, "Evidence is thin."

    return False, "Enough evidence found."