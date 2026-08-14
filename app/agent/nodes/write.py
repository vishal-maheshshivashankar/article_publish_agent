from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.agent.message_utils import extract_text
from app.agent.prompts import WRITE_SYSTEM_PROMPT, build_write_prompt
from app.agent.state import ArticleState
from app.agent.tools.code_validator import collapse_blank_lines_in_code_blocks, validate_python_blocks
from app.agent.tools.image_markers import extract_image_markers, strip_image_markers
from app.config import settings


# Generous enough for a full-catalog article (~6000 words ≈ 8000 tokens) per
# the adaptive length rule in WRITE_SYSTEM_PROMPT, verified accepted by both
# providers rather than assumed -- DeepSeek's default cap is well under this.
_MAX_OUTPUT_TOKENS = 8192


def _build_write_llm():
    if settings.write_provider == "deepseek":
        # DeepSeek's API is OpenAI-compatible -- ChatOpenAI with a swapped
        # base_url, no separate SDK needed. Confirmed against DeepSeek's own
        # docs before wiring in.
        return ChatOpenAI(
            model=settings.deepseek_model,
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
            temperature=0.5,
            max_tokens=_MAX_OUTPUT_TOKENS,
        )
    return ChatGoogleGenerativeAI(
        model=settings.gemini_write_model,
        google_api_key=settings.gemini_api_key,
        temperature=0.5,
        max_output_tokens=_MAX_OUTPUT_TOKENS,
    )


_llm = _build_write_llm()


async def write_node(state: ArticleState) -> dict:
    user_prompt = build_write_prompt(
        topic=state["topic"],
        article_type=state.get("article_type", "technical"),
        research_notes=state.get("research_notes", ""),
        feedback=state.get("feedback"),
    )
    response = await _llm.ainvoke(
        [SystemMessage(content=WRITE_SYSTEM_PROMPT), HumanMessage(content=user_prompt)]
    )
    content = extract_text(response.content)
    title = content.splitlines()[0].lstrip("# ").strip() if content else state["topic"]

    # Extract before stripping: image_prompts drives what gets generated,
    # then draft_content must never contain raw [IMAGE: ...] marker syntax
    # (it's persisted to state/DB and is what actually ships to Medium).
    image_prompts = extract_image_markers(content)
    content = strip_image_markers(content)
    content = collapse_blank_lines_in_code_blocks(content)
    warnings = validate_python_blocks(content)

    return {
        "draft_title": title,
        "draft_content": content,
        "code_warnings": warnings,
        "image_prompts": image_prompts,
        "feedback": "",
        "status": "drafted",
    }
