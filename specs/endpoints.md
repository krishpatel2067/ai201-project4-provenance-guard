# Endpoints

## `GET /logs`

### Query Params

- `tail` - Default 5. Range 1-100. How many latest logs to return.

### Header Schema

```json
{
  "Bearer": "str - An admin ID (simulates auth) for log viewing permissions"
}
```

### Response Schema

#### 200: OK

Response will contain 5 log entries.

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

#### 400: Bad Request

```json
{
  "message": "str - Error message"
}
```

Invalid inputs:

- Non-integer for query param `tail`

#### 401: Unauthorized

If the admin ID is missing from the header or invalid.

```json
{
  "message": "str - Error message"
}
```

#### 429: Too Many Requests

```json
{
  "message": "str - Error message"
}
```

## `POST /appeals`

### Header Schema

```json
{
  "Bearer": "str - The creator ID (simulates auth) for attribution and rate limiting"
}
```

### Body Schema

```json
{
  "content_id": "str - Corresponding content ID",
  "desired_label": "str - One of: likely_ai, uncertain, likely_human",
  "reason": "str - User's reason for appealing"
}
```

### Response Schema

#### 201: Created

```json
{
  "appeal_id": "str - ID of the appeal",
  "content_id": "str - Corresponding content ID",
  "appealed_at": "str - Timestamp of appeal submission",
  "desired_label": "str - One of: likely_ai, uncertain, likely_human",
  "reason": "str - Preview of user's reason for appealing (first 250 characters)"
}
```

#### 400: Bad Request

```json
{
  "message": "str - Error message"
}
```

Invalid inputs:

- Missing required fields
- Content of given ID not found
- Content of given ID is not the creator's
- Invalid desired label
- Desired label matches current label
- Reason is empty
- Reason too long (more than 2500 characters)

#### 401: Unauthorized

When creator ID is missing from the header or invalid.

```json
{
  "message": "str - Error message"
}
```

#### 429: Too Many Requests

```json
{
  "message": "str - Error message"
}
```

## `POST /content`

### Header Schema

```json
{
  "Bearer": "str - The creator ID (simulates auth) for attribution and rate limiting"
}
```

### Body Schema

```json
{
  "content": "str - User's actual creative content",
  "metadata": "dict - Metadata collected about the content and its creation"
}
```

### Response Schema

#### 201: Created

```json
{
  "content_id": "str - ID of the content",
  "submitted_at": "str - Timestamp of submission",
  "content": "str - Preview of user-submitted content (first 1000 characters)",
  "status": "str - One of: submitted, under_review",
  "confidence_score": "float - Combined score from detection signals",
  "label": "str - One of: likely_ai, uncertain, likely_human",
  "transparency_label": "str - Transparency label based on confidence score or provenance certificate",
  "verified_human": "bool - Whether content has successfully been granted a provenance certificate",
  "message": "str - Success message"
}
```

#### 400: Bad Request

```json
{
  "message": "str - Error message"
}
```

Invalid inputs:

- Missing required fields
- Content too long (over 100,000 characters)

#### 401: Unauthorized

When creator ID is missing from the header or invalid.

```json
{
  "message": "str - Error message"
}
```

#### 429: Too Many Requests

```json
{
  "message": "str - Error message"
}
```

## `POST /creators`

### Body Schema

```json
{
  "email": "str - Creator's email address"
}
```

### Response Schema

#### 201: Created

```json
{
  "creator_id": "str - ID of the creator",
  "joined_at": "str - Timestamp of account creation",
  "email": "str - Creator's email address"
}
```

#### 400: Bad Request

```json
{
  "message": "str - Error message"
}
```

Invalid inputs:

- Missing required fields
- Invalid format for email address
- Email address already exists

#### 429: Too Many Requests

```json
{
  "message": "str - Error message"
}
```
