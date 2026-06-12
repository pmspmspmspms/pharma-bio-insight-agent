from __future__ import annotations

import hashlib
import sqlite3
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collectors import NewsItem
from config import Settings


SCHEMA_VERSION = 1


def save_run(
    items_by_topic: dict[str, list[NewsItem]],
    settings: Settings,
    run_date: datetime,
    briefing_path: Path,
    dashboard_path: Path | None = None,
) -> dict[str, Any]:
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_schema(conn)
        run_id = _insert_run(conn, items_by_topic, settings, run_date, briefing_path, dashboard_path)
        stored_count = _store_articles_for_run(conn, run_id, items_by_topic)
        conn.commit()
        summary = get_database_summary(db_path, conn)

    return {
        "path": str(db_path.resolve()),
        "runId": run_id,
        "storedItems": stored_count,
        **summary,
    }


def get_database_summary(db_path: Path, conn: sqlite3.Connection | None = None) -> dict[str, int]:
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(db_path)
        close_conn = True
    try:
        return {
            "totalRuns": _count(conn, "runs"),
            "totalArticles": _count(conn, "articles"),
            "totalRunArticles": _count(conn, "run_articles"),
        }
    finally:
        if close_conn:
            conn.close()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            timezone TEXT NOT NULL,
            days_back INTEGER NOT NULL,
            max_items_per_topic INTEGER NOT NULL,
            item_count INTEGER NOT NULL,
            briefing_path TEXT,
            dashboard_path TEXT
        );

        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url_hash TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL,
            title TEXT NOT NULL,
            source TEXT,
            published TEXT,
            summary TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS run_articles (
            run_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,
            topic_key TEXT NOT NULL,
            topic_label TEXT NOT NULL,
            rank INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (run_id, article_id, topic_key),
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE,
            FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_articles_last_seen ON articles(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_run_articles_topic ON run_articles(topic_key);
        """
    )
    conn.execute(
        """
        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (str(SCHEMA_VERSION),),
    )


def _insert_run(
    conn: sqlite3.Connection,
    items_by_topic: dict[str, list[NewsItem]],
    settings: Settings,
    run_date: datetime,
    briefing_path: Path,
    dashboard_path: Path | None,
) -> int:
    item_count = sum(len(items) for items in items_by_topic.values())
    cursor = conn.execute(
        """
        INSERT INTO runs (
            run_date,
            generated_at,
            timezone,
            days_back,
            max_items_per_topic,
            item_count,
            briefing_path,
            dashboard_path
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_date.strftime("%Y-%m-%d"),
            datetime.now(timezone.utc).isoformat(),
            settings.timezone,
            settings.days_back,
            settings.max_items_per_topic,
            item_count,
            str(briefing_path),
            str(dashboard_path) if dashboard_path else None,
        ),
    )
    return int(cursor.lastrowid)


def _store_articles_for_run(
    conn: sqlite3.Connection,
    run_id: int,
    items_by_topic: dict[str, list[NewsItem]],
) -> int:
    stored_count = 0
    now = datetime.now(timezone.utc).isoformat()
    for topic_key, items in items_by_topic.items():
        for rank, item in enumerate(items, start=1):
            article_id = _upsert_article(conn, item, now)
            conn.execute(
                """
                INSERT OR IGNORE INTO run_articles (
                    run_id,
                    article_id,
                    topic_key,
                    topic_label,
                    rank,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, article_id, topic_key, item.topic_label, rank, now),
            )
            stored_count += 1
    return stored_count


def _upsert_article(conn: sqlite3.Connection, item: NewsItem, now: str) -> int:
    normalized_url = _normalize_url(item.link)
    url_hash = _hash_url(normalized_url or item.title)
    conn.execute(
        """
        INSERT INTO articles (
            url_hash,
            url,
            title,
            source,
            published,
            summary,
            first_seen_at,
            last_seen_at,
            seen_count
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(url_hash) DO UPDATE SET
            title = excluded.title,
            source = excluded.source,
            published = excluded.published,
            summary = excluded.summary,
            last_seen_at = excluded.last_seen_at,
            seen_count = articles.seen_count + 1
        """,
        (
            url_hash,
            normalized_url,
            item.title,
            item.source,
            item.published,
            item.summary,
            now,
            now,
        ),
    )
    cursor = conn.execute("SELECT id FROM articles WHERE url_hash = ?", (url_hash,))
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError("Article upsert did not return an id")
    return int(row["id"])


def _count(conn: sqlite3.Connection, table: str) -> int:
    cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
    return int(cursor.fetchone()[0])


def _normalize_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, value) for key, value in query if not key.lower().startswith("utm_")]
    return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))


def _hash_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()
