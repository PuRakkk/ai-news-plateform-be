import abc
from pathlib import Path


class StorageProvider(abc.ABC):
    """Abstract interface for storing and serving generated media assets."""

    @abc.abstractmethod
    def save_bytes(
        self,
        data: bytes,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Persist raw bytes to storage and return its public URL."""
        pass

    @abc.abstractmethod
    def save_file(
        self,
        source_path: str | Path,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Persist an existing file from disk to storage and return its public URL."""
        pass

    @abc.abstractmethod
    def get_url(self, relative_path: str) -> str:
        """Return the web-accessible URL for a stored asset."""
        pass

    @abc.abstractmethod
    def get_local_path(self, relative_path: str) -> Path | None:
        """Return the local filesystem path if available, or None for cloud providers."""
        pass

    @abc.abstractmethod
    def file_exists(self, relative_path: str) -> bool:
        """Check if an asset exists at the specified relative path."""
        pass

    @abc.abstractmethod
    def delete_file(self, relative_path: str) -> bool:
        """Delete an asset from storage. Return True if deleted or False if not found."""
        pass
