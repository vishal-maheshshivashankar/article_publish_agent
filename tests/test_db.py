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


def test_get_article_by_prefix_matches(temp_db):
    article_id = asyncio.run(db_module.create_article(1, "RAG", "technical"))

    found = asyncio.run(db_module.get_article_by_prefix(article_id[:8]))

    assert found is not None
    assert found["id"] == article_id


def test_get_article_by_prefix_no_match_returns_none(temp_db):
    asyncio.run(db_module.create_article(1, "RAG", "technical"))

    assert asyncio.run(db_module.get_article_by_prefix("00000000")) is None


def test_mark_published_without_post_id(temp_db):
    article_id = asyncio.run(db_module.create_article(1, "RAG", "technical"))
    asyncio.run(db_module.update_article(article_id, title="RAG Basics", content="body text"))

    asyncio.run(db_module.mark_published(article_id, "https://medium.com/@me/rag-basics"))

    article = asyncio.run(db_module.get_article(article_id))
    assert article["status"] == "published"
    assert article["medium_url"] == "https://medium.com/@me/rag-basics"
    assert article["medium_post_id"] is None
