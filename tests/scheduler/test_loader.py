from pathlib import Path

import pytest
from pydantic import ValidationError

from cronbox.scheduler.loader import load_jobs


def _write_yaml(directory: Path, filename: str, content: str):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(content)


class TestLoadJobs:
    def test_load_valid_yaml(self, tmp_path):
        _write_yaml(
            tmp_path,
            "job1.yaml",
            """
name: backup
schedule:
  cron: "0 2 * * *"
container:
  mode: persistent
  name: backup-ctr
steps:
  - name: run-backup
    command: /backup.sh
""",
        )
        configs = load_jobs(str(tmp_path))
        assert len(configs) == 1
        assert configs[0].name == "backup"
        assert configs[0].schedule.cron == "0 2 * * *"
        assert configs[0].container.mode == "persistent"

    def test_empty_directory(self, tmp_path):
        tmp_path.mkdir(exist_ok=True)
        configs = load_jobs(str(tmp_path))
        assert configs == []

    def test_nonexistent_directory(self, tmp_path):
        configs = load_jobs(str(tmp_path / "nonexistent"))
        assert configs == []

    def test_non_yaml_files_skipped(self, tmp_path):
        _write_yaml(
            tmp_path,
            "notes.txt",
            "name: not-a-job\nschedule:\n  cron: '0 * * * *'\n",
        )
        _write_yaml(
            tmp_path,
            "data.json",
            '{"name": "json-job"}',
        )
        configs = load_jobs(str(tmp_path))
        assert configs == []

    def test_empty_yaml_skipped(self, tmp_path):
        _write_yaml(tmp_path, "empty.yaml", "")
        configs = load_jobs(str(tmp_path))
        assert configs == []

    def test_yaml_missing_required_fields_raises(self, tmp_path):
        _write_yaml(
            tmp_path,
            "bad.yaml",
            "name: incomplete\n",
        )
        with pytest.raises(ValidationError):
            load_jobs(str(tmp_path))

    def test_multiple_files_loaded_in_order(self, tmp_path):
        _write_yaml(
            tmp_path,
            "aaa.yml",
            """
name: alpha
schedule:
  cron: "0 1 * * *"
container:
  mode: ephemeral
  image: alpine
steps:
  - name: s1
    command: echo a
""",
        )
        _write_yaml(
            tmp_path,
            "zzz.yaml",
            """
name: zulu
schedule:
  cron: "30 3 * * *"
container:
  mode: persistent
  name: zulu-ctr
steps:
  - name: s1
    command: echo z
""",
        )
        configs = load_jobs(str(tmp_path))
        assert len(configs) == 2
        assert configs[0].name == "alpha"
        assert configs[1].name == "zulu"

    def test_yml_extension_accepted(self, tmp_path):
        _write_yaml(
            tmp_path,
            "job.yml",
            """
name: yml-job
schedule:
  cron: "0 0 * * *"
container:
  mode: persistent
  name: ctr
steps:
  - name: s1
    command: echo hi
""",
        )
        configs = load_jobs(str(tmp_path))
        assert len(configs) == 1
        assert configs[0].name == "yml-job"
