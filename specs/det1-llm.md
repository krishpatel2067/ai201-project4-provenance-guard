# Detection Signal 1: `llm`

- Uses the Groq LLM analyze the content's composition to score the content to determine whether it's AI-generated.
- Qualities to measure:
  - **Tone**: AI tends to use a flatter tone whereas humans explore many different tones from emotional to deep and brooding.
  - **Informality**: AI tends to use semi-formal words and avoid conversational language that human writers may use.
  - **Language**: AI tends to use hedging language more often to temper its output whereas human writers are more direct and emphatic.
  - **Stance**: AI tends to stay neutral with most topics whereas human writers often pick sides and try to persuade the audience.
  - **Progression**: AI tends to produce stagnant plots or narratives whereas human writers create more dynamic content.
- The LLM will be prompted to assign scores to each of these characteristics and return a strictly formatted output.

## Input

| Parameter | Type  | Description                        |
| --------- | ----- | ---------------------------------- |
| `content` | `str` | User-submitted content to evaluate |

## Output

| Return Value | Type    | Description                                      |
| ------------ | ------- | ------------------------------------------------ |
| `score`      | `float` | Score reflecting whether content is AI-generated |

## System Prompt

```
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
Progression: Score: <0-1 score> Reason: <1-sentence reason>
```

## Scoring

Each of the 5 sub-scores will be combined into a single score for this detection signal via a weighted average dictated by the following category-based weights:

| Category    | Weight | Reason                                                                           |
| ----------- | ------ | -------------------------------------------------------------------------------- |
| Tone        | 0.1    | Tone can vary from work to work; not as clear of an indicator                    |
| Informality | 0.2    | Human-written content tends to be more informal but depends on personal style    |
| Language    | 0.2    | AI uses more hedging language but so can a carefully reasonable human author     |
| Stance      | 0.2    | AI tends to be more balanced but same can apply to any neutral author            |
| Progression | 0.3    | Human works progress clearly; more subtle to fake; more reliable of an indicator |

The combined score will then reflect the following breakdown:

| Range                 | Classification |
| --------------------- | -------------- |
| `0.0 <= score < 0.4`  | Likely AI      |
| `0.4 <= score < 0.6`  | Uncertain      |
| `0.6 <= score <= 1.0` | Likely human   |

## Logging

The signal will log:

- All the sub-scores along with the LLM-provided reason
- Any error, warning, and success conditions

## Error Handling

Log all error/warning conditions along with raw LLM output (if applicable) for visibility. Immediately return 0.5 as fallback to convey maximum uncertainty in a failed detection:

| Condition                                 | Severity | Action          | Reason                                         |
| ----------------------------------------- | -------- | --------------- | ---------------------------------------------- |
| Content too short (<100 chars)            | Warning  | Fall back       | Not meaningful to analyze overly short content |
| Failed LLM API call                       | Error    | Fall back       | No analysis; return max uncertainty            |
| Unparsable line; too few parsable line(s) | Error    | Fall back       | Partial results not reliable                   |
| Out of bounds line(s)                     | Warning  | Clamp; continue | LLM intention clear so clamping is safe        |
