"""
Configuration management for Catering Services AI Pro
"""
import logging
from pydantic_settings import BaseSettings
from functools import lru_cache

logger = logging.getLogger(__name__)

WEAK_SECRET_KEYS = {
    "dev-secret-key-change-in-production",
    "secret",
    "changeme",
    "your-secret-key",
    "",
}


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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # Webhook authentication
    WEBHOOK_SECRET: str = ""

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
    s = Settings()

    is_postgres = "postgresql" in s.DATABASE_URL.lower()

    # Warn about weak SECRET_KEY in production (PostgreSQL = production)
    if is_postgres and s.SECRET_KEY in WEAK_SECRET_KEYS:
        logger.critical(
            "SECRET_KEY is a known weak default on a production database! "
            "Set a strong SECRET_KEY (e.g. secrets.token_hex(32)) in environment variables."
        )

    if not is_postgres and s.SECRET_KEY in WEAK_SECRET_KEYS:
        logger.warning(
            "SECRET_KEY is a weak default — acceptable for local dev only. "
            "Set a strong key before deploying."
        )

    # Warn if DEBUG is on with production database
    if s.DEBUG and is_postgres:
        logger.critical(
            "DEBUG=True with PostgreSQL detected — this is likely production. "
            "Set DEBUG=false in environment variables."
        )

    return s
