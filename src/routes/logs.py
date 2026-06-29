from flask import Blueprint, request, jsonify

from auth import require_auth
from rate_limit import rate_limit
from log import write_log, read_logs

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/logs", methods=["GET"])
@require_auth(admin=True)
@rate_limit("GET /logs")
def get_logs(bearer: str):
    try:
        tail = int(request.args.get("tail", 5))
    except ValueError:
        return jsonify({"message": "Invalid 'tail' parameter: must be an integer"}), 400

    tail = max(1, min(tail, 100))

    write_log("Logs accessed", {"admin_id": bearer, "tail": tail})
    entries = read_logs(tail)
    return jsonify(entries), 200
