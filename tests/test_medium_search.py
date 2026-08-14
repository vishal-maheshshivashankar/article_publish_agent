from unittest.mock import MagicMock, patch

from app.agent.tools import medium_search as medium_search_module
from app.agent.tools.medium_search import medium_search


def test_returns_explicit_message_without_tavily_key(monkeypatch):
    monkeypatch.setattr(medium_search_module.settings, "tavily_api_key", None)

    result = medium_search.invoke({"query": "python design patterns"})

    assert "TAVILY_API_KEY" in result


def test_searches_medium_domain_only_via_tavily(monkeypatch):
    monkeypatch.setattr(medium_search_module.settings, "tavily_api_key", "test-key")

    with patch("tavily.TavilyClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "results": [{"title": "T", "url": "https://medium.com/x", "content": "c"}]
        }
        mock_client_cls.return_value = mock_client

        result = medium_search.invoke({"query": "RAG"})

        mock_client.search.assert_called_once_with("RAG", max_results=5, include_domains=["medium.com"])
        assert "T" in result
        assert "medium.com/x" in result


def test_reports_no_results_without_raising(monkeypatch):
    monkeypatch.setattr(medium_search_module.settings, "tavily_api_key", "test-key")

    with patch("tavily.TavilyClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": []}
        mock_client_cls.return_value = mock_client

        result = medium_search.invoke({"query": "an extremely obscure topic"})

        assert "No existing Medium articles found" in result


def test_swallows_backend_errors(monkeypatch):
    monkeypatch.setattr(medium_search_module.settings, "tavily_api_key", "test-key")

    with patch("tavily.TavilyClient") as mock_client_cls:
        mock_client_cls.side_effect = RuntimeError("network down")

        result = medium_search.invoke({"query": "RAG"})

        assert "medium_search failed" in result
