from langchain_core.tools import tool

from app.config import settings


@tool
def medium_search(query: str) -> str:
    """Search for existing, already-published Medium articles on this topic.

    Use this to see how the topic has already been covered elsewhere on
    Medium -- what angles exist, what's likely stale, and what professional
    technical writing on this topic actually reads like (tone, structure,
    depth) -- as a bar to match or exceed, not to copy. This is about the
    broader Medium ecosystem, not this blog's own history (use
    search_past_articles for that).
    """
    if not settings.tavily_api_key:
        # DuckDuckGo's site: operator and even plain domain-name queries were
        # tested live and returned unreliable/empty results (rate-limited or
        # simply not supported by that scraping-based library) -- unlike
        # web_search, there's no honest free fallback here, so this tool
        # says so rather than silently returning nothing useful.
        return "medium_search requires TAVILY_API_KEY to be set (no reliable free fallback); skipping."
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=settings.tavily_api_key)
        response = client.search(query, max_results=5, include_domains=["medium.com"])
        results = response.get("results", [])
        if not results:
            return f"No existing Medium articles found for '{query}'."
        return "\n\n".join(
            f"- {r['title']}\n  {r['url']}\n  {r.get('content', '')[:400]}" for r in results
        )
    except Exception as exc:  # noqa: BLE001
        return f"medium_search failed for '{query}': {exc}"
