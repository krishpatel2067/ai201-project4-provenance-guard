"""
Rate limit tests — verify that each endpoint enforces its per-minute and
per-day limits.

The fake_clock fixture (conftest.py) replaces datetime.now() inside rate_limit
so we can simulate the passage of time without sleeping. Advancing the clock by
one minute resets the minute window while keeping the same day window, letting
us exhaust the day limit without ever tripping the minute limit first.

Intermediate requests may return 400 or 201 depending on the payload — that is
intentional. The spec says rate limiting counts even rejected requests, so only
the final request's 429 status matters.
"""

from conftest import TEST_ADMIN_ID
from rate_limit import _RATE_LIMITS


def fire_until_day_limit_exceeded(make_request, per_min, per_day, fake_clock):
    """
    Fires exactly per_day requests while staying within per_min per minute
    (advancing the fake clock when a minute bucket fills), then fires one
    more request that should exceed the day limit.
    Returns the final response.
    """
    remaining = per_day
    while remaining > 0:
        batch = min(remaining, per_min)
        for _ in range(batch):
            make_request()
        remaining -= batch
        fake_clock.advance_minute()
    return make_request()


# ---------------------------------------------------------------------------
# POST /creators  (identity = client IP)
# ---------------------------------------------------------------------------


class TestCreatorsRateLimit:
    def test_minute_limit_returns_429(self, client, fake_clock):
        per_min, _ = _RATE_LIMITS["POST /creators"]
        for _ in range(per_min):
            client.post("/creators", json={"email": "rl@example.com"})
        resp = client.post("/creators", json={"email": "rl@example.com"})
        assert resp.status_code == 429

    def test_day_limit_returns_429(self, client, fake_clock):
        per_min, per_day = _RATE_LIMITS["POST /creators"]

        def make():
            return client.post("/creators", json={"email": "rl@example.com"})

        resp = fire_until_day_limit_exceeded(
            make, per_min=per_min, per_day=per_day, fake_clock=fake_clock
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /content  (identity = creator ID)
# ---------------------------------------------------------------------------


class TestContentRateLimit:
    def test_minute_limit_returns_429(self, client, creator_id, fake_clock):
        per_min, _ = _RATE_LIMITS["POST /content"]
        for _ in range(per_min):
            client.post(
                "/content", json={"content": "x"}, headers={"Bearer": creator_id}
            )
        resp = client.post(
            "/content", json={"content": "x"}, headers={"Bearer": creator_id}
        )
        assert resp.status_code == 429

    def test_day_limit_returns_429(self, client, creator_id, fake_clock):
        per_min, per_day = _RATE_LIMITS["POST /content"]

        def make():
            return client.post(
                "/content", json={"content": "x"}, headers={"Bearer": creator_id}
            )

        resp = fire_until_day_limit_exceeded(
            make, per_min=per_min, per_day=per_day, fake_clock=fake_clock
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# POST /appeals  (identity = creator ID)
# ---------------------------------------------------------------------------


class TestAppealsRateLimit:
    def test_minute_limit_returns_429(self, client, creator_id, fake_clock):
        per_min, _ = _RATE_LIMITS["POST /appeals"]
        # Body is intentionally empty — rate limit fires before input validation.
        for _ in range(per_min):
            client.post("/appeals", json={}, headers={"Bearer": creator_id})
        resp = client.post("/appeals", json={}, headers={"Bearer": creator_id})
        assert resp.status_code == 429

    def test_day_limit_returns_429(self, client, creator_id, fake_clock):
        per_min, per_day = _RATE_LIMITS["POST /appeals"]

        def make():
            return client.post("/appeals", json={}, headers={"Bearer": creator_id})

        resp = fire_until_day_limit_exceeded(
            make, per_min=per_min, per_day=per_day, fake_clock=fake_clock
        )
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# GET /logs  (identity = admin ID)
# ---------------------------------------------------------------------------


class TestLogsRateLimit:
    def test_minute_limit_returns_429(self, client, fake_clock):
        per_min, _ = _RATE_LIMITS["GET /logs"]
        for _ in range(per_min):
            client.get("/logs", headers={"Bearer": TEST_ADMIN_ID})
        resp = client.get("/logs", headers={"Bearer": TEST_ADMIN_ID})
        assert resp.status_code == 429

    def test_day_limit_returns_429(self, client, fake_clock):
        per_min, per_day = _RATE_LIMITS["GET /logs"]

        def make():
            return client.get("/logs", headers={"Bearer": TEST_ADMIN_ID})

        resp = fire_until_day_limit_exceeded(
            make, per_min=per_min, per_day=per_day, fake_clock=fake_clock
        )
        assert resp.status_code == 429
