import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from cronbox.config import Settings
from cronbox.executor.docker_ops import DockerOperations
from cronbox.executor.log_capture import LogCapture
from cronbox.models.database import JobRun, StepResult
from cronbox.models.job_config import JobConfig
from cronbox.notifications.discord import send_failure_notification

logger = logging.getLogger(__name__)


async def execute_job(
    job_config: JobConfig,
    trigger: str = "scheduled",
    *,
    db_session: AsyncSession,
    settings: Settings,
    docker_ops: DockerOperations | None = None,
):
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    run = JobRun(
        job_name=job_config.name,
        status="running",
        trigger=trigger,
        started_at=now,
    )
    db_session.add(run)
    await db_session.flush()

    log = LogCapture()
    log_path = log.open(settings.logs_dir, job_config.name, timestamp)
    run.log_file = log_path

    if docker_ops is None:
        docker_ops = DockerOperations()
    failed_step_name: str | None = None

    try:
        await asyncio.wait_for(
            _run_steps(job_config, run, log, docker_ops, db_session),
            timeout=job_config.timeout_seconds,
        )
    except asyncio.TimeoutError:
        run.status = "failed"
        failed_step_name = "job_timeout"
        log.write("stderr", f"Job timed out after {job_config.timeout_seconds}s")
        logger.error("Job %s timed out", job_config.name)
    except Exception as e:
        run.status = "failed"
        failed_step_name = "unexpected_error"
        log.write("stderr", f"Unexpected error: {e}")
        logger.exception("Job %s failed unexpectedly", job_config.name)

    if run.status == "running":
        run.status = "success"

    finished = datetime.now(timezone.utc)
    run.finished_at = finished
    run.duration_seconds = (finished - now).total_seconds()

    await db_session.commit()
    log.close()

    if run.status == "failed":
        notify = job_config.notify
        if notify and notify.on_failure:
            try:
                await send_failure_notification(
                    job_config.name, run, failed_step_name, settings
                )
            except Exception:
                logger.exception("Failed to send Discord notification for %s", job_config.name)

    return run


async def _run_steps(
    job_config: JobConfig,
    run: JobRun,
    log: LogCapture,
    docker_ops: DockerOperations,
    db_session: AsyncSession,
):
    for step in job_config.steps:
        step_start = datetime.now(timezone.utc)
        step_result = StepResult(
            run_id=run.id,
            step_name=step.name,
            status="running",
            started_at=step_start,
        )
        db_session.add(step_result)
        await db_session.flush()

        log.write("stdout", f"=== Step: {step.name} ===")
        log.write("stdout", f"Command: {step.command}")

        try:
            if step.timeout_seconds:
                exit_code, output = await asyncio.wait_for(
                    _exec_step(job_config, step, docker_ops),
                    timeout=step.timeout_seconds,
                )
            else:
                exit_code, output = await _exec_step(job_config, step, docker_ops)
        except asyncio.TimeoutError:
            exit_code = -1
            output = f"Step timed out after {step.timeout_seconds}s"
            log.write("stderr", output)
        except Exception as e:
            exit_code = -1
            output = f"Step execution error: {e}"
            log.write("stderr", output)

        for line in output.splitlines():
            stream = "stderr" if exit_code != 0 else "stdout"
            log.write(stream, line)

        step_end = datetime.now(timezone.utc)
        step_result.exit_code = exit_code
        step_result.finished_at = step_end
        step_result.duration_seconds = (step_end - step_start).total_seconds()
        step_result.output_snippet = _truncate_output(output)

        if exit_code != 0:
            step_result.status = "failed"
            run.status = "failed"
            log.write("stderr", f"Step '{step.name}' failed with exit code {exit_code}")

            for remaining in job_config.steps[job_config.steps.index(step) + 1 :]:
                skipped = StepResult(
                    run_id=run.id,
                    step_name=remaining.name,
                    status="skipped",
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    duration_seconds=0,
                )
                db_session.add(skipped)

            break
        else:
            step_result.status = "success"
            log.write("stdout", f"Step '{step.name}' completed (exit code 0)")


async def _exec_step(job_config, step, docker_ops):
    if job_config.container.mode == "persistent":
        await asyncio.to_thread(
            docker_ops.ensure_started, job_config.container.name
        )
        return await asyncio.to_thread(
            docker_ops.exec_in_container,
            job_config.container.name,
            step.command,
            step.workdir,
            step.environment,
            step.user,
        )
    else:
        return await asyncio.to_thread(
            docker_ops.run_ephemeral,
            job_config.container.image,
            step.command,
            job_config.container.volumes,
            job_config.container.network,
            step.workdir,
            step.environment,
            step.user,
        )


def _truncate_output(output: str, max_lines: int = 50) -> str:
    lines = output.splitlines()
    if len(lines) <= max_lines:
        return output
    head = lines[: max_lines // 2]
    tail = lines[-(max_lines // 2) :]
    return "\n".join(head + [f"... ({len(lines) - max_lines} lines omitted) ..."] + tail)
