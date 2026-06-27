# Rough Planning

## Architecture Narrative

Content workflow:

1. User submits their textual work (e.g. story, poem, etc.).
2. Contact backend at `POST /submit` with textual work as payload.
3. Check rate limit. If exceeded, return `429`.
4. Otherwise, store textual work and generate content ID.
5. Run detection pipeline.
6. Combine individual scores into combined confidence score.
7. Select appropriate transparency label.
8. Log payload, scores, transparency label.
9. Return `200` response with stored payload, confidence score, and transparency label.

Appeal workflow:

1. User appeals labeling decision for a particular content.
2. Accept `POST /appeals` request at backend.
3. Check rate limit. If exceeded, return `429`.
4. Otherwise, mark content with given ID "under review".
5. Log appeal interaction, especially "under review" status.
6. Return `200` response with content and "under review" status.

Log workflow:

1. Accept `GET /log` request at backend.
2. Check rate limit. If exceeded, return `429`.
3. Otherwise, return `200` response and a certain number of latest logs.

## Detection Signals

### 1. LLM

Use Groq to identify if a piece of text is AI-generated.

**Property**: Contextual and semantic composition. There are multiple ways to identify AI-generated text:

- Assistant-like language (e.g. "If you want, I can help you...", follow-up questions at the end) - oversight; clear giveaway
- Sycophantic tone
- Stagnant progression of ideas
- Lack of informal/conversational language
- Hedging language (e.g. "It is worth noting that...")
- Balanced, neutral portrayal of a topic
- Clear conclusion or takeaway at the end

**Blind spot**: Often misses inherent statistical qualities such as punctuation density, unvaried writing, etc. unless visibly obvious.

### 2. Stylometric Heuristics

**Property**: A writing's structural fingerprint. AI-generated text tends to use:

- Tighter vocabulary (type-token ratio/lexical diversity)
- Less varied sentence lengths
- Less punctuation diversity
- Common words more often
- More heading and bullet point use
- More evenly-sized paragraphs
- More exclamation points, emojis, etc.

**Blind spot**: Completely misses context and semantics. A poem intentionally chosen to sound robotic for artistic purposes will be incorrectly flagged as AI-generated.

### 3. Part-Of-Speech Distribution

**Property**: AI work tends to use certain parts-of-speech more than others, leading to distinct, telltale ratios. Specifically, AI content is often:

- More objective and descriptive, less personal (higher adjective-to-pronoun ratio)
- More neutral, less direct (higher passive construction percentage)
- More informative, less dynamic (higher noun-to-verb ratio)
- More tempered (higher comparative-to-superlative ratio)
- More formally structured (higher use of coordinating and subordinating conjunctions)

**Blind spot**: Completely misses context. Plus, some authors may naturally write in a way that this signal classifies as AI-generated.

## Confidence Scores and Transparency Labels

- Each detection signal returns its own score, which is combined via weighting.
- Final score: between 0-1:
  - 0.0-0.4: Likely AI
  - 0.4-0.6: Uncertain
  - 0.6-1.0: Likely human
- Besides the middle band, the continuity of the confidence score reflects certainty: the closer to 0 or 1 it is, the more certain.
- Each classification will get a non-technical transparency label - something like:
  - "This content appears to be partially or fully AI-generated."
  - "We're not sure whether this content was AI-generated."
  - "This content appears human-made."

## Appeals

- False positives (flagging truly human works as AI-generated) can damage artist reputation and trust in the detection system. Thus, an easy-to-use appeals system is beneficial to creators and consumers.
- Creators may appeal their wrongly labeled content on the frontend (for any one of the three labels for symmetry). The backend receives this request and marks the content under review.

## Flows

Submission flow:

```
POST /content
   |
   |    Content, metadata payload
   v
Backend
   |
   |    Content
   v
Signal 1: LLM
   |
   v
Signal 2: Stylometric heuristics
   |
   v
Signal 3: POS distribution
   |
   |    All signal scores
   v
Confidence scoring
   |
   |    Combined confidence score
   v
Transparency label
   |
   |    Content preview, metadata, scores, classification, transparency label,
   |    status
   v
Audit log
   |
   |    Content, status, score, classification, transparency label payload
   v
Response
```

Appeal flow:

```
POST /appeals
   |
   |    Content ID, creator ID, desired label, reason payload
   v
Backend
   |
   |    Content ID, creator ID
   v
Status update
   |
   |    IDs, updated status, desired label, reason
   v
Audit log
   |
   |    IDs, updated status
   v
Response
```
