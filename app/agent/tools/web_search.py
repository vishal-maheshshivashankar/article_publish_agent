from langchain_core.tools import tool

from app.config import settings


@tool
def web_search(query: str) -> str:
    """Search the web for current, general information on a topic.

    Returns titles, URLs, and snippets. Use this for recent developments,
    library/product announcements, and background that arxiv_search or
    wikipedia_lookup won't have yet. Prefer arxiv_search for anything
    paper-backed and wikipedia_lookup for settled background facts.
    """
    try:
        if settings.tavily_api_key:
            from tavily import TavilyClient

            client = TavilyClient(api_key=settings.tavily_api_key)
            response = client.search(query, max_results=5)
            results = response.get("results", [])
            if not results:
                return f"No web results for '{query}'."
            return "\n\n".join(
                f"- {r['title']}\n  {r['url']}\n  {r.get('content', '')[:400]}" for r in results
            )

        from duckduckgo_search import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        if not results:
            return f"No web results for '{query}'."
        return "\n\n".join(
            f"- {r['title']}\n  {r['href']}\n  {r.get('body', '')[:400]}" for r in results
        )
    except Exception as exc:  # noqa: BLE001
        return f"web_search failed for '{query}': {exc}"
