from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CRONBOX_"}

    jobs_config_dir: str = "config/jobs"
    logs_dir: str = "logs"
    db_path: str = "data/cronbox.db"
    discord_webhook_url: str = ""
    web_base_url: str = ""
    api_key: str = ""  # empty = no auth required (local dev)
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_retention_days: int = 30
