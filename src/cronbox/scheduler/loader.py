from pathlib import Path

import yaml

from cronbox.models.job_config import JobConfig


def load_jobs(config_dir: str) -> list[JobConfig]:
    configs = []
    config_path = Path(config_dir)
    if not config_path.exists():
        return configs

    for file in sorted(config_path.iterdir()):
        if file.suffix in (".yml", ".yaml"):
            with open(file) as f:
                data = yaml.safe_load(f)
            if data:
                configs.append(JobConfig(**data))

    return configs
