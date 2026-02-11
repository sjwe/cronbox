from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from cronbox.models.api_models import LogFileEntry
from cronbox.utils import read_log_tail

router = APIRouter(prefix="/api")


@router.get("/logs/{job_name}", response_model=list[LogFileEntry])
async def list_logs(job_name: str, request: Request, limit: int = 100):
    settings = request.app.state.settings
    log_dir = Path(settings.logs_dir) / job_name

    # Prevent path traversal
    resolved = log_dir.resolve()
    base = Path(settings.logs_dir).resolve()
    if not str(resolved).startswith(str(base)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not log_dir.exists():
        return []

    entries = []
    for f in sorted(log_dir.iterdir(), reverse=True):
        if f.is_file() and f.suffix == ".log":
            stat = f.stat()
            entries.append(
                LogFileEntry(
                    filename=f.name,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                )
            )

    return entries[:limit]


@router.get("/logs/{job_name}/{filename}")
async def get_log(job_name: str, filename: str, request: Request):
    settings = request.app.state.settings
    log_path = Path(settings.logs_dir) / job_name / filename

    if not log_path.exists() or not log_path.is_file():
        raise HTTPException(status_code=404, detail="Log file not found")

    # Prevent path traversal
    resolved = log_path.resolve()
    base = Path(settings.logs_dir).resolve()
    if not str(resolved).startswith(str(base)):
        raise HTTPException(status_code=403, detail="Access denied")

    content = read_log_tail(log_path)
    return PlainTextResponse(content)
