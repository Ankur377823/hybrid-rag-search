"""Safe JSON read/write helpers shared by the dense and sparse stores.

- `save_json` writes to a temporary file first and then swaps it in, so a crash
  in the middle of a save can never leave a half-written index file.
- `load_json` never silently throws data away: an unreadable file is renamed to
  `<name>.corrupt` and reported in the log, so it can still be recovered.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..logging import get_logger

log = get_logger(__name__)


def save_json(path: Path, payload: dict[str, Any]) -> None:
    """Write `payload` to `path` atomically (temp file + rename)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(payload), encoding="utf-8")
    os.replace(tmp_path, path)


def load_json(path: Path) -> dict[str, Any] | None:
    """Read `path`. Returns None when the file is missing or unreadable."""
    if not path.exists():
        return None
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        backup = path.with_name(path.name + ".corrupt")
        os.replace(path, backup)
        log.error("store.corrupt_index_file", path=str(path), backup=str(backup), error=str(exc))
        return None
    return data
