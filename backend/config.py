"""
Configuration management for Catering Services AI Pro
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Catering Services AI Pro"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./catering_ai.db"

    # Security
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Claude API
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 4096

    # Email (Gmail API)
    GMAIL_CREDENTIALS_PATH: str = ""
    GMAIL_TOKEN_PATH: str = ""

    # IMAP email polling (for daily meal reports)
    IMAP_HOST: str = ""            # e.g. "imap.gmail.com"
    IMAP_EMAIL: str = ""           # e.g. "ziv@example.com"
    IMAP_PASSWORD: str = ""        # Gmail app password
    MEAL_EMAIL_SENDER: str = ""    # filter: sender address (partial match)
    MEAL_EMAIL_SUBJECT: str = ""   # filter: subject keyword (partial match)
    MEAL_POLL_INTERVAL_MIN: int = 60  # check every N minutes

    # Calendar (Google Calendar API)
    CALENDAR_CREDENTIALS_PATH: str = ""

    # Slack
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""

    # Sites
    SITES: list[str] = ["Nes Ziona", "Kiryat Gat"]

    # Costs & Budget
    DEFAULT_MONTHLY_BUDGET: float = 120000.0  # ₪120k

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
