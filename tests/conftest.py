import os

# Provide dummy required settings before app.config is imported anywhere,
# so tests don't need a real .env file.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("OWNER_TELEGRAM_ID", "123")
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("MEDIUM_INTEGRATION_TOKEN", "test-medium-token")

# Pin optional-but-behavior-affecting settings too. pydantic-settings reads
# unset ones from the real .env file (lower priority than an actual env var,
# but higher than the field default), so without this, module-level objects
# built at import time -- e.g. app/agent/nodes/write.py's `_llm` -- silently
# pick up whatever the developer's local .env happens to have (caught live:
# a local .env with WRITE_PROVIDER=deepseek made test_llm_config.py fail
# because the module-level _llm was a ChatOpenAI, not the expected Gemini
# client, with no test-code change at fault).
os.environ.setdefault("WRITE_PROVIDER", "gemini")
