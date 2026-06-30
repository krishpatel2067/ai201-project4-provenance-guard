"""
Success condition tests — one per endpoint, verifying the response shape and
that the expected side effects (DB writes, status changes) actually occurred.

Rate limiting is bypassed so these tests focus purely on endpoint behavior.
"""

import pytest
import db
import log
from conftest import TEST_ADMIN_ID


@pytest.fixture(autouse=True)
def bypass_rate_limit(monkeypatch):
    import rate_limit

    monkeypatch.setattr(rate_limit, "_check_rate_limit", lambda *_: (True, ""))


# ---------------------------------------------------------------------------
# POST /creators
# ---------------------------------------------------------------------------


def test_create_creator_success(client):
    resp = client.post("/creators", json={"email": "new@example.com"})

    assert resp.status_code == 201
    data = resp.get_json()
    assert "creator_id" in data
    assert "joined_at" in data
    assert data["email"] == "new@example.com"

    # Verify the creator was actually persisted to the DB.
    with db.get_db(db.DB_CREATORS) as conn:
        row = conn.execute(
            "SELECT * FROM creators WHERE creator_id = ?", (data["creator_id"],)
        ).fetchone()
    assert row is not None
    assert row["email"] == "new@example.com"


# ---------------------------------------------------------------------------
# POST /content
# ---------------------------------------------------------------------------


def test_create_content_success(client, creator_id):
    resp = client.post(
        "/content",
        json={"content": "Hello world, this is test content."},
        headers={"Bearer": creator_id},
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert "content_id" in data
    assert "submitted_at" in data
    assert data["status"] == "submitted"
    assert "confidence_score" in data
    assert data["label"] in {"likely_ai", "uncertain", "likely_human"}
    assert "transparency_label" in data
    assert "verified_human" in data
    assert "message" in data

    # Verify the content was actually persisted to the DB.
    with db.get_db(db.DB_CONTENT) as conn:
        row = conn.execute(
            "SELECT * FROM content WHERE content_id = ?", (data["content_id"],)
        ).fetchone()
    assert row is not None
    assert row["creator_id"] == creator_id


# ---------------------------------------------------------------------------
# POST /appeals
# ---------------------------------------------------------------------------


def test_create_appeal_success(client, creator_id, content_id):
    # Determine the current label so we can appeal with a different one.
    with db.get_db(db.DB_CONTENT) as conn:
        current_label = conn.execute(
            "SELECT label FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()["label"]

    different_label = next(
        l for l in {"likely_ai", "uncertain", "likely_human"} if l != current_label
    )

    resp = client.post(
        "/appeals",
        json={
            "content_id": content_id,
            "desired_label": different_label,
            "reason": "This is my appeal reason.",
        },
        headers={"Bearer": creator_id},
    )

    assert resp.status_code == 201
    data = resp.get_json()
    assert "appeal_id" in data
    assert data["content_id"] == content_id
    assert "appealed_at" in data
    assert data["desired_label"] == different_label
    assert "reason" in data

    # Verify the appeal was stored in the appeals DB.
    with db.get_db(db.DB_APPEALS) as conn:
        appeal_row = conn.execute(
            "SELECT * FROM appeals WHERE appeal_id = ?", (data["appeal_id"],)
        ).fetchone()
    assert appeal_row is not None
    assert appeal_row["content_id"] == content_id

    # Verify the content status was updated to "under_review".
    with db.get_db(db.DB_CONTENT) as conn:
        status = conn.execute(
            "SELECT status FROM content WHERE content_id = ?", (content_id,)
        ).fetchone()["status"]
    assert status == "under_review"


# ---------------------------------------------------------------------------
# GET /logs
# ---------------------------------------------------------------------------


def test_get_logs_success(client):
    TAIL = 5

    # Case 1: more logs exist than tail requests — only the last TAIL returned.
    for i in range(TAIL + 2):
        log.write_log(f"seed entry {i}", {"index": i})

    resp = client.get(f"/logs?tail={TAIL}", headers={"Bearer": TEST_ADMIN_ID})
    assert resp.status_code == 200
    entries = resp.get_json()
    assert len(entries) == TAIL

    # Case 2: fewer logs exist than tail requests — all of them returned.
    # Re-initialize the log file with a smaller set.
    with open(log._LOGS_FILE, "w"):
        pass  # truncate

    FEW = TAIL - 2
    for i in range(FEW):
        log.write_log(f"few entry {i}", {"index": i})

    resp = client.get(f"/logs?tail={TAIL}", headers={"Bearer": TEST_ADMIN_ID})
    assert resp.status_code == 200
    entries = resp.get_json()
    assert len(entries) == FEW + 1  # GET /logs logs its own access before reading
