from app.agent.tools.image_markers import extract_image_markers, strip_image_markers


def test_extract_image_markers_finds_all_up_to_limit():
    markdown = "text\n[IMAGE: a diagram of X]\nmore\n[IMAGE: a photo of Y]\nend"
    assert extract_image_markers(markdown) == ["a diagram of X", "a photo of Y"]


def test_extract_image_markers_respects_limit():
    markdown = "[IMAGE: one]\n[IMAGE: two]\n[IMAGE: three]"
    assert extract_image_markers(markdown, limit=2) == ["one", "two"]


def test_extract_image_markers_returns_empty_when_none():
    assert extract_image_markers("no markers here") == []


def test_strip_image_markers_replaces_all_regardless_of_limit():
    markdown = "a\n[IMAGE: one]\nb\n[IMAGE: two]\nc\n[IMAGE: three]\nd"
    result = strip_image_markers(markdown)
    assert "[IMAGE:" not in result
    assert "*(insert image here: one)*" in result
    assert "*(insert image here: two)*" in result
    assert "*(insert image here: three)*" in result


def test_strip_image_markers_leaves_other_text_untouched():
    markdown = "# Title\n\nSome text.\n[IMAGE: a chart]\n\nMore text."
    result = strip_image_markers(markdown)
    assert "# Title" in result
    assert "Some text." in result
    assert "More text." in result


def test_strip_image_markers_forces_paragraph_break_even_with_no_blank_line():
    """Regression test: a marker immediately followed by the next sentence
    with no blank line used to render as one merged <p> when converted to
    HTML, e.g. "*(insert image here: X)*\\nThis isolation makes..." in a
    single paragraph -- caught by comparing generated output against a real
    published article."""
    markdown = "Some text.\n[IMAGE: a diagram]\nThis isolation makes it testable."

    result = strip_image_markers(markdown)

    assert "\n\n*(insert image here: a diagram)*\n\n" in result
    # Explicitly render through markdown to confirm two separate paragraphs.
    import markdown as md

    html = md.markdown(result)
    assert html.count("<p>") == 3


def test_strip_image_markers_does_not_produce_excess_blank_lines():
    markdown = "Some text.\n\n[IMAGE: a diagram]\n\nMore text."
    result = strip_image_markers(markdown)
    assert "\n\n\n" not in result
