# Detection Signal 3: `pos_dist`

- Analyzes the distribution of various part-of-speeches in the content to score AI generation likeliness.
- Quantities measured:
  - **Subjectivity**: AI tries to be objective by tending to use more adjectives than pronouns.
  - **Neutrality**: AI attempts to appear neutral via heavier use of passive language (e.g. "The action was done...").
  - **Extremeness**: AI attempts to temper superlative language with comparative language compared to human writers, who tend to be more extreme and emphatic.
  - **Dynamism**: AI often uses more nouns than verbs to be informative while sacrificing motion.
  - **Complexity**: AI often sticks to compound or complex sentences using compound conjunctions or subordinating conjunctions.

## Input

| Parameter | Type  | Description                        |
| --------- | ----- | ---------------------------------- |
| `content` | `str` | User-submitted content to evaluate |

## Output

A `dict` with keys:

| Key          | Type    | Description                                      |
| ------------ | ------- | ------------------------------------------------ |
| `score`      | `float` | Score reflecting whether content is AI-generated |
| `sub_scores` | `dict`  | Sub-score for each POS analysis category used    |

## Implementation

Use the `textblob` library to perform POS analysis.

### Subjectivity

1. Calculate and return the ratio of pronouns to adjectives in the content, capped to `1.0`.

### Neutrality

1. Get the total number of words in the content.
2. Calculate the count of passive constructions (i.e. modal/auxiliary verb immediately followed by a past participle).
3. Calculate the ratio of passive constructions to total words.
4. Invert the ratio (`1 - ratio`) so that 0 = AI-generated.

### Extremeness

1. Count the number of comparative words in the content.
2. Count the number of superlative words in the content.
3. Calculate and return the ratio of superlative to comparative, capped to `1.0`.

### Dynamism

1. Count the number of verbs in the content.
2. Count the number of nouns in the content.
3. Calculate and return the ratio of verbs to nouns, capped to `1.0`.

### Complexity

1. Count the number of coordinate conjunctions and subordinate conjunctions.
2. Count the number of sentences.
3. Calculate the ratio of conjunctions to sentences.
4. Invert this ratio (`1 - ratio`) so that 0 = AI-generated.

## Scoring

All 5 category sub-scores will be combined via an unweighted average. The combined score will then reflect the following breakdown:

| Range                 | Classification |
| --------------------- | -------------- |
| `0.0 <= score < 0.4`  | Likely AI      |
| `0.4 <= score < 0.6`  | Uncertain      |
| `0.6 <= score <= 1.0` | Likely human   |

## Fallback

If the content is too short (below 100 characters), return `0.5` since no results are meaningful on such little text.
