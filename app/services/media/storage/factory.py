from app.core.config import settings
from app.services.media.storage.base import StorageProvider
from app.services.media.storage.local_storage import LocalStorageProvider


def get_storage_provider() -> StorageProvider:
    """Factory to retrieve configured media storage provider."""
    if settings.STORAGE_PROVIDER in ("s3", "r2"):
        from app.services.media.storage.s3_storage import S3StorageProvider
        return S3StorageProvider()
    return LocalStorageProvider()
