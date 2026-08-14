from langchain_core.tools import tool


@tool
def scrape_url(url: str) -> str:
    """Fetch a specific URL (e.g. one found via web_search) and extract its main article text.

    Use this to read the full content of a promising search result before
    citing it, rather than relying on the short snippet alone.
    """
    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return f"Could not fetch {url}."
        text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        if not text:
            return f"Fetched {url} but could not extract readable content."
        return text[:4000]
    except Exception as exc:  # noqa: BLE001
        return f"scrape_url failed for '{url}': {exc}"
