import asyncio
import html
import io
import logging
import re

from langgraph.types import Command
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputFile, Message, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.agent.tools.html_render import render_html
from app.agent.tools.image_gen import build_banner_prompt, build_illustration_prompt, generate_image
from app.config import settings
from app.storage.db import (
    create_article,
    get_article,
    get_article_by_prefix,
    list_recent_articles,
    mark_published,
    update_article,
)

logger = logging.getLogger(__name__)

ARTICLE_TYPES = {"tutorial", "opinion", "technical", "news"}

# telegram_user_id -> article_id currently awaiting free-text revision feedback.
# Single-process, single-owner bot, so plain in-memory state is fine here.
_awaiting_feedback: dict[int, str] = {}

_PROGRESS_HISTORY_LINES = 15


def _owner_only(handler):
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None or update.effective_user.id != settings.owner_telegram_id:
            if update.message:
                await update.message.reply_text("This bot is private.")
            return
        await handler(update, context)

    return wrapped


def _graph(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["graph"]


def _slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug or "article"


def _starting_line(payload) -> str:
    if isinstance(payload, Command):
        action = (payload.resume or {}).get("action")
        if action == "approve":
            return "✅ Finalizing..."
        if action == "revise":
            return "✏️ Revising..."
        return "Working..."
    return "🔍 Starting research..."


def _make_progress_reporter(status_message: Message):
    """Returns an async on_progress(line) callback that appends to and
    re-renders a single Telegram message, so the chat doesn't get spammed
    with one message per tool call. Edits are best-effort: a failed edit
    (rate limit, "message not modified", network blip) just means one
    progress update is missed, not a graph failure -- research/write always
    complete regardless of whether anyone is watching this message.
    """
    lines: list[str] = [status_message.text or ""]

    async def on_progress(line: str) -> None:
        lines.append(line)
        text = "\n".join(lines[-_PROGRESS_HISTORY_LINES:])
        try:
            await status_message.edit_text(text[:4000])
        except TelegramError:
            pass

    return on_progress


async def _advance(context: ContextTypes.DEFAULT_TYPE, chat_id: int, article_id: str, payload) -> None:
    """Run the graph forward (start or resume) until it interrupts or finishes."""
    graph = _graph(context)
    status_message = await context.bot.send_message(chat_id, _starting_line(payload))
    on_progress = _make_progress_reporter(status_message)
    config = {"configurable": {"thread_id": article_id, "on_progress": on_progress}}

    try:
        result = await graph.ainvoke(payload, config=config)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Graph run failed for article %s", article_id)
        await update_article(article_id, status="failed", error=str(exc))
        await context.bot.send_message(chat_id, f"Something went wrong while working on this article: {exc}")
        return

    interrupts = result.get("__interrupt__") if isinstance(result, dict) else None
    if interrupts:
        logger.info("article %s awaiting review", article_id)
        await _send_review(context, chat_id, article_id, interrupts[0].value)
        return

    if result.get("status") == "delivered":
        logger.info("article %s delivered", article_id)
        await update_article(
            article_id, status="delivered", content=result.get("draft_content"), title=result.get("draft_title")
        )
        await _send_final_article(context, chat_id, article_id, result)
    elif result.get("status") == "failed":
        logger.error("article %s failed: %s", article_id, result.get("error"))
        await update_article(article_id, status="failed", error=result.get("error"))
        await context.bot.send_message(chat_id, f"Something went wrong: {result.get('error')}")


async def _generate_review_images(title: str, topic: str, image_prompts: list[str]) -> tuple[bytes | None, list[bytes | None]]:
    """Runs banner + illustration generation concurrently (each is a blocking
    network call, hence to_thread) to keep total review latency down to
    ~one call's worth of time rather than serial."""
    banner_task = asyncio.to_thread(generate_image, build_banner_prompt(title, topic))
    illustration_tasks = [
        asyncio.to_thread(generate_image, build_illustration_prompt(desc)) for desc in image_prompts
    ]
    results = await asyncio.gather(banner_task, *illustration_tasks)
    return results[0], list(results[1:])


async def _send_review(context: ContextTypes.DEFAULT_TYPE, chat_id: int, article_id: str, payload: dict) -> None:
    title = payload.get("title", "Draft")
    content = payload.get("preview", "")
    warnings = payload.get("code_warnings") or []
    topic = payload.get("topic") or title
    image_prompts = payload.get("image_prompts") or []

    await update_article(
        article_id,
        status="awaiting_review",
        title=title,
        content=content,
        sources=payload.get("sources", []),
    )

    banner_bytes, illustration_bytes_list = await _generate_review_images(title, topic, image_prompts)
    if banner_bytes:
        try:
            await context.bot.send_photo(
                chat_id,
                photo=io.BytesIO(banner_bytes),
                caption="Suggested Medium banner/cover image — upload this first when creating the story",
            )
        except TelegramError:
            logger.warning("failed to send banner image for article %s", article_id)
    for description, image_bytes in zip(image_prompts, illustration_bytes_list):
        if not image_bytes:
            continue
        try:
            await context.bot.send_photo(chat_id, photo=io.BytesIO(image_bytes), caption=f"Illustration: {description}")
        except TelegramError:
            logger.warning("failed to send illustration image for article %s", article_id)

    warning_text = ""
    if warnings:
        warning_text = "\n⚠️ Code warnings:\n" + "\n".join(f"- {w}" for w in warnings)

    # Full content goes as a file, not a truncated inline message -- Telegram
    # messages cap at 4096 chars, well under most article lengths, and a
    # truncated draft is a bad basis for an approve/revise decision.
    filename = f"{_slugify(title)}-draft.md"
    document = InputFile(io.BytesIO(content.encode("utf-8")), filename=filename)
    caption = f"<b>{html.escape(title)}</b>{html.escape(warning_text)}\n\nFull draft attached — review it, then:"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Approve", callback_data=f"approve:{article_id}"),
                InlineKeyboardButton("Revise", callback_data=f"revise:{article_id}"),
            ]
        ]
    )
    await context.bot.send_document(
        chat_id, document=document, caption=caption[:1024], parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def _send_final_article(context: ContextTypes.DEFAULT_TYPE, chat_id: int, article_id: str, result: dict) -> None:
    """Medium has no self-serve API token anymore, so this hands the finished
    article to the human to paste in and publish themselves, rather than
    calling a publish API. See README "Publish method" for why."""
    title = result.get("draft_title") or "Article"
    content = result.get("draft_content") or ""
    tags = result.get("suggested_tags") or []
    topic = result.get("topic") or title
    image_prompts = result.get("image_prompts") or []
    short_id = article_id[:8]

    # Regenerated here rather than reusing the review-step images: those
    # were never persisted (image bytes in LangGraph state would bloat the
    # SQLite checkpoint with binary blobs), and Pollinations is free, so a
    # second generation is the simpler trade. The delivered image may look
    # slightly different from the one previewed at review as a result.
    banner_bytes, illustration_bytes_list = await _generate_review_images(title, topic, image_prompts)
    illustration_images = {
        desc: img for desc, img in zip(image_prompts, illustration_bytes_list) if img is not None
    }

    md_document = InputFile(io.BytesIO(content.encode("utf-8")), filename=f"{_slugify(title)}.md")
    html_document = InputFile(
        io.BytesIO(render_html(title, content, banner_bytes, illustration_images).encode("utf-8")),
        filename=f"{_slugify(title)}.html",
    )

    caption = (
        f"Ready to publish: <b>{html.escape(title)}</b>\n\n"
        f"Suggested tags: {html.escape(', '.join(tags))}\n\n"
        "1. Open the attached .html file in a browser (tap to download, then open it) — "
        "the banner and any illustration images are embedded in it\n"
        "2. Select all → copy → paste into Medium's New story editor. Copying from a "
        "rendered page (not the raw .md) is what makes headings/bold/code/images carry "
        "over instead of pasting as literal # and ** characters\n"
        "3. Add the tags above in the publish dialog, review, hit Publish\n"
        f"4. Send <code>/published {short_id} &lt;medium url&gt;</code> so I can reference "
        "this article when researching future ones\n\n"
        "(.md attached too, as plain-text source — useful for other platforms that do "
        "accept raw markdown, e.g. Dev.to)"
    )
    await context.bot.send_document(chat_id, document=html_document, caption=caption, parse_mode=ParseMode.HTML)
    await context.bot.send_document(chat_id, document=md_document)


@_owner_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Send /write <topic> to research and draft a technical article.\n"
        "Optionally set the type: /write <topic> | tutorial|opinion|technical|news\n"
        "Use /status to see recent articles.\n"
        "After you publish a delivered article on Medium yourself, send "
        "/published <id> <url> so I can reference it later."
    )


async def _start_article(update: Update, context: ContextTypes.DEFAULT_TYPE, raw: str) -> None:
    raw = raw.strip()
    if not raw:
        await update.message.reply_text("Usage: /write <topic> [| tutorial|opinion|technical|news]")
        return

    if "|" in raw:
        topic, _, article_type = raw.partition("|")
        topic = topic.strip()
        article_type = article_type.strip().lower()
        if article_type not in ARTICLE_TYPES:
            article_type = "technical"
    else:
        topic, article_type = raw, "technical"

    article_id = await create_article(update.effective_user.id, topic, article_type)
    logger.info("article %s created: topic=%r type=%s", article_id, topic, article_type)

    initial_state = {
        "telegram_user_id": update.effective_user.id,
        "article_id": article_id,
        "topic": topic,
        "article_type": article_type,
        "revision_count": 0,
    }
    context.application.create_task(_advance(context, update.effective_chat.id, article_id, initial_state))


@_owner_only
async def write(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args) if context.args else ""
    await _start_article(update, context, raw)


@_owner_only
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        article = await get_article_by_prefix(context.args[0])
        articles = [article] if article else []
    else:
        articles = await list_recent_articles(update.effective_user.id)

    if not articles:
        await update.message.reply_text("No articles found.")
        return

    lines = []
    for a in articles:
        if not a:
            continue
        line = f"{a['id'][:8]}  {a['status']:<15}  {a['topic']}"
        if a.get("medium_url"):
            line += f"\n  -> {a['medium_url']}"
        lines.append(line)
    await update.message.reply_text("\n".join(lines))


@_owner_only
async def published(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /published <article id from /status> <medium url>")
        return

    prefix, url = context.args[0], context.args[1]
    article = await get_article_by_prefix(prefix)
    if not article:
        await update.message.reply_text(f"No article found matching '{prefix}'. Check /status for the id.")
        return

    await mark_published(article["id"], url)
    logger.info("article %s marked published: %s", article["id"], url)
    await update.message.reply_text(
        f"Marked “{article['title'] or article['topic']}” as published. "
        "I'll be able to reference it when researching future articles."
    )


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query.from_user.id != settings.owner_telegram_id:
        await query.answer("This bot is private.", show_alert=True)
        return
    await query.answer()

    action, _, article_id = query.data.partition(":")
    if action == "approve":
        await query.edit_message_reply_markup(reply_markup=None)
        await _advance(context, query.message.chat_id, article_id, Command(resume={"action": "approve"}))
    elif action == "revise":
        await query.edit_message_reply_markup(reply_markup=None)
        _awaiting_feedback[query.from_user.id] = article_id
        await context.bot.send_message(query.message.chat_id, "What should change? Send your feedback as a message.")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id != settings.owner_telegram_id:
        return

    text = update.message.text or ""

    article_id = _awaiting_feedback.pop(user_id, None)
    if article_id:
        await _advance(
            context,
            update.effective_chat.id,
            article_id,
            Command(resume={"action": "revise", "feedback": text}),
        )
        return

    # This handler only fires for text Telegram did NOT tag as a command
    # (filters.TEXT & ~filters.COMMAND) -- which includes "/write ..." typed
    # or pasted in a way some clients don't tag as a bot-command entity.
    # Recover that case explicitly instead of treating it as unrecognized input.
    stripped = text.strip()
    if stripped.lower().startswith("/write"):
        await _start_article(update, context, stripped[len("/write") :])
        return

    await update.message.reply_text("Send /write <topic> to start a new article.")


async def run_bot(graph) -> None:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["graph"] = graph

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("write", write))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("published", published))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

    async with app:
        await app.start()
        await app.updater.start_polling()
        logger.info("Bot started (long polling). Owner id: %s", settings.owner_telegram_id)
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()
