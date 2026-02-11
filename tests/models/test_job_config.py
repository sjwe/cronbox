import pytest
from pydantic import ValidationError

from cronbox.models.job_config import (
    ContainerConfig,
    JobConfig,
    NotifyConfig,
    ScheduleConfig,
    StepConfig,
)


class TestStepConfig:
    def test_minimal(self):
        step = StepConfig(name="build", command="make build")
        assert step.name == "build"
        assert step.command == "make build"
        assert step.timeout_seconds is None
        assert step.workdir is None
        assert step.environment is None
        assert step.user is None

    def test_all_fields(self):
        step = StepConfig(
            name="deploy",
            command="./deploy.sh",
            timeout_seconds=300,
            workdir="/app",
            environment={"ENV": "prod"},
            user="deployer",
        )
        assert step.timeout_seconds == 300
        assert step.workdir == "/app"
        assert step.environment == {"ENV": "prod"}
        assert step.user == "deployer"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            StepConfig(command="echo hi")

    def test_missing_command_raises(self):
        with pytest.raises(ValidationError):
            StepConfig(name="broken")


class TestContainerConfig:
    def test_persistent(self):
        cc = ContainerConfig(mode="persistent", name="my-ctr")
        assert cc.mode == "persistent"
        assert cc.name == "my-ctr"
        assert cc.image is None

    def test_ephemeral(self):
        cc = ContainerConfig(mode="ephemeral", image="alpine:latest")
        assert cc.mode == "ephemeral"
        assert cc.image == "alpine:latest"
        assert cc.name is None

    def test_missing_mode_raises(self):
        with pytest.raises(ValidationError):
            ContainerConfig(name="ctr")


class TestScheduleConfig:
    def test_defaults(self):
        sc = ScheduleConfig(cron="0 * * * *")
        assert sc.timezone == "UTC"
        assert sc.enabled is True

    def test_custom_values(self):
        sc = ScheduleConfig(cron="30 2 * * 1", timezone="US/Eastern", enabled=False)
        assert sc.timezone == "US/Eastern"
        assert sc.enabled is False

    def test_missing_cron_raises(self):
        with pytest.raises(ValidationError):
            ScheduleConfig()


class TestNotifyConfig:
    def test_defaults(self):
        nc = NotifyConfig()
        assert nc.on_failure is True
        assert nc.on_success is False
        assert nc.discord_webhook_url is None

    def test_custom_values(self):
        nc = NotifyConfig(
            on_failure=False,
            on_success=True,
            discord_webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert nc.on_failure is False
        assert nc.on_success is True
        assert nc.discord_webhook_url == "https://discord.com/api/webhooks/123/abc"


class TestJobConfig:
    def test_valid_minimal(self):
        jc = JobConfig(
            name="test",
            schedule=ScheduleConfig(cron="0 * * * *"),
            container=ContainerConfig(mode="persistent", name="ctr"),
            steps=[StepConfig(name="s1", command="echo hi")],
        )
        assert jc.name == "test"
        assert jc.description is None
        assert jc.timeout_seconds == 7200
        assert jc.notify is None

    def test_all_fields(self):
        jc = JobConfig(
            name="full",
            description="A fully specified job",
            schedule=ScheduleConfig(cron="0 2 * * *", timezone="Europe/London", enabled=False),
            container=ContainerConfig(mode="ephemeral", image="python:3.12"),
            steps=[
                StepConfig(name="s1", command="echo a"),
                StepConfig(name="s2", command="echo b"),
            ],
            notify=NotifyConfig(on_failure=True, discord_webhook_url="https://hook.url"),
            timeout_seconds=900,
        )
        assert jc.description == "A fully specified job"
        assert jc.timeout_seconds == 900
        assert len(jc.steps) == 2
        assert jc.notify.on_failure is True

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            JobConfig(
                schedule=ScheduleConfig(cron="0 * * * *"),
                container=ContainerConfig(mode="persistent", name="ctr"),
                steps=[StepConfig(name="s1", command="echo hi")],
            )

    def test_missing_schedule_raises(self):
        with pytest.raises(ValidationError):
            JobConfig(
                name="no-schedule",
                container=ContainerConfig(mode="persistent", name="ctr"),
                steps=[StepConfig(name="s1", command="echo hi")],
            )

    def test_missing_steps_raises(self):
        with pytest.raises(ValidationError):
            JobConfig(
                name="no-steps",
                schedule=ScheduleConfig(cron="0 * * * *"),
                container=ContainerConfig(mode="persistent", name="ctr"),
            )

    def test_default_timeout(self):
        jc = JobConfig(
            name="defaults",
            schedule=ScheduleConfig(cron="0 * * * *"),
            container=ContainerConfig(mode="persistent", name="ctr"),
            steps=[StepConfig(name="s1", command="echo hi")],
        )
        assert jc.timeout_seconds == 7200
