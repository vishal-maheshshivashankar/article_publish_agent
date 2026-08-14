from app.agent.state import ArticleState


def _derive_tags(topic: str, article_type: str) -> list[str]:
    base = ["Artificial Intelligence", "Software Engineering"]
    extra = [w.strip().title() for w in topic.split()[:2] if len(w) > 2]
    tags = list(dict.fromkeys(base + extra + [article_type.title()]))
    return tags[:5]


def deliver_node(state: ArticleState) -> dict:
    """Terminal node: hands the approved article back for the human to publish.

    Medium removed self-serve API integration tokens for new integrations
    (confirmed against the live account this was built for), so there is no
    programmatic publish step -- the bot layer sends the final markdown to
    Telegram for the user to paste into Medium's editor themselves. This
    node just computes what the bot layer needs to present (suggested tags),
    since node functions stay Telegram-agnostic.
    """
    tags = _derive_tags(state["topic"], state.get("article_type", "technical"))
    return {"status": "delivered", "suggested_tags": tags}
