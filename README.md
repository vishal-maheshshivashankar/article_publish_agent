# Article Publish Agent

A LangGraph agent that researches and drafts technical articles (AI,
computer science, RAG, ML, software engineering) with a generated banner
image, triggered by a topic message on Telegram, then hands you the
finished article to publish on Medium yourself. See
[document-export-13-08-2026-20_49_24.md](document-export-13-08-2026-20_49_24.md)
for the full design doc.

## How it works

```
Telegram /write <topic>
        │
        ▼
  ┌───────────┐    (loops back with feedback)
  │  research │◄──────────────┐   live progress messages in Telegram
  └─────┬─────┘                │   as each tool gets called
        ▼                      │
   ┌─────────┐            ┌─────────┐
   │  write  │───────────►│ review  │──revise──┐
   └─────────┘            └────┬────┘          │
                          approve│              │
                                 ▼              │
                           ┌──────────┐         │
                           │ deliver  │         │
                           └────┬─────┘         │
                                ▼                │
                  Telegram: banner image +       │
                  full draft file + tags         │
                  (you paste it into Medium)     │
                                                  │
                    (write re-runs with feedback)┘
```

- **`research`**: a ReAct tool-calling agent (Gemini + 6 tools, see below)
  that gathers grounded material before writing anything. Streams its own
  progress (each tool call) back through the graph so the bot can show it
  live rather than going silent for a minute or two.
- **`write`**: drafts the article (a stronger Gemini tier than research
  uses — see "Models"), runs a syntax check on any Python code blocks, and
  extracts any `[IMAGE: ...]` markers the writer placed for illustrations.
- **`review`**: pauses the graph (`langgraph.types.interrupt`), the bot
  generates and sends a banner image (+ any illustrations) and the *full*
  draft as a file with Approve/Revise buttons. Revise loops back to `write`
  with your feedback; Approve continues to `deliver`.
- **`deliver`**: the graph's terminal node — computes suggested tags; the
  bot layer then sends the finished article as both an `.html` and a `.md`
  file (see "Publish method" below).

State is persisted per-article via LangGraph's `AsyncSqliteSaver`
(`thread_id = article_id`), so the process can restart mid-review without
losing the draft.

## Publish method: you paste it in

Medium removed self-serve API integration tokens from account settings (no
"Integration tokens" section under Settings → Security and apps anymore), so
there's no programmatic publish step. On approval, the bot sends **two
files**:

- `article.html` — a standalone, styled HTML rendering of the article.
  **Open this one in a browser and copy from there.** A browser puts real
  rich-text (HTML) on the clipboard when you copy selected rendered text;
  Telegram's own copy is always plain text. Pasting *rendered* HTML into
  Medium is what makes headings/bold/code carry over as real formatting —
  pasting the raw markdown text pastes literal `#`/`**` characters instead
  (confirmed live: this was the whole reason the `.html` file exists).
- `article.md` — plain-text markdown source, useful for platforms that
  *do* accept raw markdown paste (e.g. Dev.to), or as an archival copy.

Workflow:
1. Open the `.html` file in a browser (tap to download, then open it).
2. Select all → copy → paste into Medium's New story editor.
3. Add the suggested tags (from the caption) in the publish dialog, review,
   hit Publish.
4. Send `/published <article id> <medium url>` back to the bot.

That last step matters beyond bookkeeping: it's what populates the
`search_past_articles` archive (see "Memory" below) — without it, the agent
has no way to know the article is real and searchable for future research.

If Medium ever reinstates API tokens (or you get access some other way),
swap `app/agent/nodes/deliver.py` for a version that calls the Medium REST
API directly — the graph shape and everything upstream of it doesn't change.

## Images

Every article gets a generated banner/cover image; the writer can also flag
up to 2 spots in the article where an illustration would genuinely help
(via a `[IMAGE: description]` marker, extracted and stripped in `write_node`
— the final article never contains raw marker syntax, and Medium doesn't
understand it anyway). Both are sent as Telegram photos at the review step,
before you approve, so you can judge them alongside the text.

Images are generated via **Pollinations.ai** (`app/agent/tools/image_gen.py`)
— free, no API key, one HTTP GET per image. This replaced an earlier version
that used Gemini's own image model (`gemini-2.5-flash-image`, "Nano Banana"),
which worked well but cost $0.039/image; switching cut per-article cost by
roughly two-thirds (see "Cost" below) at some loss of consistency/quality
control versus Gemini's model. If image quality ever becomes a problem,
reverting `generate_image()` to call Gemini's image model is a contained
change — the function signature (prompt in, bytes-or-None out) is identical
either way, so nothing else in the codebase needs to change.

**Images are embedded in the delivered `.html`, not just sent as separate
Telegram photos.** An earlier version only sent them as photos — comparing
the generated output against a real published Medium article (side by side)
showed the images never actually made it into the file the user copies
from. `app/agent/tools/html_render.py` now embeds the banner and each
resolved illustration as a base64 `<img>` directly in the HTML, at delivery
time (`deliver`'s images are regenerated there rather than reusing the
review-step ones, to avoid persisting binary blobs in the LangGraph
checkpoint — Pollinations is free, so a second generation is the simpler
trade).

## Why these tools

This agent is meant to produce **high-level, provisional technical
articles** — the kind a working engineer would actually trust — so the
research toolset (`app/agent/tools/`) is deliberately not just "web search":

| Tool | Why |
| --- | --- |
| `search_past_articles` | Checked first: keyword search (SQLite FTS5) over this blog's own previously *published* articles, so new articles can build on or deliberately diverge from earlier coverage instead of repeating it. See "Memory" below. |
| `medium_search` | Checks what's already published on Medium about the topic — informs both duplication-avoidance and the writing bar to match/beat (see "Writing quality" below). Requires `TAVILY_API_KEY` (uses its `include_domains` filter); no reliable free equivalent — DuckDuckGo's `site:` operator and even plain domain-name queries were tested live and returned empty/unreliable results, so this tool says so explicitly rather than silently returning nothing when the key is missing. |
| `arxiv_search` | Grounds claims about new architectures/RAG techniques/training methods in actual papers, not blog paraphrasing. |
| `github_search` | Verifies a library/technique referenced in the article is real and maintained, and finds a canonical repo to link. |
| `wikipedia_lookup` | Settled definitions/background so the article doesn't waste words re-deriving established concepts. |
| `web_search` | Recent news/releases that arXiv/Wikipedia won't have (Tavily if `TAVILY_API_KEY` is set, DuckDuckGo otherwise — no key required to run). |
| `scrape_url` | Full-text read of a promising result before citing it, instead of trusting a two-line snippet. |
| `validate_python_blocks` | Not an LLM tool — a plain `ast.parse` syntax gate the `write` node runs on its own output, surfaced as warnings in the Telegram review card so broken code examples don't slip through unnoticed. |
| `image_gen` | Not an LLM tool — generates the banner/illustration images (see "Images" above). |

The research prompt requires at least 5 tool calls across 4+ different
tools per article (not just one search) — depth was a deliberate choice
after an early draft came back too shallow.

## Writing quality

Two things specifically target "reads as AI-generated" vs. "reads like a
person wrote it," both in `WRITE_SYSTEM_PROMPT`
([app/agent/prompts.py](app/agent/prompts.py)):

- Explicit anti-tells: vary sentence/paragraph length, avoid transition-word
  padding ("Furthermore," "Moreover," "In conclusion,") and cliché words
  ("leverage," "robust," "seamless," "delve," "landscape"), and take a
  position when the research supports one instead of a flat
  both-sides-have-merit summary.
- When `medium_search` (above) surfaces strong existing coverage of the
  topic, the writer is told to match or exceed its depth and specificity,
  not produce a shallower version of the same thing.

This is prompt-level guidance, not a hard filter — worth spot-checking
actual output quality over time rather than assuming the prompt alone
guarantees it.

## Models

Two Gemini tiers are used deliberately, not just one:

| Step | Model | Why |
| --- | --- | --- |
| `research` (many tool-calling round trips) | `gemini-3.5-flash-lite` | Cheap/fast fits a loop that calls the model 5+ times per article. |
| `write` (one call, produces the actual article) | `gemini-3.5-flash` | Prose quality matters more than per-call cost for the one call that becomes the deliverable. |

Both are read from env (`GEMINI_MODEL`, `GEMINI_WRITE_MODEL`) rather than
hardcoded — verify exact IDs against Google AI Studio's `ListModels` before
relying on a new one; `gemini-3.5-lite` (missing "flash") 404s, for example.

## Cost

Rough per-article estimate (not measured — see Google AI Studio's usage
dashboard for real numbers):

| Step | Estimate |
| --- | --- |
| Research (~5-8 tool-calling turns) | ~$0.007 |
| Write (~1500-word article) | ~$0.02 |
| Images (banner + 0-2 illustrations) | $0 (Pollinations.ai) |

**≈ $0.03/article**, or about **$0.90/month** at one article/day. A
`/revise` round adds another ~$0.02 (one more write call). The HTML
rendering step (`app/agent/tools/html_render.py`) is local, zero-cost.

## Memory

Two separate things are called "memory" in this system:

- **Per-article working memory** — LangGraph's `AsyncSqliteSaver` checkpointer
  ([app/agent/graph.py](app/agent/graph.py)) persists each article's graph
  state (research notes, draft, revision count) keyed by `thread_id =
  article_id`. This is what lets `/revise` resume a paused review correctly,
  even across a process restart.
- **Cross-article knowledge** — the `search_past_articles` tool
  ([app/agent/tools/archive_tool.py](app/agent/tools/archive_tool.py)) gives
  the `research` node keyword recall over everything previously *published*
  (backed by a SQLite FTS5 index populated in `mark_published()`, triggered
  by your `/published` command — see "Publish method" above). This is
  deliberately keyword search, not a vector store / embeddings-based
  semantic memory: at roughly 365 articles/year, exact-ish term matching is
  enough to catch duplicate topics, and it avoids adding an embeddings
  dependency or a framework-level memory store. (LangGraph does ship a
  cross-thread `Store` abstraction, but its only persistent backend needs
  Postgres — reintroducing infra this project deliberately dropped, so it
  wasn't used here.) If semantic recall ever turns out to matter, upgrading
  this one tool to embeddings is a contained change, not a rewrite.

## Telegram commands

| Command | What it does |
| --- | --- |
| `/write <topic> [\| type]` | Start a new article. `type` is `tutorial`\|`opinion`\|`technical`\|`news`, default `technical`. Also recovered from plain text if Telegram doesn't tag it as a command (common when pasted rather than typed) — see `on_text` in the bot. |
| *(inline buttons)* | Approve or Revise a delivered draft. |
| `/status [id]` | List recent articles, or look up one by id/prefix. |
| `/published <id> <url>` | Confirm you published it on Medium — records the URL and adds it to the searchable archive. |

While an article is running, the bot edits a single status message live
with each research tool call as it happens, rather than going silent.

## Project layout

```
app/
  config.py              # env-var settings (pydantic-settings)
  main.py                # entrypoint: init DB, open checkpointer, start bot
  agent/
    state.py              # ArticleState TypedDict
    prompts.py             # research + writer system prompts
    message_utils.py       # normalizes LLM .content (str or block-list) to text
    graph.py               # StateGraph wiring
    nodes/                 # research / write / review / deliver
    tools/                  # search_past_articles (archive), medium_search,
                            # web_search, arxiv, wikipedia, scrape, github,
                            # code_validator, image_gen, image_markers,
                            # html_render
  bot/
    telegram_bot.py        # commands, live progress, review flow, delivery
  storage/
    db.py                  # SQLite articles table + FTS5 archive (aiosqlite)
tests/                      # unit tests + interrupt/resume graph tests
```

## Setup

```bash
cp .env.example .env   # fill in the values below
python3 -m venv .venv && source .venv/bin/activate   # Python 3.11+ required, see note below
pip install -r requirements-dev.txt
pytest                 # 81 tests, no API keys required
```

**Python 3.11+ is required**, not just recommended: LangGraph's `interrupt()`
raises `RuntimeError: Called get_config outside of a runnable context` on
3.10 when the calling node runs inside an async graph invocation (which the
bot always uses) — caught by running the app for real on this machine's
default Python 3.10, fixed by rebuilding the venv on 3.13. The Dockerfile
already targets `python:3.12-slim`, so this only affects local dev venvs.

Required `.env` values:

| Variable | Where to get it |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | [@BotFather](https://t.me/BotFather) on Telegram |
| `OWNER_TELEGRAM_ID` | [@userinfobot](https://t.me/userinfobot) — the bot only responds to this id |
| `GEMINI_API_KEY` | Google AI Studio |
| `GEMINI_MODEL` / `GEMINI_WRITE_MODEL` | See "Models" above. Defaults are sensible; verify against `ListModels` before overriding. |
| `TAVILY_API_KEY` | Optional but recommended: better `web_search` quality than the DuckDuckGo fallback, and *required* for `medium_search` (no reliable free equivalent) |
| `GITHUB_TOKEN` | Optional, raises GitHub search rate limits |

No Medium credential is needed — see "Publish method" above. No image API
key is needed either — see "Images" above.

## Run locally

```bash
source .venv/bin/activate
python -m app.main
```

Then in Telegram: `/write Retrieval-Augmented Generation for code search`
(optionally `/write <topic> | tutorial`).

## Deploy (Oracle VM / any Docker host)

```bash
docker compose up -d --build
docker compose logs -f
```

No inbound ports are opened — the bot uses Telegram long-polling, so there's
nothing to put behind nginx/a load balancer/TLS termination. `./data/` is
bind-mounted for the SQLite file (article records, the FTS5 archive, and
LangGraph checkpoints); back it up if you care about article history
surviving a host rebuild.

**Rollback**: `docker compose down && docker compose up -d --build` against
a previous git commit/image tag — single container, no blue-green needed at
this scale.

**Monitoring**: structured logs go to stdout (`docker compose logs`); no
Prometheus/Grafana at this scale (see design doc §9 if that ever changes).

## Manual end-to-end check before trusting a deploy

Automated tests cover the tools, the DB layer, and the interrupt/resume
graph wiring, but not real Gemini calls. Before relying on a deploy, run one
article through by hand: `/write <topic>` → watch the live progress message
update as tools get called → review the banner image, any illustrations,
the draft, and any code warnings → Approve → confirm both files arrive →
open the `.html` one in a browser and paste into Medium (verify headings
render as headings, not literal `#`) → `/published <id> <url>` → confirm
`/status` shows it and a later `search_past_articles` call on a related
topic finds it.

## Known deviations from the original design doc

- **No Medium API call**: the design doc originally specified `POST
  /users/{userId}/posts` against Medium's API. Medium has since removed
  self-serve integration tokens from account settings, so `deliver` hands
  the article to Telegram instead — see "Publish method" above.
- **`OWNER_TELEGRAM_ID` gate**: not in the original doc, added because this
  bot handles your drafts and Medium workflow on command — every handler
  rejects messages from any other Telegram user.
- **Two Gemini tiers, not one**: split research (cheap) from writing
  (stronger) after the single-model version's articles read as shallow.
- **Images added**: banner + optional illustrations, generated via
  Pollinations.ai (free) rather than Gemini's paid image model, to keep
  per-article cost near-zero. No Mermaid-diagram feature survives from an
  earlier iteration — it was replaced outright by real generated images
  after user feedback that a flowchart-style diagram looked dated. Images
  are embedded directly in the delivered `.html` (base64), not only sent as
  Telegram photos — an earlier version did the latter only, and comparing
  against a real published Medium article showed the images never actually
  reached the file the user copies from.
- **`medium_search` added**: not in the original design at all — added
  after comparing generated output against a real published Medium article
  surfaced both the missing-images gap above and a "should reference what's
  already out there" ask. Requires `TAVILY_API_KEY`; deliberately has no
  DuckDuckGo fallback (tested live, unreliable/empty for domain-filtered
  queries) rather than silently degrading to a tool that returns nothing.
