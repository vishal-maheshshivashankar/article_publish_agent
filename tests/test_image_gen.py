from unittest.mock import MagicMock, patch

from app.agent.tools.image_gen import build_banner_prompt, build_illustration_prompt, generate_image


def test_build_banner_prompt_includes_title_and_topic():
    prompt = build_banner_prompt("My Title", "RAG")
    assert "My Title" in prompt
    assert "RAG" in prompt
    assert "no text" in prompt.lower()


def test_build_illustration_prompt_includes_description():
    prompt = build_illustration_prompt("a pipeline diagram")
    assert "a pipeline diagram" in prompt


@patch("app.agent.tools.image_gen.requests.get")
def test_generate_image_returns_bytes_on_success(mock_get):
    mock_get.return_value = MagicMock(status_code=200, content=b"fake-image-bytes")

    result = generate_image("a prompt")

    assert result == b"fake-image-bytes"
    url = mock_get.call_args.args[0]
    assert url.startswith("https://image.pollinations.ai/prompt/")


@patch("app.agent.tools.image_gen.requests.get")
def test_generate_image_url_encodes_the_prompt(mock_get):
    mock_get.return_value = MagicMock(status_code=200, content=b"bytes")

    generate_image("a prompt with spaces & symbols")

    url = mock_get.call_args.args[0]
    assert " " not in url
    assert "&" not in url.split("/prompt/")[1]


@patch("app.agent.tools.image_gen.requests.get")
def test_generate_image_returns_none_on_bad_status(mock_get):
    mock_get.return_value = MagicMock(status_code=500, content=b"")
    assert generate_image("a prompt") is None


@patch("app.agent.tools.image_gen.requests.get")
def test_generate_image_returns_none_on_network_error(mock_get):
    mock_get.side_effect = ConnectionError("boom")
    assert generate_image("a prompt") is None
