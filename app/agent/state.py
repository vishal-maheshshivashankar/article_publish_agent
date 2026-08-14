from typing import TypedDict


class ArticleState(TypedDict, total=False):
    telegram_user_id: int
    article_id: str
    topic: str
    article_type: str  # tutorial | opinion | technical | news

    research_notes: str
    sources: list[dict]

    draft_title: str
    draft_content: str
    code_warnings: list[str]
    suggested_tags: list[str]
    image_prompts: list[str]

    feedback: str
    revision_count: int
    status: str

    medium_url: str
    medium_post_id: str
    error: str
