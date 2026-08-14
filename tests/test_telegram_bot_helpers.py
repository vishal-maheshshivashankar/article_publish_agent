import asyncio
from unittest.mock import AsyncMock, patch

from langgraph.types import Command
from telegram.error import TelegramError

from app.bot import telegram_bot
from app.bot.telegram_bot import _generate_review_images, _make_progress_reporter, _slugify, _starting_line


def test_starting_line_for_initial_dict_payload():
    assert "research" in _starting_line({"topic": "RAG"}).lower()


def test_starting_line_for_approve_resume():
    assert "final" in _starting_line(Command(resume={"action": "approve"})).lower()


def test_starting_line_for_revise_resume():
    assert "revis" in _starting_line(Command(resume={"action": "revise"})).lower()


def test_starting_line_for_unknown_resume_action():
    assert _starting_line(Command(resume={"action": "something_else"})) == "Working..."


def test_slugify_basic():
    assert _slugify("Python Design Patterns: In Detail!") == "python-design-patterns-in-detail"


def test_slugify_empty_falls_back():
    assert _slugify("!!!") == "article"


def test_progress_reporter_accumulates_and_edits():
    message = AsyncMock()
    message.text = "start"
    on_progress = _make_progress_reporter(message)

    asyncio.run(on_progress("step one"))
    asyncio.run(on_progress("step two"))

    assert message.edit_text.await_count == 2
    last_text = message.edit_text.await_args.args[0]
    assert "step one" in last_text
    assert "step two" in last_text


def test_progress_reporter_swallows_telegram_errors():
    message = AsyncMock()
    message.text = "start"
    message.edit_text.side_effect = TelegramError("rate limited")
    on_progress = _make_progress_reporter(message)

    asyncio.run(on_progress("should not raise"))


def test_generate_review_images_pairs_illustrations_with_prompts_in_order():
    def fake_generate(prompt: str) -> bytes:
        return prompt.encode()

    with patch.object(telegram_bot, "generate_image", side_effect=fake_generate):
        banner, illustrations = asyncio.run(
            _generate_review_images("Title", "Topic", ["desc one", "desc two"])
        )

    assert banner is not None
    assert len(illustrations) == 2
    assert b"desc one" in illustrations[0]
    assert b"desc two" in illustrations[1]


def test_generate_review_images_handles_no_illustrations():
    with patch.object(telegram_bot, "generate_image", return_value=b"banner-bytes"):
        banner, illustrations = asyncio.run(_generate_review_images("Title", "Topic", []))

    assert banner == b"banner-bytes"
    assert illustrations == []


def test_generate_review_images_tolerates_partial_failures():
    def fake_generate(prompt: str):
        return None if "fail" in prompt else b"ok"

    with patch.object(telegram_bot, "generate_image", side_effect=fake_generate):
        banner, illustrations = asyncio.run(
            _generate_review_images("Title", "Topic", ["a fail case", "a good case"])
        )

    assert illustrations[0] is None
    assert illustrations[1] == b"ok"
