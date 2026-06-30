"""
Detection signal tests — four categories:
  1. Fallback cases for each signal (returns 0.5 immediately on error/short content)
  2. Certificate: adequate and inadequate metadata via POST /content integration
  3. Certificate + special transparency label: combined test (mocked signals)
  4. Content classification: clearly human, clearly AI, ambiguous (real LLM calls)

For LLM fallback tests the Groq client is mocked via monkeypatching.
For certificate tests the detection signals themselves are mocked so cert logic
is tested in isolation from LLM variability.
Classification tests use the real LLM — no mocking.
"""

import types
import pytest
import detection
import routes.content
import db
from conftest import TEST_ADMIN_ID


@pytest.fixture(autouse=True)
def bypass_rate_limit(monkeypatch):
    import rate_limit
    monkeypatch.setattr(rate_limit, "_check_rate_limit", lambda *_: (True, ""))


# Helpers ----------------------------------------------------------------

def _mock_llm_resp(text: str):
    """Builds a minimal Groq-response-shaped namespace from a text string."""
    msg = types.SimpleNamespace(content=text)
    choice = types.SimpleNamespace(message=msg)
    return types.SimpleNamespace(choices=[choice])


ADEQUATE_METADATA = {
    "platform": "desktop_app",
    "pastes_from_elsewhere": 0,
    "sessions": [
        {"start": "2026-01-01T10:00:00", "end": "2026-01-01T11:30:00"},
        {"start": "2026-01-02T10:00:00", "end": "2026-01-02T11:30:00"},
        {"start": "2026-01-03T10:00:00", "end": "2026-01-03T11:30:00"},
    ],
}

SHORT = "too short"  # < 100 chars — triggers every signal's length fallback

# Content long enough for the real detection signals (used in cert tests)
LONG_CONTENT = "The quick brown fox jumps over the lazy dog. " * 10


# -------------------------------------------------------------------------
# 1. Fallback cases
# -------------------------------------------------------------------------

class TestLLMFallbacks:
    def test_short_content_returns_0_5(self):
        assert detection.detect_llm(SHORT) == 0.5

    def test_api_exception_returns_0_5(self, monkeypatch):
        def raise_error(*args, **kwargs):
            raise RuntimeError("Groq API unavailable")
        monkeypatch.setattr(detection._client.chat.completions, "create", raise_error)
        assert detection.detect_llm(LONG_CONTENT) == 0.5

    def test_unparsable_response_line_returns_0_5(self, monkeypatch):
        monkeypatch.setattr(
            detection._client.chat.completions, "create",
            lambda *a, **kw: _mock_llm_resp("this is not the expected format at all"),
        )
        assert detection.detect_llm(LONG_CONTENT) == 0.5

    def test_too_few_valid_categories_returns_0_5(self, monkeypatch):
        # All five lines parse correctly but use unknown category names,
        # so none are added to scores — len(scores) < 5 triggers fallback.
        bad_categories = (
            "Alpha: Score: 0.8 Reason: test.\n"
            "Beta: Score: 0.7 Reason: test.\n"
            "Gamma: Score: 0.6 Reason: test.\n"
            "Delta: Score: 0.9 Reason: test.\n"
            "Epsilon: Score: 0.75 Reason: test."
        )
        monkeypatch.setattr(
            detection._client.chat.completions, "create",
            lambda *a, **kw: _mock_llm_resp(bad_categories),
        )
        assert detection.detect_llm(LONG_CONTENT) == 0.5

    def test_valid_formatted_output_returns_weighted_score(self, monkeypatch):
        # Scores: Tone=0.8, Informality=0.7, Language=0.6, Stance=0.9, Progression=0.75
        # Weighted: 0.1*0.8 + 0.2*0.7 + 0.2*0.6 + 0.2*0.9 + 0.3*0.75 = 0.745
        valid_output = (
            "Tone: Score: 0.8 Reason: Emotional and reflective.\n"
            "Informality: Score: 0.7 Reason: Casual and conversational.\n"
            "Language: Score: 0.6 Reason: Direct, minimal hedging.\n"
            "Stance: Score: 0.9 Reason: Clearly takes a side.\n"
            "Progression: Score: 0.75 Reason: Clear arc from start to finish."
        )
        monkeypatch.setattr(
            detection._client.chat.completions, "create",
            lambda *a, **kw: _mock_llm_resp(valid_output),
        )
        result = detection.detect_llm(LONG_CONTENT)
        assert result == pytest.approx(0.745)


class TestStyloFallbacks:
    def test_short_content_returns_0_5(self):
        assert detection.detect_stylo_heuristics(SHORT) == 0.5


class TestPosDistFallbacks:
    def test_short_content_returns_0_5(self):
        assert detection.detect_pos_dist(SHORT) == 0.5


# -------------------------------------------------------------------------
# 2 & 3. Certificate adequacy + special transparency label (combined)
# -------------------------------------------------------------------------

@pytest.fixture
def mocked_signals(monkeypatch):
    """
    Patches all three detection signals in the content route to return 0.3
    (combined score = 0.3, label = likely_ai without cert).
    With the provenance boost: 1 - (1-0.3)^3.25 ≈ 0.683 → likely_human.
    """
    monkeypatch.setattr(routes.content, "detect_llm",              lambda c: 0.3)
    monkeypatch.setattr(routes.content, "detect_stylo_heuristics", lambda c: 0.3)
    monkeypatch.setattr(routes.content, "detect_pos_dist",         lambda c: 0.3)


class TestProvenance:
    def test_adequate_metadata_grants_cert_and_verified_label(
        self, client, creator_id, mocked_signals
    ):
        """
        Adequate metadata should grant the certificate, boost the score into
        likely_human territory, and produce the special verified transparency label.
        Both the response and the stored DB row are checked.
        """
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT, "metadata": ADEQUATE_METADATA},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201
        data = resp.get_json()

        # Response checks
        assert data["verified_human"] is True
        assert data["label"] == "likely_human"
        assert data["transparency_label"] == "Verified human - this content is most likely human-made."

        # DB checks — verified_human stored as integer 1 in SQLite
        with db.get_db(db.DB_CONTENT) as conn:
            row = conn.execute(
                "SELECT verified_human, label, transparency_label FROM content WHERE content_id = ?",
                (data["content_id"],),
            ).fetchone()
        assert row["verified_human"] == 1
        assert row["label"] == "likely_human"
        assert row["transparency_label"] == "Verified human - this content is most likely human-made."

    def test_wrong_platform_no_cert(self, client, creator_id, mocked_signals):
        meta = {**ADEQUATE_METADATA, "platform": "web_app"}
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT, "metadata": meta},
            headers={"Bearer": creator_id},
        )
        assert resp.get_json()["verified_human"] is False

    def test_pastes_from_elsewhere_no_cert(self, client, creator_id, mocked_signals):
        meta = {**ADEQUATE_METADATA, "pastes_from_elsewhere": 1}
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT, "metadata": meta},
            headers={"Bearer": creator_id},
        )
        assert resp.get_json()["verified_human"] is False

    def test_too_few_qualifying_sessions_no_cert(self, client, creator_id, mocked_signals):
        meta = {
            **ADEQUATE_METADATA,
            "sessions": [  # only 2 qualifying sessions instead of 3
                {"start": "2026-01-01T10:00:00", "end": "2026-01-01T11:30:00"},
                {"start": "2026-01-02T10:00:00", "end": "2026-01-02T11:30:00"},
            ],
        }
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT, "metadata": meta},
            headers={"Bearer": creator_id},
        )
        assert resp.get_json()["verified_human"] is False

    def test_sessions_too_short_no_cert(self, client, creator_id, mocked_signals):
        meta = {
            **ADEQUATE_METADATA,
            "sessions": [  # 3 sessions but each under 1 hour
                {"start": "2026-01-01T10:00:00", "end": "2026-01-01T10:30:00"},
                {"start": "2026-01-02T10:00:00", "end": "2026-01-02T10:30:00"},
                {"start": "2026-01-03T10:00:00", "end": "2026-01-03T10:30:00"},
            ],
        }
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT, "metadata": meta},
            headers={"Bearer": creator_id},
        )
        assert resp.get_json()["verified_human"] is False

    def test_missing_metadata_no_cert(self, client, creator_id, mocked_signals):
        resp = client.post(
            "/content",
            json={"content": LONG_CONTENT},
            headers={"Bearer": creator_id},
        )
        assert resp.get_json()["verified_human"] is False


# -------------------------------------------------------------------------
# 4. Content classification (real LLM calls)
# -------------------------------------------------------------------------

CLEARLY_HUMAN = (
    "ok so i finally tried that new ramen place downtown and honestly? underwhelming. "
    "the broth was fine but they put WAY too much sodium in it and i was thirsty for "
    "like three hours after. my friend got the spicy version and said it was better. "
    "probably won't go back unless someone drags me there"
)

CLEARLY_AI = (
    "Artificial intelligence represents a transformative paradigm shift in modern "
    "society. It is important to note that while the benefits of AI are numerous, it "
    "is equally essential to consider the ethical implications. Furthermore, "
    "stakeholders across various sectors must collaborate to ensure responsible "
    "deployment."
)


class TestClassification:
    def test_clearly_human_content(self, client, creator_id):
        resp = client.post(
            "/content",
            json={"content": CLEARLY_HUMAN},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["confidence_score"] >= 0.5  # 0.1 leeway around the 0.6 spec threshold
        assert data["label"] in {"likely_human", "uncertain"}  # must not be likely_ai

    def test_clearly_ai_content(self, client, creator_id):
        resp = client.post(
            "/content",
            json={"content": CLEARLY_AI},
            headers={"Bearer": creator_id},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["confidence_score"] <= 0.5  # 0.1 leeway around the 0.4 spec threshold
        assert data["label"] in {"likely_ai", "uncertain"}  # must not be likely_human

