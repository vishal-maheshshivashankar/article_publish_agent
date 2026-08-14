from langchain_core.tools import tool


@tool
def wikipedia_lookup(query: str) -> str:
    """Look up foundational, well-established background on a term or concept.

    Good for terminology, history, and settled facts. Wikipedia won't have
    anything on very recent or niche developments -- pair with web_search or
    arxiv_search for those.
    """
    try:
        import wikipedia

        try:
            page = wikipedia.page(query, auto_suggest=True)
        except wikipedia.exceptions.DisambiguationError as exc:
            page = wikipedia.page(exc.options[0], auto_suggest=False)
        return f"{page.title}\n{page.url}\n\n{page.summary[:1500]}"
    except Exception as exc:  # noqa: BLE001
        return f"wikipedia_lookup failed for '{query}': {exc}"
