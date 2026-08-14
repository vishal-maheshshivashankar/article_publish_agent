import base64
import html as html_module

import markdown

from app.agent.tools.image_markers import PLACEHOLDER_RE

_CSS = """
body { font-family: -apple-system, Georgia, 'Times New Roman', serif; max-width: 700px;
       margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #1a1a1a; }
h1, h2, h3 { font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif; line-height: 1.25; }
h1 { font-size: 2em; margin-bottom: 0.3em; }
h2 { margin-top: 1.8em; }
pre { background: #f6f6f6; padding: 1em; overflow-x: auto; border-radius: 4px; }
code { font-family: 'SF Mono', Menlo, Consolas, monospace; font-size: 0.9em; }
pre code { font-size: 0.85em; }
p code { background: #f0f0f0; padding: 0.15em 0.35em; border-radius: 3px; }
blockquote { border-left: 3px solid #ccc; margin-left: 0; padding-left: 1em; color: #555; }
img { max-width: 100%; border-radius: 6px; }
"""


def _img_tag(image_bytes: bytes, alt: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f'<img src="data:image/jpeg;base64,{b64}" alt="{html_module.escape(alt)}" />'


def _embed_illustrations(content_markdown: str, illustration_images: dict[str, bytes]) -> str:
    """Swaps each "*(insert image here: description)*" placeholder (see
    strip_image_markers) for a real embedded <img>, matched by description
    text. A placeholder with no matching image (generation failed, or none
    was requested) is left as the text note rather than silently dropped."""

    def _replace(match):
        description = match.group(1)
        image_bytes = illustration_images.get(description)
        return _img_tag(image_bytes, description) if image_bytes else match.group(0)

    return PLACEHOLDER_RE.sub(_replace, content_markdown)


def render_html(
    title: str,
    content_markdown: str,
    banner_image: bytes | None = None,
    illustration_images: dict[str, bytes] | None = None,
) -> str:
    """Standalone HTML for the user to open in a browser and copy from.

    The point isn't styling for its own sake -- it's that a browser puts
    real rich-text (HTML) on the clipboard when you copy selected rendered
    text, whereas copying plain text (from Telegram, a .md file, etc.)
    never does. Medium's paste handler only preserves headings/bold/code
    -- and images -- when it receives that rich-text clipboard data.

    Images are embedded as base64 data URIs (self-contained, one file) --
    matches an earlier gap found comparing against a real published Medium
    article: the generated banner/illustrations were only ever sent as
    separate Telegram photos, never actually part of the file the user
    copies from, so they never made it into the pasted result.
    """
    body_markdown = _embed_illustrations(content_markdown, illustration_images or {})
    body_html = markdown.markdown(body_markdown, extensions=["fenced_code", "tables", "sane_lists"])
    banner_html = _img_tag(banner_image, f"{title} banner") if banner_image else ""
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{html_module.escape(title)}</title>"
        f"<style>{_CSS}</style></head><body>{banner_html}{body_html}</body></html>"
    )
