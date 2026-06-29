def detect_llm(content: str) -> float:
    """Signal 1: LLM-based detection. Returns 0-1 score."""
    # TODO: implement in M3
    return 0.5


def detect_stylo_heuristics(content: str) -> float:
    """Signal 2: Stylometric heuristics. Returns 0-1 score."""
    # TODO: implement in M4
    return 0.5


def detect_pos_dist(content: str) -> float:
    """Signal 3: Part-of-speech distribution. Returns 0-1 score."""
    # TODO: implement in M4
    return 0.5


def combine_scores(llm: float, stylo: float, pos: float) -> float:
    return 0.40 * llm + 0.30 * stylo + 0.30 * pos


def score_to_label(score: float) -> tuple[str, str]:
    """Returns (label, transparency_label) for a given confidence score."""
    if score < 0.4:
        return (
            "likely_ai",
            "This content appears to be partially or fully AI-generated.",
        )
    if score < 0.6:
        return "uncertain", "We're not sure whether this content was AI-generated."
    return "likely_human", "This content appears human-made."
