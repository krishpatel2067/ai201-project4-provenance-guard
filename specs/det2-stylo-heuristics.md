# Detection Signal 2: `stylo_heuristics`

- Calculates basic structural statistics about the content to establish a unique fingerprint and score AI generation likeliness.
- Quantities to measure:
  - **Paragraph size diversity**: AI tends to use more uniformly-sized paragraphs than humans.
  - **Vocabulary diversity**: AI tends to use tends to repeat words more often than human writers.
  - **Punctuation diversity**: AI tends to overuse certain punctuation (e.g. hyphens and exclamation points) while underusing others.
  - **Sentence length variance**: AI tends to use more evenly-sized sentences than human writers.
  - **Common-word ratio**: AI tends to stick to the most common words.

## Input

| Parameter | Type  | Description                        |
| --------- | ----- | ---------------------------------- |
| `content` | `str` | User-submitted content to evaluate |

## Output

| Return Value | Type    | Description                                      |
| ------------ | ------- | ------------------------------------------------ |
| `score`      | `float` | Score reflecting whether content is AI-generated |

## Implementation

### Paragraph Size Diversity and Sentence Length Variance

1. Split text via respective delimiter (e.g. newlines for paragraphs). Discard empty chunks.
2. Calculate Gini coefficient (already between 0-1).

### Vocabulary Diversity and Punctuation Diversity

1. Generate a frequency map of the respective tokens (e.g. words for vocab).
2. Calculate the Shannon entropy.
3. Normalize the entropy by dividing by `log(N)`.

### Common-Word Ratio

1. Download a top-n list from online.
2. Read the list file.
3. Count the ratio of words in the text that appear in the top-n list chosen to those that don't appear in the list.

## Scoring

Each of the 5 sub-scores will be combined into a single score for this detection signal via a weighted average dictated by the following category-based weights:

| Category                 | Weight | Reason                                                                                         |
| ------------------------ | ------ | ---------------------------------------------------------------------------------------------- |
| Paragraph size diversity | 0.1    | AI tends to use uniformly-sized paragraphs; but human work may coincidentally be like that too |
| Vocabulary diversity     | 0.1    | AI tends to use limited vocabulary; but non-native English authors may do so too               |
| Punctuation diversity    | 0.2    | AI tends to use less varied punctuation; though so can texts like poems                        |
| Sentence length variance | 0.3    | AI uses uniformly-sized sentences; may fail on intentionally-sized sentences                   |
| Common-word ratio        | 0.3    | AI primarily uses the most common words; rare edge case: an archaic or formal work             |

The combined score will then reflect the following breakdown:

| Range                 | Classification |
| --------------------- | -------------- |
| `0.0 <= score < 0.4`  | Likely AI      |
| `0.4 <= score < 0.6`  | Uncertain      |
| `0.6 <= score <= 1.0` | Likely human   |

<!-- TODO: update to Error Handling -->

## Fallback

If the content is too short (below 100 characters), return `0.5` for maximum uncertainty since stylometric results aren't too meaningful.
