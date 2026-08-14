from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    owner_telegram_id: int

    gemini_api_key: str
    # Cheap/fast tier for the research loop, which makes many tool-calling
    # round trips. Confirmed against the live ListModels API.
    gemini_model: str = "gemini-3.5-flash-lite"
    # Pro tier for the single final write call: Flash-class models compressed
    # rich research into thin articles (observed live); Pro-class models are
    # built for thorough synthesis, not concise output, which is what this
    # step needs. Priced close to gemini-3.5-flash for our token counts
    # ($1.25/$10.00 per 1M in/out vs $1.50/$9.00) -- confirmed against the
    # live pricing page before switching, not assumed cheaper-is-worse.
    gemini_write_model: str = "gemini-2.5-pro"

    # A/B toggle for the write step only -- research stays on Gemini either
    # way. "gemini" (default) or "deepseek". DeepSeek's API is OpenAI-
    # compatible (base_url swap on ChatOpenAI), confirmed against their docs
    # before wiring in.
    write_provider: str = "gemini"
    deepseek_api_key: str | None = None
    deepseek_model: str = "deepseek-v4-pro"

    tavily_api_key: str | None = None
    github_token: str | None = None

    database_path: str = "./data/agent.db"


settings = Settings()
