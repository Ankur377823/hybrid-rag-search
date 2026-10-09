"""Local file and object storage manager for uploaded document assets."""

from __future__ import annotations

import hashlib
from pathlib import Path


class FileStorage:
    """Manages raw document file storage on disk (S3-compatible structure)."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def save_file(
        self,
        *,
        user_id: str,
        filename: str,
        content: bytes,
        version: int = 1,
    ) -> tuple[str, str, int]:
        """Save file bytes and return (storage_path, sha256_hash, size_bytes)."""
        file_hash = hashlib.sha256(content).hexdigest()
        user_dir = self.root_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)

        # Namespaced storage path
        safe_name = Path(filename).name
        target = user_dir / f"v{version}_{safe_name}"
        target.write_bytes(content)

        return str(target), file_hash, len(content)

    def read_file(self, storage_path: str) -> bytes:
        p = Path(storage_path)
        if not p.exists():
            raise FileNotFoundError(f"Stored file not found: {storage_path}")
        return p.read_bytes()

    def delete_file(self, storage_path: str) -> bool:
        p = Path(storage_path)
        if p.exists():
            try:
                p.unlink()
                return True
            except OSError:
                return False
        return False
