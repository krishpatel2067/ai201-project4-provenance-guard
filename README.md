# Provenance Guard

## Setup

1. Create a virtual environment:

```bash
python -m venv .venv
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables:

```bash
cp .env.example .env
```

Populate `GROQ_API_KEY` to your API key, freely available on [Groq](https://console.groq.com/keys).

4. Create the data directory and necessary files within:

```bash
mkdir data/
touch data/top_1k_common_words.txt
touch data/admin-ids.txt                # optional
```

Populate `data/top_1k_common_words.txt` with the top 1000 most common English words from [this repo file](https://github.com/first20hours/google-10000-english/blob/master/google-10000-english-no-swears.txt) (one per line), and optionally populate `data/admin-ids.txt` with any UUIDs (one per line).

5. Run the server:

```bash
python src/server.py
```

6. (Optional) (Separate terminal) View the analytics dashboard:

```bash
source .venv/bin/activate
gradio src/analytics.py
```

7. (Optional) (Separate terminal) Make test HTTP requests:

```bash
source .venv/bin/activate
curl -s -X POST http://localhost:5000/creators \        # default port 5000 - change if needed
-H "Content-Type: application/json" \
-d '{"email": "test@gmail.com"}'
```

8. (Optional) (Separate terminal) Run test SQLite queries on a specific database:

```bash
source .venv/bin/activate
python tests/manual_query.py data/content.db
```

Enter any SQLite query on the tables, such as:

```
SQL> SELECT * FROM content;
```

## Tech Stack

| Component                        | Technology                |
| -------------------------------- | ------------------------- |
| Signal 1 (LLM)                   | `llama-3.3-70b-versatile` |
| Signal 2 (sylometric-heuristics) | Vanilla Python            |
| Signal 3 (POS distribution)      | TextBlob/NLTK             |
| Backend server                   | Flask                     |
| User data storage                | SQLite                    |
| Rate limiting                    | SQLite, vanilla Python    |
| Logging                          | JSONL file                |
| Analytics dashboard              | Gradio, Pandas            |

## Project Structure

```
    specs/
        det1-llm.md                 # Detection signal 1 (LLM) specs
        det2-stylo-heuristics.md    # Detection signal 2 (stylometric heuristics) specs
        det3-pos-dist.md            # Detection signal 3 (POS distribution) specs
        endpoints.md                # Endpoint request and response specs
        planning.md                 # Overall project specs
        rough-planning.md           # Rudimentary planning
    src/
        routes/
            appeals.py                  # Endpoint handler for creating appeals
            content.py                  # Endpoint handler for creating content
            creators.py                 # Endpoint handler for creating creator account
            logs.py                     # Endpoint handler for accessing logs
        analytics.py                # Analytics dashboard creation
        auth.py                     # Authentication manager
        cert.py                     # Provenance certificate manager
        db.py                       # Database initialization manager
        detection.py                # Detection signal implementations
        log.py                      # Log manager
        rate_limit.py               # Rate limit manager
        server.py                   # Main server script
    tests/
        conftest.py                 # Common fixtures and mocks
        manual_query.py             # Manual SQLite query input via terminal
        test_auth.py                # Authentication tests
        test_detection.py           # Detection signal tests
        test_endpoints.py           # Successful endpoint response tests
        test_rate_limit.py          # Rate limit tests
        test_validation.py          # Endpoint input validation tests
    requirements.txt            # Project dependencies
```

## Confidence Scores

A single continuous scale from 0-1 that classifies content as AI-generated or human-written and conveys uncertainty. The following breakdown is used to map a range of scores to labels:

```
  0                          0.4             0.6                         1.0
  |---------------------------|-------|-------|---------------------------|
Likely AI                     +-- Uncertain --+                  Likely human
```

A score within the 0.4-0.6 range is too uncertain to be clearly classified as AI or human.

It is much simpler to use one number of represent certainty of both labels than use two scores with their own certainties. The latter case raises interesting and difficult questions such as: what does it mean for both scores to be at their maximums at the same time as opposed to at their minimums at the same time? Thus, a single continuous scale is simple yet informative enough.

## Detection Signals

The pipeline is composed of 3 detection signals. A multi-signal detector is much more powerful and accurate than any single-signal detector. This is because each has unique strengths that can be combined to cover the weaknesses:

| Signal                 | Strengths                                                   | Weaknesses                                            |
| ---------------------- | ----------------------------------------------------------- | ----------------------------------------------------- |
| LLM                    | Understands context and holistic composition                | Misses hidden statistical and structural properties   |
| Stylometric heuristics | Uses key structural differentiators like length variance    | Rigid and mechanical; misses context and composition  |
| POS distribution       | Analyzes part-of-speech use to establish unique fingerprint | Rigid and mechanical ; misses context and composition |

Each signal is further composed of sub-categories, whose scores are averaged together. Each sub-category's significance is based on reasonable assumptions about human and AI text. LLM and stylometric heuristics uses weighted averages to compute their signal-final scores, which are also built on reasonable assumptions. That is fine for a learning project, but in production, data collection and annotation are needed to test these assumptions.

### LLM

| Sub-Category | Significance                                                                                                         |
| ------------ | -------------------------------------------------------------------------------------------------------------------- |
| Tone         | AI tends to use a flatter tone whereas humans explore many different tones from emotional to deep and brooding.      |
| Informality  | AI tends to use semi-formal words and avoid conversational language that human writers may use.                      |
| Language     | AI tends to use hedging language more often to temper its output whereas human writers are more direct and emphatic. |
| Stance       | AI tends to stay neutral with most topics whereas human writers often pick sides and try to persuade the audience.   |
| Progression  | AI tends to produce stagnant plots or narratives whereas human writers create more dynamic content.                  |

| Category    | Weight | Reason                                                                                        |
| ----------- | ------ | --------------------------------------------------------------------------------------------- |
| Tone        | 0.1    | Low weight because tone can vary greatly from work to work.                                   |
| Informality | 0.2    | Medium weight because human-written content tends to be more informal though not always.      |
| Language    | 0.2    | Medium weight because a carefully reasonable human author can also use hedging language.      |
| Stance      | 0.2    | Medium weight because a human author can also choose to be neutral.                           |
| Progression | 0.3    | High weight because human works progress clearly, and this is a very subtle property to fake. |

### Stylometric Heuristics

| Sub-Category             | Significance                                                                                           |
| ------------------------ | ------------------------------------------------------------------------------------------------------ |
| Paragraph size diversity | AI tends to use more uniformly-sized paragraphs than humans.                                           |
| Vocabulary diversity     | AI tends to use tends to repeat words more often than human writers.                                   |
| Punctuation diversity    | AI tends to overuse certain punctuation (e.g. hyphens and exclamation points) while underusing others. |
| Sentence length variance | AI tends to use more evenly-sized sentences than human writers, who are usually more varied.           |
| Common-word ratio        | AI tends to stick to the most common words while humans may wander to rare words.                      |

| Category                 | Weight | Reason                                                                                                                   |
| ------------------------ | ------ | ------------------------------------------------------------------------------------------------------------------------ |
| Paragraph size diversity | 0.1    | Low weight because humans work may (coincidentally or intentionally) write evenly sized paragraphs.                      |
| Vocabulary diversity     | 0.1    | Low weight because non-native English authors may be less accustomed to synonyms to boost vocabulary diversity.          |
| Punctuation diversity    | 0.2    | Medium weight because punctuation use depends on text genre and author's style.                                          |
| Sentence length variance | 0.3    | High weight because human works don't consciously focus on sentence size (some even stylistically use run-on sentences). |
| Common-word ratio        | 0.3    | High weight because human authors' personal linguistic background often leads to less frequent words being used.         |

### Part-of-Speech Distribution

| Sub-Category | Significance                                                                                                                  |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| Subjectivity | AI tries to be objective by tending to use more adjectives than pronouns.                                                     |
| Neutrality   | AI attempts to appear neutral via heavier use of passive language (e.g. "The action was done...").                            |
| Extremeness  | AI tries to temper superlative language with comparative language compared to human writers, who can be extreme and emphatic. |
| Dynamism     | AI often uses more nouns than verbs to be informative while sacrificing motion.                                               |
| Complexity   | AI often sticks to compound or complex sentences using compound conjunctions or subordinating conjunctions.                   |

All categories are of equal weight because all are just as important to building each content's unique fingerprint to classify as AI- or human-originated.

## Transparency Labels

Each classification label also maps to a longer label that non-technical users can understand. In a complete full-stack application, these labels would be displayed next to the content for users to provide transparency about AI use to content consumers - hence the name "transparency label."

| Short Label                     | Transparency Label                                            |
| ------------------------------- | ------------------------------------------------------------- |
| `likely_ai`                     | "This content appears to be partially or fully AI-generated." |
| `uncertain`                     | "We're not sure whether this content was AI-generated."       |
| `likely_human` (no certificate) | "This content appears human-made."                            |
| `likely_human` (certificate)    | "Verified human - this content is most likely human-made."    |

Provenance certificates lead their own transparency labels and are discussed below.

## Metadata and Provenance Certificate

Creators may apply for a provenance ("verified human") certificate for each content they upload. The pipeline uses metadata about the content to determine certificate eligibility. Specifically, the metadata must show that they:

- Used the first-party in-app editor to write their entire draft (no web app). Web apps don't have deep permissions that full desktop apps have to collect further metadata data such device ID.
- Did not paste anything from outside the app while editing the draft. AI-generated text is often copy-pasted from the chat window to the sharing platform.
- Spent reasonably enough time in the editor across a reasonable number of sessions. Human works take time to make often split across multiple sessions.

The backend scans the metadata to see if these 3 requirements are satisfied. Since this is a learning project, the metadata is simply generated or hard-coded - not actually collected. That would require advanced frontend scripting, which is outside the scope of this project.

Nonetheless, the idea is effective: if someone writes their entire work in the in-app editor without pasting anything in, that editor can be programmed to store all the keystrokes, sessions, revision history, and much more as evidence that the work was truly human-created. Technically, webcam data (i.e. the author actually sat at their computer to write the work) strengthens the evidence much more, but it has its own set of issues like privacy and video processing. Thus, text metadata strikes a balance between verifiability and processing overhead. (However, as with most client-inbound payloads, metadata, too, can be tampered with, leading to false certificates being awarded. But again, for a learning project, this is a good starting point.)

If the 3 metadata requirements are satisfied, the content receives a provenance certificate. This means that its classification score gets boosted asymmetrically (so that low AI-tending scores are boosted more than high human-tending ones). However, to receive the special transparency label listed in the [section above](#transparency-labels), the boosted score must still fall in the "likely human" range. This is a low bar to clear, but it does help reduce the chances of falsely granting certificates: if the detector gave an egregiously low AI-tending score, then perhaps that content is truly not fit to be called "verified human" even with the necessary metadata. In this case, waiting for a creator appeal and investigating further is a better alternative.

## Appeals

A fully deployed content-sharing application often have ways for creators to appeal their content being marked a certain way, taken down, etc. - and this project is no different. Appeal functionality exists not just due to imperfect labeling (though that is very true for this detector pipeline) but also to grant creators the right to explain themselves.

In this project, any creator can file an appeal for any of their _own_ content being misclassified. All the appeal needs is

- the content ID (the frontend translates their intention for them),
- desired label (which must be different from the current label), and
- reasoning (non-empty but also capped to a character limit to avoid storage issues).

Due to this being a learning project, appeals simply get stored to the database and the respective content marked as "under review." In a deployed application, there would often be a separate pipeline and human team to manage, approve, or deny appeals.

## Rate Limiting and Authentication

Most backends use rate limiting to ensure only authenticated application users get their fair share of requests to the backend. Otherwise, any bad actor can spam backend with requests, hogging resources and potentially crashing servers. This project defends all of its endpoints via a custom rate limiting system built on a rudimentary authentication proxy.

| Endpoint         | Auth Proxy | Per Min | Per Day | Reason                                                                                                 |
| ---------------- | ---------- | ------- | ------- | ------------------------------------------------------------------------------------------------------ |
| `POST /appeals`  | Creator ID | 3       | 18      | Similar to content limits; more headroom for appealing older content.                                  |
| `POST /content`  | Creator ID | 3       | 15      | Content requires time to make; low limit is reasonable; some leeway for retrying after errors.         |
| `POST /creators` | IP address | 1       | 5       | Very low limit since account is ideally created once per person; some leeway for retires after errors. |
| `GET /logs`      | Admin ID   | 10      | 100     | High ceiling for admin use; but not infinite in case of an admin account breach.                       |

Admin IDs are simply special creator IDs that have elevated privileges (namely exclusive access to the `GET /logs` endpoint). Thus any endpoint that accepts creator ID also, by definition, accepts admin IDs. Notice that `POST /creators` cannot use creator ID (or admin ID) because that is the "sign-up" endpoint to attain the creator ID in the first place. Thus, IP address is used, which is not foolproof (a VPN can easily bypass IP-based rate limiting) but works for this project.

## Logging

Logging is essential to monitor system health, catch bugs, and ensure accountability. This project uses structured JSONL logging that appends entries when:

- New content is submitted.
- New appeal request is created.
- New creator account is created.
- Any request is rejected for invalid input.
- Any error or warning conditions occur in request handling and detection pipeline.
- Logs are accessed.

(Rate limiting rejecting requests is not logged due to clutter, but would offer value by allowing cybersecurity experts to monitor any potential denial-of-service attacks.)

Each log entry stores:

- A unique log ID.
- A short human-readable message of the event logged.
- A severity tag that allows warnings and errors to be easily detected.
- A body that contains structured info about the resource created, changed, etc.

The following are example log entries for content submission, appeal submission, and creator account creation.

### Content

```json
{
  "log_id": "62466ef6-867a-45cf-abea-a34d99fb23ec",
  "message": "Stored new content submission",
  "severity": "info",
  "body": {
    "content_id": "fb849f9b-44f0-43e7-8c67-7684c851a5b0",
    "creator_id": "33188e7b-d051-4ed2-ba9e-41690638c9c9",
    "submitted_at": "2026-06-28T22:02:56.158765+00:00",
    "status": "submitted",
    "confidence_score": 0.5,
    "label": "uncertain",
    "transparency_label": "We're not sure whether this content was AI-generated.",
    "verified_human": false
  }
}
```

### Appeals

```json
{
  "log_id": "ed5e744d-6179-4732-b665-994b8e1a6213",
  "message": "Stored new appeal",
  "severity": "info",
  "body": {
    "appeal_id": "8027f8f9-8f2f-4191-94ad-bc49ff05c1d4",
    "content_id": "0afd445a-7cf9-4670-9f0d-580b7e2dd525",
    "appealed_at": "2026-06-28T22:25:08.020214+00:00",
    "desired_label": "likely_human",
    "reason": "a"
  }
}
```

```json
{
  "log_id": "33b5e513-0d30-448a-8616-4764c362752f",
  "message": "Updated content status to under_review",
  "severity": "info",
  "body": { "content_id": "0afd445a-7cf9-4670-9f0d-580b7e2dd525" }
}
```

### Creators

```json
{
  "log_id": "43b37b1e-05f2-4c02-add2-cd760a9aeb41",
  "message": "Created new creator account",
  "severity": "info",
  "body": {
    "creator_id": "7319d79b-a3e3-4385-8fdd-28826f9a9710",
    "joined_at": "2026-06-28T21:50:42.329710+00:00",
    "email": "test2@gmail.com"
  }
}
```

## Analytics Dashboard

The project also contains a simple analytics dashboard built on Gradio UI that shows

- Visualization of label distribution (human vs AI vs uncertain verdicts).
- A graph of appeals filed in the past week per hour.
- A graph of uploaded content size (number of characters) in the past week per hour.
- A panel showing the all the logs.

Such a dashboard would be reserved for just internal use to monitor the system and identify any issues (e.g. rapidly increasing content upload sizes, potentially requiring an expanded storage infrastructure).

## Known Limitations

This is a learning project focused on building fundamentals without tuning any feature to production-grade perfection. Thus, there are known limitations:

- None of the categories or weights in the detection pipeline were chosen empirically. Rather, they were derived through reasoned assumptions. Thus, the accuracy of the multi-signal detector is fairly low, outputting "uncertain" more often than the other two certain labels. Some fixes include performing experiments to see which weights work the best against labeled data and fine-tuning the weights further via real-world data collected and annotated (like in the [TakeMeter](https://github.com/krishpatel2067/ai201-project3-takemeter) project).
- Metadata is synthesized. However, its principles are generalizable to production environments, and its structure can plug into a fully fledged frontend text editor and metadata collector.
- Authentication is simulated. Only creator/admin IDs or IP addresses are used without any passwords, auth tokens, etc. found in real authentication. Nonetheless, the intent is clear, and the structured mirrors real APIs (e.g. a "Bearer" header).
- IP-based rate limiting can be easily bypassed via a VPN. Additional checks would be needed for non-auth endpoints (perhaps another multi-signal detector to determine if requests are genuine).

## Spec Reflection

- In this project, I wrote the spec entirely by myself with some planning assistance from AI for the detection signals, which I was unfamiliar with. This project is the most in-depth I have been with specs before writing any code. Compartmentalizing the specs into logical chunks (via sections and files) helped even more by allowing me to reveal to AI only the specs necessary for the current implementation step. This helped keep the AI tool in focus and reduced token usage by restricting it a subset of the specs at a time.
- There are a few ways I diverged from the specs. One prominent example is with the metadata used to grant a provenance certificate. I originally planned to have more requirements such as no watermarks and passed plagiarism test. The watermark requirement simply required scanning the text for potential zero-width Unicode characters that may be intentionally embedded in AI-generated output, but the plagiarism test would have just been a simple boolean standing in for the results of another part of the backend of the hypothetical complete application. However, I chose not to implement this due to time.

## AI Usage

I used Claude Code for most of the implementation and some planning. I also used GitHub Copilot for the [`tests/manual_query.py`](./tests/manual_query.py) code and basic syntax and API questions.

- At the very start of implementation after I wrote all the specs, I asked the AI tool to create skeleton code in the main Flask [`src/server.py`](./src/server.py) script. I expected it to just create the necessary Flask boilerplate and stubs for the endpoints and detector functions. However, I forgot to mention this strict requirement, and the AI tool went ahead and generated code for endpoint handling and rate limiting all in one fell-swoop. Of course, I reviewed the whole code, and it was sound, but this was a case in point for a more specific prompt to emphasize my preferred style (step-by-step) to the AI tool. I did not override much except modularize the code into multiple files since I felt that the main server script should have minimal code: the necessary boilerplate plus wiring handlers to routes.
- Right before the rate limiting implementation, the AI tool caught my spec oversight for the `POST /creators` endpoint: I had dictated the same creator-ID-based rate limiting as the other endpoints - but this endpoint it self creates the creator ID! I changed my spec manually and re-prompted it with the updated info. This validates my practice of asking the AI tool to confirm its understanding and ask questions if the specs leave a gap, which can help surface such spec oversights.
- During the rate limiting implementation, the AI tool chose to store the IP address in its own column in the rate limiting SQLite database even though it gets stored in the identity column as well. This also required special handling in the code. The AI tool cited observability as the reason, which I understood, but I felt that the column was unnecessary for this project since I wouldn't be making advanced queries with the databases anyway. I wanted to keep the database and code lean, so I asked the AI tool to remove the IP address column.
