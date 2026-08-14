"""Regression test for a live-tested bug: some Telegram clients don't tag a
pasted "/write ..." message with a bot-command entity, so it never reaches
the CommandHandler and instead falls through to on_text's plain-text
handler. on_text now recovers that case explicitly instead of just saying
"I don't understand" for something that was clearly meant as a command.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.bot import telegram_bot

_OWNER_ID = 8559768453


def _make_update_context(text: str, user_id: int = _OWNER_ID):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = 111
    update.message.text = text
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    # Close the coroutine instead of running or leaving it unawaited.
    context.application.create_task = MagicMock(side_effect=lambda coro: coro.close())

    return update, context


def test_plain_pasted_write_command_is_recovered(monkeypatch):
    monkeypatch.setattr(telegram_bot.settings, "owner_telegram_id", _OWNER_ID)
    telegram_bot._awaiting_feedback.pop(_OWNER_ID, None)
    update, context = _make_update_context("/write RAG basics | tutorial")

    with patch.object(telegram_bot, "create_article", new=AsyncMock(return_value="abc123")):
        asyncio.run(telegram_bot.on_text(update, context))

    context.application.create_task.assert_called_once()
    update.message.reply_text.assert_not_called()


def test_write_command_recovery_is_case_insensitive_and_strips_prefix(monkeypatch):
    monkeypatch.setattr(telegram_bot.settings, "owner_telegram_id", _OWNER_ID)
    telegram_bot._awaiting_feedback.pop(_OWNER_ID, None)
    update, context = _make_update_context("/WRITE  RAG basics")

    captured = {}

    async def fake_create_article(user_id, topic, article_type):
        captured["topic"] = topic
        captured["article_type"] = article_type
        return "abc123"

    with patch.object(telegram_bot, "create_article", new=fake_create_article):
        asyncio.run(telegram_bot.on_text(update, context))

    assert captured["topic"] == "RAG basics"
    assert captured["article_type"] == "technical"


def test_unrelated_text_still_gets_fallback_message(monkeypatch):
    monkeypatch.setattr(telegram_bot.settings, "owner_telegram_id", _OWNER_ID)
    telegram_bot._awaiting_feedback.pop(_OWNER_ID, None)
    update, context = _make_update_context("hello there")

    asyncio.run(telegram_bot.on_text(update, context))

    update.message.reply_text.assert_awaited_once_with("Send /write <topic> to start a new article.")


def test_pending_revise_feedback_still_takes_priority_over_write_recovery(monkeypatch):
    monkeypatch.setattr(telegram_bot.settings, "owner_telegram_id", _OWNER_ID)
    telegram_bot._awaiting_feedback[_OWNER_ID] = "article-1"
    update, context = _make_update_context("make it shorter")

    with patch.object(telegram_bot, "_advance", new=AsyncMock()) as mock_advance:
        asyncio.run(telegram_bot.on_text(update, context))

    mock_advance.assert_awaited_once()
    assert _OWNER_ID not in telegram_bot._awaiting_feedback
