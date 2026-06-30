"""
Auth tests — verify that each endpoint enforces its Bearer token requirements.

POST /content and POST /appeals accept any valid creator ID (admins included,
since admin IDs are also creator IDs). GET /logs only accepts admin IDs.
POST /creators has no auth and is not tested here.

Rate limiting is bypassed so these tests are purely about auth behavior.
"""

import pytest
from conftest import TEST_ADMIN_ID


@pytest.fixture(autouse=True)
def bypass_rate_limit(monkeypatch):
    import rate_limit
    monkeypatch.setattr(rate_limit, "_check_rate_limit", lambda *_: (True, ""))


# ---------------------------------------------------------------------------
# POST /content
# ---------------------------------------------------------------------------

class TestContentAuth:
    def test_valid_creator_id_accepted(self, client, creator_id):
        resp = client.post(
            "/content",
            json={"content": "Hello world."},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201

    def test_valid_admin_id_accepted(self, client, admin_creator_id):
        # Admin IDs are also creator IDs, so creator-auth endpoints must accept them.
        resp = client.post(
            "/content",
            json={"content": "Hello world."},
            headers={"Bearer": admin_creator_id},
        )
        assert resp.status_code == 201

    def test_missing_bearer_returns_401(self, client):
        resp = client.post("/content", json={"content": "Hello world."})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /appeals
# ---------------------------------------------------------------------------

class TestAppealsAuth:
    def _submit_content(self, client, bearer):
        """Helper: submit content and return (content_id, label)."""
        resp = client.post(
            "/content",
            json={"content": "Content for appeals auth test."},
            headers={"Bearer": bearer},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        return data["content_id"], data["label"]

    def _different_label(self, current_label):
        return next(l for l in {"likely_ai", "uncertain", "likely_human"} if l != current_label)

    def test_valid_creator_id_accepted(self, client, creator_id):
        content_id, label = self._submit_content(client, creator_id)
        resp = client.post(
            "/appeals",
            json={
                "content_id": content_id,
                "desired_label": self._different_label(label),
                "reason": "auth test appeal",
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201

    def test_valid_admin_id_accepted(self, client, admin_creator_id):
        # Admin submits their own content then appeals it.
        content_id, label = self._submit_content(client, admin_creator_id)
        resp = client.post(
            "/appeals",
            json={
                "content_id": content_id,
                "desired_label": self._different_label(label),
                "reason": "auth test appeal",
            },
            headers={"Bearer": admin_creator_id},
        )
        assert resp.status_code == 201

    def test_missing_bearer_returns_401(self, client):
        resp = client.post(
            "/appeals",
            json={
                "content_id": "irrelevant",
                "desired_label": "likely_human",
                "reason": "auth test appeal",
            },
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /logs
# ---------------------------------------------------------------------------

class TestLogsAuth:
    def test_valid_admin_id_accepted(self, client):
        resp = client.get("/logs", headers={"Bearer": TEST_ADMIN_ID})
        assert resp.status_code == 200

    def test_valid_creator_id_rejected(self, client, creator_id):
        # A regular creator ID is not an admin — must be rejected.
        resp = client.get("/logs", headers={"Bearer": creator_id})
        assert resp.status_code == 401

    def test_missing_bearer_returns_401(self, client):
        resp = client.get("/logs")
        assert resp.status_code == 401
