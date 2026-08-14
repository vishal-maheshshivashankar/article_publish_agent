import requests
from langchain_core.tools import tool

from app.config import settings


@tool
def github_search(query: str) -> str:
    """Search GitHub for real repositories/implementations related to a technical topic.

    Use this to verify that a library, framework, or technique you're about
    to write about actually exists and is maintained (recent activity, star
    count), and to find a canonical repo to link to. Don't reference
    tools/code without checking they're real first.
    """
    try:
        headers = {"Accept": "application/vnd.github+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        resp = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 5},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return f"No GitHub repositories found for '{query}'."
        return "\n\n".join(
            f"- {r['full_name']} ({r['stargazers_count']}★, updated {r['updated_at'][:10]})\n"
            f"  {r['html_url']}\n"
            f"  {(r.get('description') or '').strip()}"
            for r in items
        )
    except Exception as exc:  # noqa: BLE001
        return f"github_search failed for '{query}': {exc}"
