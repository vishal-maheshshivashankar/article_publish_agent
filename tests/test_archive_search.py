import asyncio
import os
import tempfile

import pytest

from app.storage import db as db_module


@pytest.fixture()
def temp_db(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.db")
        monkeypatch.setattr(db_module.settings, "database_path", path)
        asyncio.run(db_module.init_db())
        yield path


def _publish_article(topic: str, title: str, content: str) -> str:
    async def setup():
        article_id = await db_module.create_article(1, topic, "technical")
        await db_module.update_article(article_id, title=title, content=content)
        await db_module.mark_published(article_id, "https://medium.com/x", "post1")
        return article_id

    return asyncio.run(setup())


def test_search_finds_published_article(temp_db):
    article_id = _publish_article(
        "RAG",
        "RAG Basics",
        "This article covers retrieval augmented generation for engineers.",
    )

    results = db_module.search_published_articles("retrieval")

    assert any(r["article_id"] == article_id for r in results)


def test_search_returns_empty_for_no_match(temp_db):
    _publish_article("RAG", "RAG Basics", "retrieval augmented generation")

    assert db_module.search_published_articles("nonexistent-topic-xyz") == []


def test_search_before_any_publish_is_empty(temp_db):
    assert db_module.search_published_articles("anything") == []


def test_search_handles_punctuation_without_crashing(temp_db):
    _publish_article("RAG", "RAG Basics", "retrieval augmented generation")

    # Must not raise an FTS5 syntax error on punctuation-heavy LLM-style input.
    results = db_module.search_published_articles("what's new: RAG?! (2026 edition)")

    assert any(r["title"] == "RAG Basics" for r in results)


def test_search_empty_query_returns_empty(temp_db):
    _publish_article("RAG", "RAG Basics", "retrieval augmented generation")

    assert db_module.search_published_articles("???") == []


def test_unpublished_article_is_not_searchable(temp_db):
    async def setup():
        article_id = await db_module.create_article(1, "RAG", "technical")
        await db_module.update_article(
            article_id, title="Draft Only", content="retrieval augmented generation draft"
        )
        return article_id

    asyncio.run(setup())

    assert db_module.search_published_articles("retrieval") == []
