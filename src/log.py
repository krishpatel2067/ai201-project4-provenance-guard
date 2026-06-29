import uuid
import json

_LOGS_FILE = "data/logs.jsonl"


def init_log_file():
    open(_LOGS_FILE, "a").close()


def write_log(message: str, body: dict):
    entry = {
        "log_id": str(uuid.uuid4()),
        "message": message,
        "body": body,
    }
    with open(_LOGS_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
