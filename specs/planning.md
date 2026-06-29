# Planning

This project involves building the backend of a creative writing platform, complete with multi-signal detection of how likely creator content is AI-generated or human-made - a continuous confidence score that has inherently conveys uncertainty. This confidence score is translated to non-technical labels to help users understand the content's classification. Other features of the backend include data storage for persistence, logging for accountability, and rate limiting for protection.

## Detection Signals

- Each detection outputs a score between 0-1 (each upper bound below except 1.0 is exclusive):
  - 0.0-0.4: Likely AI
  - 0.4-0.6: Uncertain
  - 0.6-1.0: Likely human

Detection-specific details in:

- [`det1-llm.md`](./det1-llm.md)
- [`det2-stylo-heuristics.md`](./det2-stylo-heuristics.md)
- [`det3-pos-dist.md`](./det3-pos-dist.md)

## Confidence Scores

- The 3 detection signal scores will be combined into a single confidence score via weighting.
- Same breakdown for the combined score:

```
  0                          0.4             0.6                         1.0
  |---------------------------|-------|-------|---------------------------|
Likely AI                     +-- Uncertain --+                  Likely human
```

- Weights used to combine the signal scores:

| Signal             | Weight | Reason                                                                               |
| ------------------ | ------ | ------------------------------------------------------------------------------------ |
| `llm`              | 0.40   | Context and semantics are powerful indicators of AI generation                       |
| `stylo_heuristics` | 0.30   | Similar importance to `llm` for covering its major blind spot: structure             |
| `pos_dist`         | 0.30   | Similarly rigid as `stylo_heuristics` - works well for most cases but misses context |

## Labels

- Return a machine-friendly label and non-technical user-friendly label corresponding to the confidence score.
- Classifications, labels, and transparency labels:
  - **Likely AI**: `likely_ai` - "This content appears to be partially or fully AI-generated."
  - **Uncertain**: `uncertain` - "We're not sure whether this content was AI-generated."
  - **Likely human**: `likely_human` - "This content appears human-made." (Different transparency label if provenance certificate is successfully granted.)

## Provenance Certificate

- Creators can apply for a provenance ("verified human") certificate for a particular content if:
  - They express their intent (via the `GET /verified-human-certificate`)
  - They used the first-party in-app editor to write their entire draft
  - They did not paste anything from outside the app while editing the draft
  - They spent reasonably enough time in the editor across a reasonable number of sessions
  - Their content that contains no watermarks
  - Their content passes plagiarism tests
- Advantage:
  - Boosts their confidence score
  - If the resulting score is in the likely-human range, then a special "verified" transparency label that carries more weight than a "likely human" one: "Verified human - this content is most likely human-made."
  - Score boosting function: `1 - (1 - score)^3.25` (0 -> 0, 1 -> 1, low scores boosted more significantly)
- Metadata format with values needed to get certificate (at least 3 sessions of an hour each are required):

  ```json
  {
    "platform": "desktop_app",
    "pastes_from_elsewhere": 0,
    "sessions": [
      {
        "start": "<ISO time stamp>",
        "end": "<ISO time stamp>"
      }
    ]
  }
  ```

- Reasons for the requirements:
  - **First-party in-app editor**: The hypothetical first-party app would have an editor to track info necessary to distinguish human creation (keystrokes, copy-pastes, session lengths, etc.). It would also have deeper permissions than a web app, allowing more secure data collection and lowering the chances of client-side metadata tampering
  - **Copy-pasting**: A true human creation most often doesn't require copy-pasting from outside sources - it should all be organically typed.
  - **Session time and count**: Genuine human creations take a lot of time to make and usually multiple sessions for inspiration to strike and iterate on the draft - much different than the few minutes of AI-generation and proofreading in a single session.
  - **Watermarks**: A hidden watermark that AI can embed into its output text is zero-width Unicode characters - not rendered at all but exist in the raw string, which couldn't be typed naturally let alone when humans write creative works
  - **Plagiarism tests**: Human works are usually original works if the author doesn't consult outside sources, especially AI. One caveat: can't check against private chats.

## Appeals

- Any content creator will be able to appeal to re-evaluate their content for all classifications (i.e. not just falsely labeled as AI-generated)
- Content creators will not be able to submit appeals for content that is already under review
- Need to provide:
  - Particular content in question (frontend would get the corresponding ID)
  - Desired label
  - Reason for appealing and why the desired label should be used instead
- When an appeal is received:
  - Immediately reject if the desired label is invalid or the same as the current label
  - Otherwise, store it in the `appeals` database
  - Update the corresponding content's status to "Under review"
  - Add a log entry for receiving the appeal and changing the content status
- A human reviewer would query the `appeals` database (either directly or via an interface) to chronologically see and handle the appeals

## Rate Limiting

- Rate limiting will count even when requests are rejected for any reason for maximal server protection.
- Per-endpoint rate limiting:

  | Endpoint         | Auth Proxy | Per Min | Per Day | Reason                                                                                            |
  | ---------------- | ---------- | ------- | ------- | ------------------------------------------------------------------------------------------------- |
  | `POST /appeals`  | Creator ID | 3       | 18      | Similar to content limits; some higher headroom for appealing older content                       |
  | `POST /content`  | Creator ID | 3       | 15      | Content requires time to make; low limit is reasonable; some leeway for retrying invalid requests |
  | `POST /creators` | IP address | 1       | 5       | Very low limit since account is ideally created once per person; some leeway for invalid requests |
  | `GET /logs`      | Admin ID   | 10      | 100     | High ceiling for admin use; but not infinite in case of an admin account breach                   |

- Note: `POST /creators` needs to use the IP address for individual rate limiting because the current creator's ID has not been yet. That endpoint itself creates the creator ID used by the rate limiting at the other endpoints.
- One person may have multiple creator accounts, allowing for higher rate limit per person, so it is in the best interest to use creator ID for most endpoints in stead of IP address (which is usually the same for the same person).
- Admin IDs are special creator IDs (all admins are creators).

## Logging

- Logging will be stored in a `logs` database in a JSONL format (unlike SQLite tables for the other databases) to allow nested objects.
- Log entries will be created when:
  - New content is submitted.
  - New appeal request is created.
  - New creator account is created.
  - Any request is rejected for invalid input.
  - Any error or warning conditions occur in request handling and detection pipeline.
  - Logs are accessed.
- Log entries will _not_ be created when:
  - Rate limiting kicks in and rejects a request. This should be stored elsewhere to avoid flooding the logs yet monitoring any potential attacks.

## Databases

- Three databases to store key info:
  - `content`: SQLite database - Stores the actual text content and metadata submitted by users.
  - `creators`: SQLite database - Holds creator info (proxy for account info) for attribution and rate limiting
  - `appeals`: SQLite database - Stores appeal requests submitted by users.
  - `rate_limits`: SQLite database - Stores rate limiting info by creator ID for most endpoints or IP address on the `POST /creators` endpoint in which the creator ID is yet to be created.
  - `logs`: JSONL file - Store log entries of every submission's evaluation and appeal request as they arrive.

### `content` Schema

```json
[
  {
    "content_id": "str - Content ID",
    "creator_id": "str - Creator ID",
    "submitted_at": "str - Timestamp of submission",
    "content": "str - User-submitted content",
    "metadata": "str - JSON string of content metadata",
    "status": "str - One of: submitted, under_review",
    "llm_score": "float - Detection signal 1 (LLM) score",
    "stylo_heuristics_score": "float - Detection signal 2 (Stylometric heuristics) score",
    "pos_dist_score": "float - Detection signal 3 (Part-of-speech distribution) score",
    "confidence_score": "float - Combined score from detection signals",
    "label": "str - One of: likely_ai, uncertain, likely_human",
    "transparency_label": "str - Transparency label based on confidence score or provenance certificate",
    "verified_human": "bool - Whether content has successfully been granted a provenance certificate"
  },
  ...
]
```

**Primary key**: `content_id`

### `creators` Schema

```json
[
  {
    "creator_id": "str - ID of the creator",
    "joined_at": "str - Timestamp of account creation",
    "email": "str - Creator's email address"
  },
  ...
]
```

**Primary key**: `creator_id`

### `appeals` Schema

```json
[
  {
    "appeal_id": "str - ID of the appeal",
    "content_id": "str - Corresponding content ID",
    "appealed_at": "str - Timestamp of appeal submission",
    "desired_label": "str - One of: likely_ai, uncertain, likely_human",
    "reason": "str - User's reason for appealing"
  },
  ...
]
```

**Primary key**: `"appeal_id"`

### `rate_limits` Schema

```json
[
  {
    "identity": "str - Creator ID on most endpoints or IP address on POST /creators endpoint",
    "endpoint": "str - Endpoint on which to rate limit (e.g. `POST /creators`)",
    "window_min": "str - Minute on which minute-based rate limiting applies",
    "window_day": "str - Day on which day-based rate limiting applies",
    "count_min": "str - Endpoint use count in the minute window",
    "count_day": "str - Endpoint use count in the day window"
  },
  ...
]
```

**Primary key**: `"identity"` and `"endpoint"` together

### `logs` Schema

```json
[
  {
    "log_id": "str - ID of the log",
    "message": "str - Message describing the log entry",
    "body": "dict - Corresponding object created, updated, etc."
  },
  ...
]
```

**Primary key**: `log_id`

For example:

```json
[
  {
    "log_id": "168a93e6-54f5-43d3-b3c7-8dce155107cc",
    "message": "Stored new appeal",
    "body": {
      "appeal_id": "bf056077-1608-4225-88af-261108678130",
      "content_id": "e88acb50-fd94-490b-b1cd-1023c9fc1f79",
      "appealed_at": "2026-06-27T11:51:14.997479",
      "desired_label": "likely_human",
      "reason": "Test appeal request"
    }
  },
  ...
]
```

## Endpoints

Info in [`endpoints.md`](./endpoints.md).

## Analytics Dashboard

- Will be built on Gradio UI.
- No rate limiting since it is intended purely for internal use.
- Will contain visualizations and logs:
  - **Visualizations**:
    - Label distribution (human vs AI vs uncertain verdicts)
    - Appeals filed in the past week per hour
    - Uploaded content size (number of characters) in the past week per hour
  - **Logs**: Separate panel displaying all the logs from the database
- Manual refresh button to update the metrics.

## Architecture

### Submission Flow

```
                                POST /content
                                     |
                       Content       |
                 + metadata payload  |
                                     v
       400 response <-----------  Backend  ------------> 429 response
                        Invalid     | |      Surpassed
                         input      | |      rate limit
                                    | |
      ------------------------------- ---------------------------> 401 response
      |                 OK            Unauthorized (no creator ID)
      |
      v
>> (content)                   >> (content)                    >> (content)
Signal 1: llm  ------>  Signal 2: stylo_heuristics  ------>  Signal 3: pos_dist
      |                              |                                |
      |                              |                                |
      --------------->-------------------------------<-----------------
                                     |
                        Individual   |
                      signal scores  |
                                     v
                              Combine scores
                            (weighted average)
                                     |
                                     v
                              Apply certificate
                             if requirements met
                          (boost confidence score)
                                     |
                                     v
                            Transparency label
                                     |
                                     v
                               Store content
                                (content db)
                                     |
                                     v
                              Log submission
                                 (logs db)
                                     |
                                     v
                               201 response
```

### Account Creation Flow

```
    POST /creators
         |
         v
      Backend
         |
         |         Invalid input
         +----------------------------> 400 response
         |
         |  OK
         |
         v
    Store creator
    (creators db)
         |
         v
    Log account
      creation
         |
         v
    201 response
```

### Appeal Flow

```
    POST /appeals
         |
         v
      Backend
         |
         |     Invalid input
         +------------------------> 400 response
         |
         |     Unauthorized (no creator ID)
         +----------------------------------> 401 response
         |
         +---------------------------------------> 429 response
         |     Rate limit surpassed
         |
         |  OK
         |
         v
       Update
    content status
         |
         v
    Store appeal
    (appeals db)
         |
         v
     Log appeal
         |
         v
    201 response
```

### Log Flow

```
    GET /appeals
         |
         v
      Backend
         |
         |     Unauthorized (No admin ID)
         +----------------------------------> 401 response
         |
         +---------------------------------------> 429 response
         |     Rate limit surpassed
         |
         |  OK
         |
         v
     Log access
         |
         v
     Fetch logs
    (logs JSONL)
         |
         v
    200 response
```

### Analytics Dashboard Flow

```
Appeals db          Content db          Logs JSONL
    |                   |                    |
    |                   |                    |
    ---------->---------+----------<----------
                        |
                        |
                        v
               Analytics dashboard
```

## Automated Tests

- Use pytest
- Test endpoints:
  - Input validation for all endpoints and for all invalid inputs listed in [`endpoints.md`](./endpoints.md)
  - Auth for all applicable endpoints
  - Rate limiting for all endpoints
  - Success conditions:
    - `GET /logs`: `tail=n` logs are returned when the log file has that many
    - `POST /appeals`: Appeal is stored in the appeals database and content is marked under review
    - `POST /content`: Content is stored in the content database
    - `POST /creators`: Creator is stored in the creators database
- Test detection signals:
  - All fallback cases (e.g. immediate returns of 0.5) for each detection signal
  - Metadata effect on attaining certificate
  - Special transparency label appears after attaining certificate
  - Clearly human content leads to human transparency label and >=0.6 confidence score

  > "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there"
  - Clearly AI content leads to AI transparency label and <=0.4 confidence score

  > "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment."
  - Ambiguous examples lead to uncertain scores and labels:

  > "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations."

  > "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type."

## Anticipated Edge Cases

- While three detections signals are powerful, careful calibration is required via pre-labeled data.
- The current setup uses reasonable assumptions, which may be vulnerable to edge cases.
- Specific anticipated scenarios where the detection pipeline is wrong:
  - A human-written poem that is intentionally and artistically chosen to use heavy repetition and simple vocabulary may be wrongly classified as AI-generated.
  - A short story generated by AI through careful prompting may use complex vocabulary and sentences of varying lengths, which may be incorrectly classified as human-made.

## AI Tool Plan

**M3 (submission endpoint + first signal)**: I will provide my AI tool my `llm` detection signal section, submission architecture diagram, and submission endpoint design section. I will ask it to generate a Flask app skeleton and the `llm` signal function. I will verify the output by testing with a few inputs directly before wiring into the submission endpoint.

**M4 (second signal + confidence scoring)**: I will provide my AI tools the sections for the rest of the detection signals (`stylo_heuristics` and `pos_dist`) as well as the confidence score section. I will ask it to generate the rest of the signal functions and confidence scoring logic. I will verify the output by testing if scores vary meaningfully between clearly AI and clearly human text via example content - while monitoring the logs to see how weights need to be calibrated to get the desired output.

**M5 (production layer)**: I will provide my AI tool my label section, appeals workflow diagram, and appeals endpoint section. I will ask it to generate label generation logic and implement the appeals endpoint. I will verify the output by testing that all three label variants are reachable and that an appeal updates content status correctly.
