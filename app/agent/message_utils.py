def extract_text(content) -> str:
    """Normalize a LangChain message's .content to plain text.

    Newer Gemini responses (observed with gemini-3.5-flash-lite) return
    content as a list of block dicts (e.g. [{"type": "text", "text": "..."}])
    rather than a plain string, which broke code that assumed str -- caught
    by running the app for real, not by the test suite (mocks all used str).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(item["text"])
        return "\n".join(parts)
    return str(content) if content else ""
