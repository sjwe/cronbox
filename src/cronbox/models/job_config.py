from pydantic import BaseModel


class StepConfig(BaseModel):
    name: str
    command: str
    timeout_seconds: int | None = None
    workdir: str | None = None
    environment: dict[str, str] | None = None
    user: str | None = None


class ContainerConfig(BaseModel):
    mode: str  # "persistent" or "ephemeral"
    name: str | None = None
    image: str | None = None
    volumes: dict[str, str] | None = None
    network: str | None = None


class ScheduleConfig(BaseModel):
    cron: str
    timezone: str = "UTC"
    enabled: bool = True


class NotifyConfig(BaseModel):
    on_failure: bool = True
    on_success: bool = False
    discord_webhook_url: str | None = None


class JobConfig(BaseModel):
    name: str
    description: str | None = None
    schedule: ScheduleConfig
    container: ContainerConfig
    steps: list[StepConfig]
    notify: NotifyConfig | None = None
    timeout_seconds: int = 7200
