from app.agent.nodes.deliver import _derive_tags, deliver_node


def test_derive_tags_caps_at_five():
    tags = _derive_tags("Retrieval Augmented Generation for Code Search", "tutorial")
    assert len(tags) <= 5
    assert "Artificial Intelligence" in tags
    assert "Tutorial" in tags


def test_derive_tags_has_no_duplicates():
    tags = _derive_tags("AI Software", "technical")
    assert len(tags) == len(set(tags))


def test_deliver_node_sets_delivered_status():
    result = deliver_node({"topic": "RAG", "article_type": "technical"})
    assert result["status"] == "delivered"
    assert isinstance(result["suggested_tags"], list)
