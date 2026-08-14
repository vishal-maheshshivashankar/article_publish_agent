from urllib.parse import quote

import requests


def build_banner_prompt(title: str, topic: str) -> str:
    return (
        f'A clean, professional cover/banner illustration for a technical blog article '
        f'titled "{title}" about {topic}. Modern tech-editorial style, an abstract or '
        f"conceptual visual metaphor for the topic -- not a literal screenshot or diagram. "
        f"No text or words anywhere in the image. Wide aspect ratio suitable for a blog header."
    )


def build_illustration_prompt(description: str) -> str:
    return (
        f"A clean, simple illustrative image for a technical blog article, showing: "
        f"{description}. Modern, minimal, tech-editorial style. No text or words in the image."
    )


def generate_image(prompt: str, timeout: float = 30.0) -> bytes | None:
    """Generate an image via Pollinations.ai -- free, no API key, no per-image
    cost (unlike Gemini's image model, which this replaced specifically to
    cut cost: verified against a live request before switching). Returns
    image bytes, or None on any failure (network, bad status, service down)
    -- callers should degrade gracefully (skip the image) rather than fail
    the whole article over a missing illustration. Synchronous/blocking
    network call -- run via asyncio.to_thread from async code.
    """
    try:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            return resp.content
        return None
    except Exception:  # noqa: BLE001
        return None
