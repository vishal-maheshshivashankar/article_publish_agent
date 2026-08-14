"""Exercises the trickiest part of the graph -- interrupt/Command(resume=...)
human-in-the-loop wiring -- with a stub write node so it runs with no API
keys or network calls. The real research/write nodes are only covered by
the manual end-to-end checklist in the README, since they call Gemini
directly. deliver_node has no external I/O (the bot layer handles actually
sending the file to Telegram), so it's exercised for real here.

Uses graph.ainvoke() throughout, matching app/bot/telegram_bot.py's actual
call pattern -- NOT graph.invoke(). This matters: on Python < 3.11,
interrupt() inside an async-context node raises
"Called get_config outside of a runnable context" even though the exact
same node works fine under sync invoke() (see app/agent/nodes/review.py,
which is async specifically because LangGraph offloads sync nodes to a
thread-pool executor under ainvoke(), which breaks interrupt() differently
again). review_node is now async-only, so sync invoke() no longer works for
it at all -- which is fine, since production never calls it synchronously.
Requires Python 3.11+ (the Dockerfile already targets python:3.12-slim).
"""

import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agent.nodes.deliver import deliver_node
from app.agent.nodes.review import review_node, route_after_review
from app.agent.state import ArticleState


def _stub_write(state: ArticleState) -> dict:
    feedback = state.get("feedback", "")
    suffix = f" (revised: {feedback})" if feedback else ""
    return {"draft_title": "Stub Title", "draft_content": f"draft content{suffix}", "code_warnings": []}


def _build_test_graph():
    graph = StateGraph(ArticleState)
    graph.add_node("write", _stub_write)
    graph.add_node("review", review_node)
    graph.add_node("deliver", deliver_node)
    graph.add_edge(START, "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", route_after_review, {"write": "write", "deliver": "deliver"})
    graph.add_edge("deliver", END)
    return graph.compile(checkpointer=MemorySaver())


def test_approve_flow_delivers():
    graph = _build_test_graph()
    config = {"configurable": {"thread_id": "t1"}}

    async def run():
        result = await graph.ainvoke(
            {"topic": "RAG", "article_type": "technical", "revision_count": 0}, config=config
        )
        assert "__interrupt__" in result
        assert result["__interrupt__"][0].value["title"] == "Stub Title"

        result = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
        assert result["status"] == "delivered"
        assert "Artificial Intelligence" in result["suggested_tags"]

    asyncio.run(run())


def test_revise_then_approve_flow():
    graph = _build_test_graph()
    config = {"configurable": {"thread_id": "t2"}}

    async def run():
        result = await graph.ainvoke(
            {"topic": "RAG", "article_type": "technical", "revision_count": 0}, config=config
        )
        assert "__interrupt__" in result

        result = await graph.ainvoke(
            Command(resume={"action": "revise", "feedback": "add more detail"}), config=config
        )
        assert "__interrupt__" in result
        assert "add more detail" in result["__interrupt__"][0].value["preview"]

        result = await graph.ainvoke(Command(resume={"action": "approve"}), config=config)
        assert result["status"] == "delivered"

    asyncio.run(run())


def test_route_after_review_defaults_to_write():
    assert route_after_review({"status": "revising"}) == "write"
    assert route_after_review({"status": "approved"}) == "deliver"
