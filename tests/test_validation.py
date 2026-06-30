"""
Input validation tests — verify that each endpoint rejects invalid inputs with 400.

Rate limiting is bypassed here (see the autouse fixture below) because validation
tests may need multiple requests to the same endpoint within a single test, and
hitting rate limits would produce 429s that mask the 400s we're testing for.
Rate limiting has its own dedicated test file.
"""

import pytest
from conftest import TEST_ADMIN_ID


@pytest.fixture(autouse=True)
def bypass_rate_limit(monkeypatch):
    import rate_limit
    monkeypatch.setattr(rate_limit, "_check_rate_limit", lambda *_: (True, ""))


# ---------------------------------------------------------------------------
# POST /creators
# ---------------------------------------------------------------------------

class TestCreatorsValidation:
    def test_missing_email_returns_400(self, client):
        resp = client.post("/creators", json={})
        assert resp.status_code == 400

    def test_email_with_no_at_symbol_returns_400(self, client):
        resp = client.post("/creators", json={"email": "notanemail"})
        assert resp.status_code == 400

    def test_email_with_no_domain_returns_400(self, client):
        resp = client.post("/creators", json={"email": "user@"})
        assert resp.status_code == 400

    def test_email_with_no_tld_returns_400(self, client):
        resp = client.post("/creators", json={"email": "user@domain"})
        assert resp.status_code == 400

    def test_duplicate_email_returns_400(self, client):
        client.post("/creators", json={"email": "dup@example.com"})
        resp = client.post("/creators", json={"email": "dup@example.com"})
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# POST /content
# ---------------------------------------------------------------------------

class TestContentValidation:
    def test_missing_content_field_returns_400(self, client, creator_id):
        resp = client.post(
            "/content",
            json={"metadata": {}},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_content_over_100k_chars_returns_400(self, client, creator_id):
        resp = client.post(
            "/content",
            json={"content": "x" * 100_001},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_metadata_is_optional(self, client, creator_id):
        """Omitting metadata entirely should succeed — it is not a required field."""
        resp = client.post(
            "/content",
            json={"content": "Hello world, this is valid content."},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# POST /appeals
# ---------------------------------------------------------------------------

class TestAppealsValidation:
    def test_missing_content_id_returns_400(self, client, creator_id):
        resp = client.post(
            "/appeals",
            json={"desired_label": "likely_human", "reason": "test reason"},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_missing_desired_label_returns_400(self, client, creator_id, content_id):
        resp = client.post(
            "/appeals",
            json={"content_id": content_id, "reason": "test reason"},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_missing_reason_returns_400(self, client, creator_id, content_id):
        resp = client.post(
            "/appeals",
            json={"content_id": content_id, "desired_label": "likely_human"},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_empty_reason_returns_400(self, client, creator_id, content_id):
        resp = client.post(
            "/appeals",
            json={"content_id": content_id, "desired_label": "likely_human", "reason": ""},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_invalid_desired_label_returns_400(self, client, creator_id, content_id):
        resp = client.post(
            "/appeals",
            json={
                "content_id": content_id,
                "desired_label": "not_a_real_label",
                "reason": "test reason",
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_reason_over_2500_chars_returns_400(self, client, creator_id, content_id):
        resp = client.post(
            "/appeals",
            json={
                "content_id": content_id,
                "desired_label": "likely_human",
                "reason": "x" * 2501,
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_nonexistent_content_id_returns_400(self, client, creator_id):
        resp = client.post(
            "/appeals",
            json={
                "content_id": "00000000-0000-0000-0000-000000000000",
                "desired_label": "likely_human",
                "reason": "test reason",
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_content_owned_by_other_creator_returns_400(
        self, client, content_id, other_creator_id
    ):
        """content_id belongs to creator_id; appealing as other_creator_id should fail."""
        resp = client.post(
            "/appeals",
            json={
                "content_id": content_id,
                "desired_label": "likely_human",
                "reason": "test reason",
            },
            headers={"Bearer": other_creator_id},
        )
        assert resp.status_code == 400

    def test_desired_label_same_as_current_returns_400(self, client, creator_id):
        # Submit content and read back the label the detection pipeline assigned.
        content_resp = client.post(
            "/content",
            json={"content": "Some content for the same-label test."},
            headers={"Bearer": creator_id},
        )
        assert content_resp.status_code == 201
        data = content_resp.get_json()
        local_content_id = data["content_id"]
        current_label = data["label"]

        resp = client.post(
            "/appeals",
            json={
                "content_id": local_content_id,
                "desired_label": current_label,
                "reason": "test reason",
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400

    def test_content_already_under_review_returns_400(self, client, creator_id):
        content_resp = client.post(
            "/content",
            json={"content": "Content for the under-review test."},
            headers={"Bearer": creator_id},
        )
        assert content_resp.status_code == 201
        data = content_resp.get_json()
        local_content_id = data["content_id"]
        current_label = data["label"]

        # Pick any label that differs from the current one for the first appeal.
        all_labels = {"likely_ai", "uncertain", "likely_human"}
        different_label = next(l for l in all_labels if l != current_label)

        # First appeal — should succeed and put the content under review.
        first = client.post(
            "/appeals",
            json={
                "content_id": local_content_id,
                "desired_label": different_label,
                "reason": "first appeal",
            },
            headers={"Bearer": creator_id},
        )
        assert first.status_code == 201

        # Second appeal — content is now under review, should be rejected.
        resp = client.post(
            "/appeals",
            json={
                "content_id": local_content_id,
                "desired_label": different_label,
                "reason": "second appeal",
            },
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /logs
# ---------------------------------------------------------------------------

class TestLogsValidation:
    def test_non_integer_tail_returns_400(self, client):
        resp = client.get("/logs?tail=abc", headers={"Bearer": TEST_ADMIN_ID})
        assert resp.status_code == 400
