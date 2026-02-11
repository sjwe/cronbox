from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CRONBOX_"}

    jobs_config_dir: str = "config/jobs"
    logs_dir: str = "logs"
    db_path: str = "data/cronbox.db"
    discord_webhook_url: str = ""
    web_base_url: str = ""
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_retention_days: int = 30
