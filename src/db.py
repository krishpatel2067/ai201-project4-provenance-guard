import sqlite3

DB_CONTENT = "data/content.db"
DB_CREATORS = "data/creators.db"
DB_APPEALS = "data/appeals.db"


def get_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db(DB_CREATORS) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                creator_id TEXT PRIMARY KEY,
                joined_at  TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE
            )
        """)
        # Per-endpoint rate limit counters.
        # `identity` is either the creator_id (authenticated requests) or the
        # client IP address (unauthenticated, e.g. POST /creators).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rate_limits (
                identity   TEXT NOT NULL,
                endpoint   TEXT NOT NULL,
                window_min TEXT NOT NULL,
                window_day TEXT NOT NULL,
                count_min  INTEGER NOT NULL DEFAULT 0,
                count_day  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (identity, endpoint)
            )
        """)

    with get_db(DB_CONTENT) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS content (
                content_id             TEXT PRIMARY KEY,
                creator_id             TEXT NOT NULL,
                submitted_at           TEXT NOT NULL,
                content                TEXT NOT NULL,
                metadata               TEXT,
                status                 TEXT NOT NULL DEFAULT 'submitted',
                llm_score              REAL,
                stylo_heuristics_score REAL,
                pos_dist_score         REAL,
                confidence_score       REAL,
                label                  TEXT,
                transparency_label     TEXT,
                verified_human         INTEGER NOT NULL DEFAULT 0
            )
        """)

    with get_db(DB_APPEALS) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS appeals (
                appeal_id    TEXT PRIMARY KEY,
                content_id   TEXT NOT NULL,
                appealed_at  TEXT NOT NULL,
                desired_label TEXT NOT NULL,
                reason       TEXT NOT NULL
            )
        """)
