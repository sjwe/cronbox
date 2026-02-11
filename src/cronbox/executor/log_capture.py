from datetime import datetime, timezone
from pathlib import Path


class LogCapture:
    def __init__(self):
        self._file = None
        self._path: str | None = None

    def open(self, logs_dir: str, job_name: str, timestamp: str) -> str:
        dir_path = Path(logs_dir) / job_name
        dir_path.mkdir(parents=True, exist_ok=True)
        self._path = str(dir_path / f"{timestamp}.log")
        self._file = open(self._path, "w")
        return self._path

    def write(self, stream: str, line: str):
        if self._file:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            tag = "STDOUT" if stream == "stdout" else "STDERR"
            self._file.write(f"[{ts}] [{tag}] {line}\n")
            self._file.flush()

    def close(self):
        if self._file:
            self._file.close()
            self._file = None

    @property
    def path(self) -> str | None:
        return self._path
