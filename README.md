# Provenance Guard

## Setup

## Tech Stack

## Architecture

## Detection Signals

- order doesn't matter - all 3 run anyway

## Confidence Scores

## Transparency Labels

## Appeals

## Rate Limiting

## Logging

## Known Limitations

- None of the thresholds chosen empirically
- Metadata was synthesized, but its structure can be generalizable and can plug into a fully fledged frontend text editor
- No auth - simply IDs
- IP-based rate limiting easily evaded via VPN

## Spec Reflection

## AI Usage

- Asked it to create server skeleton with just endpoint stubs - created the whole skeleton including with rate limiting.
- It caught my rate limiting spec oversight for /creators - went with its plan but overrode observability-based-but-unnecessary ip_address column

## Notes

Testing via:

```bash
curl -s -w "\n%{http_code}\n" \
-X POST http://localhost:5000/ENDPOINT \  # set endpoint
-H "Content-Type: application/json" \
-H "Bearer: CREATOR_ID" \                 # set creator ID if needed
-d 'BODY_HERE'                            # set body if needed
```
