import uuid
import json

_LOGS_FILE = "data/logs.jsonl"


def init_log_file():
    open(_LOGS_FILE, "a").close()


def write_log(message: str, body: dict, severity: str = "info"):
    """
    Appends a log to the log file. Severity is one of "info", "warning", or
    "error".
    """
    entry = {
        "log_id": str(uuid.uuid4()),
        "severity": severity,
        "message": message,
        "body": body,
    }
    with open(_LOGS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_logs(tail: int = 0) -> list[dict]:
    """
    Returns log entries in chronological order (oldest first). If `tail` is 0,
    returns all entries; otherwise returns the last `tail` entries.
    """
    try:
        with open(_LOGS_FILE, "r") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
    except FileNotFoundError:
        return []

    entries = [json.loads(l) for l in lines]
    return entries[-tail:] if tail > 0 else entries
