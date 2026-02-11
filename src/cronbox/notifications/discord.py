import httpx

from cronbox.config import Settings
from cronbox.models.database import JobRun


async def send_failure_notification(
    job_name: str,
    run: JobRun,
    failed_step: str | None,
    settings: Settings,
):
    webhook_url = settings.discord_webhook_url
    if not webhook_url:
        return

    duration = f"{run.duration_seconds:.1f}s" if run.duration_seconds else "N/A"
    log_url = ""
    if settings.web_base_url and run.log_file:
        log_filename = run.log_file.rsplit("/", 1)[-1] if "/" in run.log_file else run.log_file
        log_url = f"{settings.web_base_url}/api/logs/{job_name}/{log_filename}"

    fields = [
        {"name": "Job", "value": job_name, "inline": True},
        {"name": "Trigger", "value": run.trigger, "inline": True},
        {"name": "Duration", "value": duration, "inline": True},
    ]
    if failed_step:
        fields.append({"name": "Failed Step", "value": failed_step, "inline": True})
    if log_url:
        fields.append({"name": "Logs", "value": f"[View logs]({log_url})", "inline": False})

    payload = {
        "embeds": [
            {
                "title": f"Job Failed: {job_name}",
                "color": 0xFF0000,
                "fields": fields,
                "timestamp": run.started_at.isoformat() if run.started_at else None,
            }
        ]
    }

    async with httpx.AsyncClient() as client:
        await client.post(webhook_url, json=payload, timeout=10)
