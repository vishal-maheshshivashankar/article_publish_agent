import asyncio
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from app.agent.nodes.write import write_node


@patch("app.agent.nodes.write._llm")
def test_write_node_extracts_and_strips_image_markers(mock_llm):
    draft = (
        "# My Title\n\nIntro text.\n\n[IMAGE: a diagram of the pipeline]\n\n"
        "More text.\n\n[IMAGE: a photo of a server room]\n"
    )
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=draft))

    result = asyncio.run(write_node({"topic": "RAG", "article_type": "technical"}))

    assert result["image_prompts"] == ["a diagram of the pipeline", "a photo of a server room"]
    assert "[IMAGE:" not in result["draft_content"]
    assert "insert image here: a diagram of the pipeline" in result["draft_content"]
    assert result["draft_title"] == "My Title"


@patch("app.agent.nodes.write._llm")
def test_write_node_with_no_markers_has_empty_image_prompts(mock_llm):
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="# Title\n\nJust text, no markers."))

    result = asyncio.run(write_node({"topic": "RAG", "article_type": "technical"}))

    assert result["image_prompts"] == []
