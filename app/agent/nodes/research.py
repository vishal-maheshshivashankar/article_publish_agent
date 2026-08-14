from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent

from app.agent.message_utils import extract_text
from app.agent.prompts import RESEARCH_SYSTEM_PROMPT
from app.agent.state import ArticleState
from app.agent.tools.archive_tool import search_past_articles
from app.agent.tools.arxiv_tool import arxiv_search
from app.agent.tools.github_tool import github_search
from app.agent.tools.medium_search import medium_search
from app.agent.tools.scrape_tool import scrape_url
from app.agent.tools.web_search import web_search
from app.agent.tools.wikipedia_tool import wikipedia_lookup
from app.config import settings

RESEARCH_TOOLS = [
    search_past_articles,
    medium_search,
    web_search,
    arxiv_search,
    wikipedia_lookup,
    scrape_url,
    github_search,
]

# System prompt is passed as the first message rather than via create_react_agent's
# prompt/state_modifier kwarg, whose name has shifted across langgraph versions.
_llm = ChatGoogleGenerativeAI(model=settings.gemini_model, google_api_key=settings.gemini_api_key, temperature=0.2)
_research_agent = create_react_agent(_llm, RESEARCH_TOOLS)


async def research_node(state: ArticleState, config: RunnableConfig | None = None) -> dict:
    """Streams the research sub-agent's own steps (not the outer graph's)
    rather than calling .ainvoke() on it, so a caller can pass an optional
    `on_progress(message: str)` async callback via
    config["configurable"]["on_progress"] and see each tool call as it
    happens -- the outer graph is still driven with plain ainvoke() by the
    caller, unaffected by this. See app/bot/telegram_bot.py for the
    Telegram-side consumer. Verified against a real call: create_react_agent
    emits per-step updates keyed "agent" (AIMessage, tool_calls non-empty
    while still calling tools) and "tools" (ToolMessage per call); the final
    answer is the "agent" update whose AIMessage has no tool_calls.
    """
    on_progress = ((config or {}).get("configurable") or {}).get("on_progress")

    prompt = (
        f"Topic: {state['topic']}\n"
        f"Article type: {state.get('article_type', 'technical')}\n"
        "Research this topic thoroughly for a high-level, provisional technical "
        "article aimed at software engineers. Use a mix of tools before answering."
    )

    sources: list[dict] = []
    final_text = ""

    async for chunk in _research_agent.astream(
        {"messages": [SystemMessage(content=RESEARCH_SYSTEM_PROMPT), HumanMessage(content=prompt)]},
        # >=5 tool calls (prompt requirement) is ~10-12 agent/tool steps plus the
        # final answer; comprehensive "all X" topics now research one tool call
        # per named item (see prompt), which can mean 15-20+ tool calls -- 32
        # was fine for a single-angle article but too tight for a full catalog.
        config={"recursion_limit": 60},
        stream_mode="updates",
    ):
        for update in chunk.values():
            for msg in (update or {}).get("messages") or []:
                if isinstance(msg, ToolMessage):
                    sources.append({"tool": msg.name, "output": str(msg.content)[:1000]})
                    if on_progress:
                        await on_progress(f"🔧 called {msg.name} ({len(sources)} so far)")
                elif isinstance(msg, AIMessage) and not msg.tool_calls:
                    final_text = extract_text(msg.content)

    return {
        "research_notes": final_text,
        "sources": sources,
        "status": "researched",
    }
