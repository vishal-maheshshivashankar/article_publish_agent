import re

_IMAGE_MARKER_RE = re.compile(r"^\[IMAGE:\s*(.+?)\]\s*$", re.MULTILINE)

# Matches what strip_image_markers() produces, so html_render.py can find
# and replace each placeholder with a real embedded image at delivery time.
PLACEHOLDER_RE = re.compile(r"\*\(insert image here: (.+?)\)\*")


def extract_image_markers(markdown: str, limit: int = 2) -> list[str]:
    """Return the first `limit` [IMAGE: description] marker descriptions the
    writer placed in the draft (see WRITE_SYSTEM_PROMPT), capping how many
    illustration images get generated per article."""
    return _IMAGE_MARKER_RE.findall(markdown)[:limit]


def strip_image_markers(markdown: str) -> str:
    """Replace every [IMAGE: ...] marker with a plain-text placement note,
    always as its own paragraph.

    Applied to ALL markers, not just the first `limit` -- raw marker syntax
    must never reach the delivered article regardless of how many the
    writer included, since Medium wouldn't understand it. The blank lines
    around the replacement are forced explicitly (then excess collapsed)
    rather than relying on whatever whitespace the writer happened to leave
    around the marker -- without this, a marker with no blank line before
    the next sentence merges into that sentence's paragraph when rendered
    (observed live: "*(insert image here: ...)*\\nThis isolation makes..."
    landed in one <p>, not two).
    """
    replaced = _IMAGE_MARKER_RE.sub(lambda m: f"\n\n*(insert image here: {m.group(1)})*\n\n", markdown)
    return re.sub(r"\n{3,}", "\n\n", replaced)
