from pathlib import Path

MAX_LOG_BYTES = 1_048_576  # 1MB


def read_log_tail(path: Path, max_bytes: int = MAX_LOG_BYTES) -> str:
    """Read a log file, returning only the tail if it exceeds max_bytes."""
    file_size = path.stat().st_size
    if file_size <= max_bytes:
        return path.read_text(errors="replace")

    with open(path, "rb") as f:
        f.seek(-max_bytes, 2)
        f.readline()  # skip partial first line
        content = f.read().decode("utf-8", errors="replace")

    header = f"[... truncated, showing last {max_bytes // 1024}KB of {file_size:,} bytes ...]\n"
    return header + content
