from langgraph.types import interrupt

from app.agent.state import ArticleState


async def review_node(state: ArticleState) -> dict:
    """Must be async: when the graph runs via ainvoke() (the live bot),
    LangGraph offloads sync node functions to a thread-pool executor, and
    interrupt()'s context lookup doesn't survive that thread hop -- caught
    by running the app for real; graph.invoke() (sync, used in tests)
    doesn't hit this path since sync nodes run in-thread there."""
    decision = interrupt(
        {
            "type": "review",
            "article_id": state.get("article_id"),
            "topic": state.get("topic"),
            "title": state["draft_title"],
            "preview": state["draft_content"],
            "code_warnings": state.get("code_warnings", []),
            "sources": state.get("sources", []),
            "image_prompts": state.get("image_prompts", []),
        }
    )
    if decision.get("action") == "approve":
        return {"status": "approved"}
    return {
        "feedback": decision.get("feedback", ""),
        "revision_count": state.get("revision_count", 0) + 1,
        "status": "revising",
    }


def route_after_review(state: ArticleState) -> str:
    return "deliver" if state.get("status") == "approved" else "write"
