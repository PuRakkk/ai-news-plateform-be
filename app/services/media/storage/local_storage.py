import shutil
from pathlib import Path

from app.core.config import settings
from app.core.log import logger
from app.services.media.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Local filesystem storage provider for development and testing."""

    def __init__(
        self,
        base_dir: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR).resolve()
        self.base_url = (base_url or settings.STORAGE_BASE_URL).rstrip("/")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_key(self, relative_path: str) -> str:
        return relative_path.replace("\\", "/").lstrip("/")

    def _get_target_path(self, relative_path: str) -> Path:
        normalized = self._normalize_key(relative_path)
        target = self.base_dir / normalized
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def save_bytes(
        self,
        data: bytes,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        target = self._get_target_path(relative_path)
        target.write_bytes(data)
        logger.debug(f"Saved {len(data)} bytes to {target}")
        return self.get_url(relative_path)

    def save_file(
        self,
        source_path: str | Path,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        src = Path(source_path)
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")

        target = self._get_target_path(relative_path)
        if src.resolve() != target.resolve():
            shutil.copy2(src, target)
        logger.debug(f"Saved file {src} -> {target}")
        return self.get_url(relative_path)

    def get_url(self, relative_path: str) -> str:
        normalized = self._normalize_key(relative_path)
        return f"{self.base_url}/{normalized}"

    def get_local_path(self, relative_path: str) -> Path | None:
        normalized = self._normalize_key(relative_path)
        return self.base_dir / normalized

    def file_exists(self, relative_path: str) -> bool:
        normalized = self._normalize_key(relative_path)
        return (self.base_dir / normalized).exists()

    def delete_file(self, relative_path: str) -> bool:
        normalized = self._normalize_key(relative_path)
        target = self.base_dir / normalized
        if target.exists():
            target.unlink()
            return True
        return False
