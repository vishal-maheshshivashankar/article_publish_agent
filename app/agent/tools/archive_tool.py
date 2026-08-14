from langchain_core.tools import tool

from app.storage.db import search_published_articles


@tool
def search_past_articles(query: str) -> str:
    """Search previously published articles on this blog for related prior coverage.

    Use this early in research to avoid duplicating a topic already covered,
    to reference or build on a previous article's angle, or to keep
    terminology consistent with earlier posts. Returns title, topic, and a
    short excerpt for each match. An empty result is normal for a new blog
    or a genuinely new topic -- it's not an error.
    """
    try:
        results = search_published_articles(query)
        if not results:
            return f"No previously published articles found matching '{query}'."
        return "\n\n".join(f"- {r['title']} ({r['topic']})\n  {r['excerpt']}" for r in results)
    except Exception as exc:  # noqa: BLE001
        return f"search_past_articles failed for '{query}': {exc}"
