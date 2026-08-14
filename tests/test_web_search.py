from unittest.mock import MagicMock, patch

from app.agent.tools import web_search as web_search_module


def test_uses_tavily_key_from_settings_not_os_environ(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", "settings-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    with patch("tavily.TavilyClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.search.return_value = {"results": [{"title": "T", "url": "u", "content": "c"}]}
        mock_client_cls.return_value = mock_client

        result = web_search_module.web_search.invoke({"query": "RAG"})

        mock_client_cls.assert_called_once_with(api_key="settings-key")
        assert "T" in result


def test_falls_back_to_duckduckgo_without_tavily_key(monkeypatch):
    monkeypatch.setattr(web_search_module.settings, "tavily_api_key", None)

    with patch("duckduckgo_search.DDGS") as mock_ddgs_cls:
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__.return_value.text.return_value = [{"title": "T", "href": "u", "body": "b"}]
        mock_ddgs_cls.return_value = mock_ddgs

        result = web_search_module.web_search.invoke({"query": "RAG"})

        assert "T" in result
