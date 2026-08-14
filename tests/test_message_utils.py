from app.agent.message_utils import extract_text


def test_plain_string_passes_through():
    assert extract_text("hello world") == "hello world"


def test_list_of_text_blocks_is_joined():
    content = [{"type": "text", "text": "part one"}, {"type": "text", "text": "part two"}]
    assert extract_text(content) == "part one\npart two"


def test_list_of_plain_strings_is_joined():
    assert extract_text(["a", "b"]) == "a\nb"


def test_non_text_blocks_are_skipped():
    content = [{"type": "text", "text": "kept"}, {"type": "tool_use", "id": "x"}]
    assert extract_text(content) == "kept"


def test_empty_list_returns_empty_string():
    assert extract_text([]) == ""


def test_none_returns_empty_string():
    assert extract_text(None) == ""
