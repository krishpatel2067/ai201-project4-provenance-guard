import uuid
import json
import os

_LOGS_FILE = "data/logs.jsonl"
_CHUNK_SIZE = 8192


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


def read_logs(tail: int) -> list[dict]:
    """
    Returns the last `tail` log entries by reading the file from the end in
    chunks, avoiding loading the entire file into memory.
    """
    try:
        file_size = os.path.getsize(_LOGS_FILE)
    except FileNotFoundError:
        return []

    if file_size == 0:
        return []

    lines = []
    with open(_LOGS_FILE, "rb") as f:
        pos = file_size
        remainder = b""
        while pos > 0 and len(lines) <= tail:
            chunk_size = min(_CHUNK_SIZE, pos)
            pos -= chunk_size
            f.seek(pos)
            chunk = f.read(chunk_size) + remainder
            parts = chunk.split(b"\n")
            remainder = parts[0]
            lines = parts[1:] + lines

        if remainder:
            lines = [remainder] + lines

    raw = [line for line in lines if line.strip()]
    last_n = raw[-tail:]
    return [json.loads(line) for line in last_n]
