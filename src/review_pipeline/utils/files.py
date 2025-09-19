from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional


def timestamped_filename(pattern: str, timestamp: Optional[str] = None) -> str:
    """Return *pattern* formatted with a timestamp placeholder."""

    ts = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    return pattern.format(timestamp=ts)


def ensure_parent_dir(path: Path) -> Path:
    """Create parent directories for *path* and return the path."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
