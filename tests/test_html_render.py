from app.agent.tools.html_render import render_html


def test_headers_become_real_heading_tags():
    html = render_html("Title", "# H1 Heading\n\n## H2 Heading\n")
    assert "<h1>H1 Heading</h1>" in html
    assert "<h2>H2 Heading</h2>" in html
    # The literal markdown syntax must not survive -- that's the whole point.
    assert "# H1 Heading" not in html


def test_bold_and_links_convert():
    html = render_html("Title", "Some **bold** text and a [link](https://example.com).")
    assert "<strong>bold</strong>" in html
    assert '<a href="https://example.com">link</a>' in html


def test_fenced_code_block_becomes_pre_code():
    html = render_html("Title", "```python\nprint('hi')\n```")
    assert "<pre>" in html
    assert "<code" in html
    assert "print(&#39;hi&#39;)" in html or "print('hi')" in html


def test_title_is_escaped_in_head():
    html = render_html("<script>alert(1)</script>", "body text")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_output_is_a_complete_html_document():
    html = render_html("Title", "Some text.")
    assert html.startswith("<!doctype html>")
    assert "<body>" in html
    assert "Some text." in html


def test_banner_image_embedded_as_data_uri_before_body():
    html = render_html("Title", "# Title\n\nBody text.", banner_image=b"fake-jpeg-bytes")
    assert 'src="data:image/jpeg;base64,' in html
    # Banner appears before the article body in document order.
    assert html.index('src="data:image/jpeg;base64,') < html.index("Body text.")


def test_no_banner_image_means_no_img_tag_for_it():
    html = render_html("Title", "Body text.", banner_image=None)
    assert "data:image/jpeg;base64," not in html


def test_illustration_placeholder_replaced_with_embedded_image():
    content = "Intro.\n\n*(insert image here: a diagram)*\n\nMore text."
    html = render_html("Title", content, illustration_images={"a diagram": b"fake-bytes"})

    assert "insert image here" not in html
    assert 'alt="a diagram"' in html
    assert "data:image/jpeg;base64," in html


def test_illustration_placeholder_without_matching_image_is_left_as_text():
    content = "Intro.\n\n*(insert image here: missing one)*\n\nMore text."
    html = render_html("Title", content, illustration_images={})

    assert "insert image here: missing one" in html


def test_multiple_illustrations_matched_by_description():
    content = "*(insert image here: first)*\n\n*(insert image here: second)*"
    html = render_html(
        "Title", content, illustration_images={"first": b"AAA", "second": b"BBB"}
    )

    import base64

    assert base64.b64encode(b"AAA").decode() in html
    assert base64.b64encode(b"BBB").decode() in html
