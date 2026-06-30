import sqlite3
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Force all src modules to be imported before any test runs so that
# monkeypatching their namespaces in fixtures actually takes effect.
import db
import auth
import log
import rate_limit
import routes.content
import routes.appeals
import routes.creators
import routes.logs

from db import init_db

TEST_ADMIN_ID = "test-admin-id"


@pytest.fixture(autouse=True)
def isolated_dbs(monkeypatch, tmp_path):
    """
    Redirect all SQLite connections and the log file to per-test temp paths
    so the real data/ directory is never touched.

    Every module that did `from db import get_db, DB_*` holds its own binding,
    so we must patch each of those namespaces individually in addition to db itself.
    """
    path_map = {
        "data/content.db":  str(tmp_path / "content.db"),
        "data/creators.db": str(tmp_path / "creators.db"),
        "data/appeals.db":  str(tmp_path / "appeals.db"),
    }
    # Some modules (auth, rate_limit) have their DB_* constants patched to the
    # temp path, so redirected_get_db may be called with the temp path directly.
    # Add self-mappings so those already-redirected paths pass straight through.
    path_map.update({v: v for v in list(path_map.values())})

    def redirected_get_db(path):
        if path not in path_map:
            raise KeyError(
                f"Test path_map has no entry for '{path}' — add it to avoid hitting the real DB"
            )
        conn = sqlite3.connect(path_map[path])
        conn.row_factory = sqlite3.Row
        return conn

    # Patch get_db everywhere it was imported
    for module in (
        db,
        auth,
        rate_limit,
        routes.content,
        routes.appeals,
        routes.creators,
        routes.logs,
    ):
        if hasattr(module, "get_db"):
            monkeypatch.setattr(module, "get_db", redirected_get_db)

    # Patch DB path constants wherever they were imported
    monkeypatch.setattr(db, "DB_CONTENT", path_map["data/content.db"])
    monkeypatch.setattr(db, "DB_CREATORS", path_map["data/creators.db"])
    monkeypatch.setattr(db, "DB_APPEALS", path_map["data/appeals.db"])
    monkeypatch.setattr(auth, "DB_CREATORS", path_map["data/creators.db"])
    monkeypatch.setattr(rate_limit, "DB_CREATORS", path_map["data/creators.db"])

    # Redirect log file
    log_file = str(tmp_path / "logs.jsonl")
    monkeypatch.setattr(log, "_LOGS_FILE", log_file)
    open(log_file, "a").close()

    # Provide a known admin ID without needing a real admin-ids.txt
    monkeypatch.setattr(auth, "admin_ids", {TEST_ADMIN_ID})

    init_db()


@pytest.fixture
def client():
    from server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture
def creator_id(client):
    resp = client.post("/creators", json={"email": "creator@example.com"})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["creator_id"]


@pytest.fixture
def other_creator_id(client):
    resp = client.post("/creators", json={"email": "other@example.com"})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["creator_id"]


@pytest.fixture
def admin_creator_id():
    """
    Inserts TEST_ADMIN_ID into the creators DB so _is_creator() passes for it.
    TEST_ADMIN_ID is already in auth.admin_ids via isolated_dbs, so this makes
    it valid for both creator-auth and admin-auth endpoints.
    """
    from datetime import datetime, timezone
    with db.get_db(db.DB_CREATORS) as conn:
        conn.execute(
            "INSERT INTO creators (creator_id, joined_at, email) VALUES (?, ?, ?)",
            (TEST_ADMIN_ID, datetime.now(timezone.utc).isoformat(), "admin@example.com"),
        )
    return TEST_ADMIN_ID


@pytest.fixture
def content_id(client, creator_id):
    """Submits a minimal piece of content and returns its ID."""
    resp = client.post(
        "/content",
        json={"content": "Hello world, this is test content."},
        headers={"Bearer": creator_id},
    )
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["content_id"]
