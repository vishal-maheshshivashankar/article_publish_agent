from unittest.mock import patch

from app.agent.tools.archive_tool import search_past_articles


@patch("app.agent.tools.archive_tool.search_published_articles")
def test_formats_results_when_found(mock_search):
    mock_search.return_value = [
        {"article_id": "abc123", "title": "RAG Basics", "topic": "RAG", "excerpt": "...retrieval..."}
    ]

    result = search_past_articles.invoke({"query": "retrieval"})

    assert "RAG Basics" in result
    assert "...retrieval..." in result


@patch("app.agent.tools.archive_tool.search_published_articles")
def test_reports_no_match_without_raising(mock_search):
    mock_search.return_value = []

    result = search_past_articles.invoke({"query": "nothing"})

    assert "No previously published articles" in result


@patch("app.agent.tools.archive_tool.search_published_articles")
def test_swallows_backend_errors(mock_search):
    mock_search.side_effect = RuntimeError("db locked")

    result = search_past_articles.invoke({"query": "retrieval"})

    assert "search_past_articles failed" in result
