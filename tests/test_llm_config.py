"""Regression test for a real bug: pydantic-settings loads .env into our own
Settings object, but that does NOT export those vars into os.environ. Any
code that read os.environ directly (or relied on a library's own env-var
auto-detection) silently got no key when the app was launched without the
key separately exported in the shell -- caught by actually running the app.
"""

from app.agent.nodes.research import _llm as research_llm
from app.agent.nodes.write import _llm as write_llm
from app.config import settings


def test_research_llm_receives_api_key_from_settings():
    assert research_llm.google_api_key is not None
    assert research_llm.google_api_key.get_secret_value() == settings.gemini_api_key


def test_write_llm_receives_api_key_from_settings():
    assert write_llm.google_api_key is not None
    assert write_llm.google_api_key.get_secret_value() == settings.gemini_api_key
