from collections.abc import Callable
from datetime import datetime

from apscheduler import AsyncScheduler, ConflictPolicy
from apscheduler.triggers.cron import CronTrigger

from cronbox.models.job_config import JobConfig


class SchedulerEngine:
    def __init__(self):
        self.scheduler = AsyncScheduler()
        self._configs: dict[str, JobConfig] = {}

    async def register_jobs(
        self,
        configs: list[JobConfig],
        execute_fn: Callable,
        kwargs: dict | None = None,
    ):
        self._configs = {c.name: c for c in configs}
        for config in configs:
            if not config.schedule.enabled:
                continue
            parts = config.schedule.cron.split()
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
                timezone=config.schedule.timezone,
            )
            await self.scheduler.add_schedule(
                execute_fn,
                trigger,
                id=config.name,
                args=[config],
                kwargs=kwargs or {},
                conflict_policy=ConflictPolicy.replace,
            )

    async def register_job(
        self,
        config: JobConfig,
        execute_fn: Callable,
        kwargs: dict | None = None,
    ):
        self._configs[config.name] = config
        if not config.schedule.enabled:
            # Remove any existing schedule if disabling
            try:
                await self.scheduler.remove_schedule(config.name)
            except Exception:
                pass
            return
        parts = config.schedule.cron.split()
        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone=config.schedule.timezone,
        )
        await self.scheduler.add_schedule(
            execute_fn,
            trigger,
            id=config.name,
            args=[config],
            kwargs=kwargs or {},
            conflict_policy=ConflictPolicy.replace,
        )

    async def remove_job(self, job_name: str):
        self._configs.pop(job_name, None)
        try:
            await self.scheduler.remove_schedule(job_name)
        except Exception:
            pass

    async def start(self):
        await self.scheduler.__aenter__()

    async def stop(self):
        await self.scheduler.__aexit__(None, None, None)

    def get_config(self, job_name: str) -> JobConfig | None:
        return self._configs.get(job_name)

    def get_all_configs(self) -> list[JobConfig]:
        return list(self._configs.values())

    async def get_next_run_time(self, job_name: str) -> datetime | None:
        try:
            schedule = await self.scheduler.get_schedule(job_name)
            return schedule.next_fire_time if schedule else None
        except Exception:
            return None

    async def get_all_next_run_times(self) -> dict[str, datetime | None]:
        schedules = await self.scheduler.get_schedules()
        return {s.id: s.next_fire_time for s in schedules}
