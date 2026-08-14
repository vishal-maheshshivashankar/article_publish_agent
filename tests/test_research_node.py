from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.nodes.research import research_node


async def _fake_astream(*args, **kwargs):
    """Mirrors the real create_react_agent update shape, verified against a
    live call: 'agent' updates carry an AIMessage (non-empty tool_calls while
    still working, empty on the final answer), 'tools' updates carry a
    ToolMessage per call."""
    yield {"agent": {"messages": [AIMessage(content="", tool_calls=[{"name": "web_search", "args": {}, "id": "1"}])]}}
    yield {"tools": {"messages": [ToolMessage(content="result one", name="web_search", tool_call_id="1")]}}
    yield {
        "agent": {
            "messages": [AIMessage(content="", tool_calls=[{"name": "arxiv_search", "args": {}, "id": "2"}])]
        }
    }
    yield {"tools": {"messages": [ToolMessage(content="result two", name="arxiv_search", tool_call_id="2")]}}
    yield {"agent": {"messages": [AIMessage(content="Final synthesis text.", tool_calls=[])]}}


def test_research_node_collects_sources_and_final_text():
    import asyncio

    with patch("app.agent.nodes.research._research_agent") as mock_agent:
        mock_agent.astream = _fake_astream

        result = asyncio.run(research_node({"topic": "RAG", "article_type": "technical"}))

    assert result["research_notes"] == "Final synthesis text."
    assert result["status"] == "researched"
    assert [s["tool"] for s in result["sources"]] == ["web_search", "arxiv_search"]
    assert result["sources"][0]["output"] == "result one"


def test_research_node_calls_progress_callback_per_tool():
    import asyncio

    with patch("app.agent.nodes.research._research_agent") as mock_agent:
        mock_agent.astream = _fake_astream
        on_progress = AsyncMock()

        asyncio.run(
            research_node(
                {"topic": "RAG", "article_type": "technical"},
                config={"configurable": {"on_progress": on_progress}},
            )
        )

    assert on_progress.await_count == 2
    first_call_text = on_progress.await_args_list[0].args[0]
    assert "web_search" in first_call_text


def test_research_node_without_progress_callback_does_not_error():
    import asyncio

    with patch("app.agent.nodes.research._research_agent") as mock_agent:
        mock_agent.astream = _fake_astream

        result = asyncio.run(research_node({"topic": "RAG", "article_type": "technical"}, config=None))

    assert result["status"] == "researched"
