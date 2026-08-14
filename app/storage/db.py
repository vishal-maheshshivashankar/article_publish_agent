import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    telegram_user_id INTEGER NOT NULL,
    topic TEXT NOT NULL,
    article_type TEXT DEFAULT 'technical',
    status TEXT DEFAULT 'researching',
    title TEXT,
    content TEXT,
    sources TEXT,
    medium_url TEXT,
    medium_post_id TEXT,
    error TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    published_at TEXT
);

-- Full-text archive of published articles, used by the search_past_articles
-- research tool so new articles can build on / avoid duplicating old ones.
-- Populated in mark_published(), which the user triggers via /published
-- after manually publishing on Medium (see app/bot/telegram_bot.py) --
-- not on every article write, since drafts that never got published aren't
-- meaningful prior coverage.
CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
    article_id UNINDEXED,
    title,
    topic,
    content
);
"""


async def init_db() -> None:
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.executescript(_SCHEMA)
        await db.commit()


async def create_article(telegram_user_id: int, topic: str, article_type: str) -> str:
    article_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO articles (id, telegram_user_id, topic, article_type, status) "
            "VALUES (?, ?, ?, ?, 'researching')",
            (article_id, telegram_user_id, topic, article_type),
        )
        await db.commit()
    return article_id


async def update_article(article_id: str, **fields: Any) -> None:
    if not fields:
        return
    if "sources" in fields and not isinstance(fields["sources"], str):
        fields["sources"] = json.dumps(fields["sources"])
    columns = ", ".join(f"{k} = ?" for k in fields)
    values = [*fields.values(), article_id]
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(f"UPDATE articles SET {columns} WHERE id = ?", values)  # noqa: S608
        await db.commit()


async def mark_published(article_id: str, medium_url: str, medium_post_id: str | None = None) -> None:
    await update_article(
        article_id,
        status="published",
        medium_url=medium_url,
        medium_post_id=medium_post_id,
        published_at=datetime.now(timezone.utc).isoformat(),
    )
    article = await get_article(article_id)
    async with aiosqlite.connect(settings.database_path) as db:
        await db.execute(
            "INSERT INTO articles_fts (article_id, title, topic, content) VALUES (?, ?, ?, ?)",
            (article_id, article["title"] or "", article["topic"] or "", article["content"] or ""),
        )
        await db.commit()


async def get_article(article_id: str) -> dict | None:
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_article_by_prefix(prefix: str) -> dict | None:
    """Look up an article by an id prefix, e.g. the short id shown in /status.

    Most-recently-created match wins if a prefix is ambiguous.
    """
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM articles WHERE id LIKE ? ORDER BY created_at DESC LIMIT 1",
            (f"{prefix}%",),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def list_recent_articles(telegram_user_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM articles WHERE telegram_user_id = ? ORDER BY created_at DESC LIMIT ?",
            (telegram_user_id, limit),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


def _sanitize_fts_query(text: str) -> str:
    """Turn arbitrary (possibly LLM-generated) text into a safe FTS5 MATCH expression.

    FTS5's query syntax treats punctuation specially and raises on malformed
    input, but the caller here is a tool argument, not a controlled query --
    so this reduces to bare alphanumeric tokens ORed together rather than
    trying to preserve FTS5 query operators.
    """
    tokens = re.findall(r"[A-Za-z0-9]+", text)
    return " OR ".join(f'"{t}"' for t in tokens)


def search_published_articles(query: str, limit: int = 5) -> list[dict]:
    """Synchronous keyword search over previously published articles.

    Plain sqlite3 (not aiosqlite) since this is called from a sync LangChain
    tool inside the research agent's tool-calling loop, not from the async
    bot handlers.
    """
    match = _sanitize_fts_query(query)
    if not match:
        return []
    with sqlite3.connect(settings.database_path) as db:
        db.row_factory = sqlite3.Row
        cursor = db.execute(
            "SELECT article_id, title, topic, "
            "snippet(articles_fts, 3, '', '', '...', 20) AS excerpt "
            "FROM articles_fts WHERE articles_fts MATCH ? ORDER BY rank LIMIT ?",
            (match, limit),
        )
        return [dict(r) for r in cursor.fetchall()]
