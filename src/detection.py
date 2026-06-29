import os
import re
from groq import Groq

from log import write_log

# Detection signal 1 (LLM) constants
_LLM_WEIGHTS = {
    "Tone": 0.1,
    "Informality": 0.2,
    "Language": 0.2,
    "Stance": 0.2,
    "Progression": 0.3,
}
_MODEL = "llama-3.3-70b-versatile"
_SYS_PMT = """\
You are a content analyzer that scores text on how AI-generated or human-made it appears based on certain criteria. Apply all of the following analysis and scoring guidelines systematically. Do NOT resort to any external guidelines. Each guideline's must be a decimal from 0 to 1 inclusive. Do NOT go outside the range at all.

Guidelines:

1. Tone: How brooding, reflective, deep, or emotional is the text's tone? More brooding, deep, or emotional tone = higher score.
2. Informality: How informal/conversational vs formal/proper is the text? How much slang does it contain? More informality and/or more slang = higher score.
3. Language: How much hedging language does the text use (e.g. "It's worth noting that...", "Despite...", etc.). Less hedging language = higher score.
4. Stance: Is the text subtly or firmly taking a side on a topic? Or is it carefully neutral? More one-sided = higher score.
5. Progression: How clear is the text's progression from a beginning/exposition to an end/resolution? Clearer progression = higher score.

Output format:

Return your scoring exactly in the format specified below. Substitute each category's scores and reasons into the placeholder angle brackets. Do NOT add any extra characters such as formatting symbols (e.g. Markdown or LaTeX symbols) - just plain text as shown below.

Tone: Score: <0-1 score> Reason: <1-sentence reason>
Informality: Score: <0-1 score> Reason: <1-sentence reason>
Language: Score: <0-1 score> Reason: <1-sentence reason>
Stance: Score: <0-1 score> Reason: <1-sentence reason>
Progression: Score: <0-1 score> Reason: <1-sentence reason>"""
_client = Groq(api_key=os.environ["GROQ_API_KEY"])


def detect_llm(content: str) -> float:
    """Signal 1: LLM-based detection. Returns 0-1 score."""
    if len(content) < 100:
        write_log(
            "Signal 1 (LLM): Content too short — returning fallback 0.5",
            {"content": content},
            severity="warning",
        )
        return 0.5

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYS_PMT},
                {"role": "user", "content": f"User Text:\n\n{content}"},
            ],
        )
        text = response.choices[0].message.content
        raw_text = text[:10_000]
        scores = {}

        for i, line in enumerate(text.strip().splitlines(), start=1):
            if not line.strip():
                continue
            match = re.match(r"^(\w+):\s*Score:\s*([0-9.]+)", line, re.IGNORECASE)
            if not match:
                write_log(
                    f"Signal 1 (LLM): Unparsable line {i} — returning fallback 0.5",
                    {"line": line, "raw_text": raw_text},
                    severity="error",
                )
                return 0.5
            category, value = match.group(1).title(), float(match.group(2))
            if category in _LLM_WEIGHTS:
                if not (0.0 <= value <= 1.0):
                    write_log(
                        f"Signal 1 (LLM): Out-of-bound score for {category} ({value}) — clamping",
                        {"category": category, "value": value, "raw_text": raw_text},
                        severity="warning",
                    )
                scores[category] = max(0.0, min(1.0, value))

        if len(scores) != 5:
            write_log(
                f"Signal 1 (LLM): Not enough parsable lines ({len(scores)}/5) — returning fallback 0.5",
                {"scores_found": scores, "raw_text": raw_text},
                severity="error",
            )
            return 0.5

        result = sum(_LLM_WEIGHTS[cat] * scores[cat] for cat in _LLM_WEIGHTS)
        write_log(
            "Signal 1 (LLM): Scored content",
            {"scores": scores, "result": result, "raw_text": raw_text},
        )
        return result

    except Exception as e:
        write_log(
            "Signal 1 (LLM): API call failed — returning fallback 0.5",
            {"error": str(e)},
            severity="error",
        )
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
