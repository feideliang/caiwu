"""Application configuration using pydantic-settings."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "caiwu"
    db_user: str = "postgres"
    db_password: str = ""

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?ssl=disable"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    # ── Redis ─────────────────────────────────────────────────
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{self.redis_db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # ── IMAP ──────────────────────────────────────────────────
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_use_xoauth2: bool = False
    imap_poll_interval: int = 300  # seconds (legacy — unused; beat schedule drives polling now)
    email_poll_hour: int = 2  # daily beat schedule: hour (local)
    email_poll_minute: int = 0  # daily beat schedule: minute
    imap_subject_keywords: list[str] = []
    imap_from_whitelist: list[str] = []
    imap_max_attachment_size: int = 20_971_520  # 20 MB in bytes
    imap_processed_uids_file: str = "./data/processed_uids.json"
    imap_poll_timeout: int = 60  # seconds

    # ── AI (Qwen) ─────────────────────────────────────────────
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ── JWT ───────────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60

    # ── App ───────────────────────────────────────────────────
    app_name: str = "AI+BI Financial Reporting System"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_hosts: list[str] = ["*"]
    cors_origins: list[str] = ["*"]

    # ── Data Sync ─────────────────────────────────────────────
    sync_full_interval_days: int = 1
    sync_incremental_interval_hours: int = 4

    # ── BI MySQL ──────────────────────────────────────────────
    bi_mysql_host: str = "192.168.159.22"
    bi_mysql_port: int = 33307
    bi_mysql_database: str = "caiwu"
    bi_mysql_user: str = "app_caiwu"
    bi_mysql_password: str = "123456"

    @property
    def bi_mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.bi_mysql_user}:{self.bi_mysql_password}"
            f"@{self.bi_mysql_host}:{self.bi_mysql_port}/{self.bi_mysql_database}"
        )

    # ── Alert ─────────────────────────────────────────────────
    alert_check_interval_seconds: int = 60
    alert_retention_days: int = 90

    # ── Report ────────────────────────────────────────────────
    report_generator_timeout_seconds: int = 600
    report_max_retries: int = 3

    # ── Celery ────────────────────────────────────────────────
    celery_broker_url: str = ""  # defaults to redis_url
    celery_result_backend: str = ""  # defaults to redis_url
    celery_task_default_queue: str = "default"

    # ── Prediction ────────────────────────────────────────────
    prediction_min_history_months: int = 3
    prediction_mape_qualified: float = 15.0
    prediction_mape_warning: float = 25.0

    # ── File storage ──────────────────────────────────────────
    report_output_dir: str = "./output/reports"

    # ── Vector DB (Qdrant RAG) ────────────────────────────────
    qdrant_path: str = "./qdrant_data_seed"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536


settings = Settings()
