from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from app.agent.nodes.write import _build_write_llm
from app.config import settings


def test_defaults_to_gemini(monkeypatch):
    monkeypatch.setattr(settings, "write_provider", "gemini")
    llm = _build_write_llm()
    assert isinstance(llm, ChatGoogleGenerativeAI)


def test_deepseek_provider_uses_chatopenai_with_deepseek_base_url(monkeypatch):
    monkeypatch.setattr(settings, "write_provider", "deepseek")
    monkeypatch.setattr(settings, "deepseek_api_key", "test-key")
    monkeypatch.setattr(settings, "deepseek_model", "deepseek-v4-pro")

    llm = _build_write_llm()

    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "deepseek-v4-pro"
    assert str(llm.openai_api_base) == "https://api.deepseek.com"
