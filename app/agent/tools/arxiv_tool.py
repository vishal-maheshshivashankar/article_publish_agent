from langchain_core.tools import tool


@tool
def arxiv_search(query: str) -> str:
    """Search arXiv for academic papers relevant to an AI/ML/CS topic.

    Use this for research-heavy topics (RAG techniques, transformer variants,
    training methods, novel algorithms) to ground the article in actual
    published research instead of secondhand blog paraphrasing. Returns
    title, authors, publish date, an abstract snippet, and the paper URL for
    the top matches.
    """
    try:
        import arxiv

        client = arxiv.Client()
        search = arxiv.Search(query=query, max_results=4, sort_by=arxiv.SortCriterion.Relevance)
        results = list(client.results(search))
        if not results:
            return f"No arXiv papers found for '{query}'."
        return "\n\n".join(
            f"- {r.title} ({r.published.date()})\n"
            f"  Authors: {', '.join(a.name for a in r.authors[:4])}\n"
            f"  {r.entry_id}\n"
            f"  {r.summary[:400].replace(chr(10), ' ')}"
            for r in results
        )
    except Exception as exc:  # noqa: BLE001
        return f"arxiv_search failed for '{query}': {exc}"
