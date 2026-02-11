from datetime import datetime

from pydantic import BaseModel


class StepInfo(BaseModel):
    name: str
    command: str
    timeout_seconds: int | None = None


class ScheduleInfo(BaseModel):
    cron: str
    timezone: str
    enabled: bool


class LastRunInfo(BaseModel):
    status: str
    started_at: datetime
    duration_seconds: float | None = None


class JobSummary(BaseModel):
    name: str
    description: str | None = None
    schedule: ScheduleInfo
    next_run_time: str | None = None
    last_run: LastRunInfo | None = None


class ContainerInfo(BaseModel):
    mode: str
    name: str | None = None
    image: str | None = None


class RunSummary(BaseModel):
    id: int
    job_name: str
    status: str
    trigger: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_seconds: float | None = None


class StepResultResponse(BaseModel):
    name: str
    status: str
    exit_code: int | None = None
    duration_seconds: float | None = None


class RunDetail(RunSummary):
    steps: list[StepResultResponse] = []
    log_file: str | None = None


class JobDetail(JobSummary):
    container: ContainerInfo
    steps: list[StepInfo] = []
    recent_runs: list[RunSummary] = []


class TriggerResponse(BaseModel):
    message: str
    job_name: str


class ReloadResponse(BaseModel):
    message: str
    jobs_loaded: int


class LogFileEntry(BaseModel):
    filename: str
    size_bytes: int
    modified_at: datetime


class PaginatedRuns(BaseModel):
    runs: list[RunSummary]
    total: int
    page: int
    per_page: int


# --- Auth models ---


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    user: UserResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class CreateAPIKeyRequest(BaseModel):
    name: str
    expires_in_days: int | None = 30


class APIKeyResponse(BaseModel):
    id: int
    key: str
    key_prefix: str
    name: str
    expires_at: datetime | None = None
    created_at: datetime


class APIKeyListItem(BaseModel):
    id: int
    key_prefix: str
    name: str
    expires_at: datetime | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    is_active: bool


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: str = "viewer"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
