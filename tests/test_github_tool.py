from unittest.mock import MagicMock, patch

from app.agent.tools import github_tool as github_tool_module


def test_uses_github_token_from_settings_not_os_environ(monkeypatch):
    monkeypatch.setattr(github_tool_module.settings, "github_token", "settings-token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with patch("app.agent.tools.github_tool.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": []},
        )
        mock_get.return_value.raise_for_status = lambda: None

        github_tool_module.github_search.invoke({"query": "langgraph"})

        headers = mock_get.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer settings-token"


def test_no_auth_header_without_token(monkeypatch):
    monkeypatch.setattr(github_tool_module.settings, "github_token", None)

    with patch("app.agent.tools.github_tool.requests.get") as mock_get:
        mock_get.return_value = MagicMock(status_code=200, json=lambda: {"items": []})
        mock_get.return_value.raise_for_status = lambda: None

        github_tool_module.github_search.invoke({"query": "langgraph"})

        headers = mock_get.call_args.kwargs["headers"]
        assert "Authorization" not in headers
