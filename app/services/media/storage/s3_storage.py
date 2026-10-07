from pathlib import Path

from app.core.config import settings
from app.core.log import logger
from app.services.media.storage.base import StorageProvider


class S3StorageProvider(StorageProvider):
    """S3 and Cloudflare R2 compatible storage provider for production."""

    def __init__(self) -> None:
        try:
            import boto3
            from botocore.client import Config
        except ImportError as exc:
            raise ImportError(
                "boto3 is required for S3/R2 storage. Run 'uv add boto3' to install it."
            ) from exc

        self.bucket = settings.S3_BUCKET_NAME
        self.endpoint_url = settings.S3_ENDPOINT_URL
        self.public_base_url = (settings.S3_PUBLIC_BASE_URL or "").rstrip("/")

        self.client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
        )

    def _normalize_key(self, relative_path: str) -> str:
        return relative_path.replace("\\", "/").lstrip("/")

    def save_bytes(
        self,
        data: bytes,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        key = self._normalize_key(relative_path)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return self.get_url(relative_path)

    def save_file(
        self,
        source_path: str | Path,
        relative_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        key = self._normalize_key(relative_path)
        with open(source_path, "rb") as f:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=f,
                ContentType=content_type,
            )
        return self.get_url(relative_path)

    def get_url(self, relative_path: str) -> str:
        key = self._normalize_key(relative_path)
        if self.public_base_url:
            return f"{self.public_base_url}/{key}"
        if self.endpoint_url:
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
        return f"https://{self.bucket}.s3.amazonaws.com/{key}"

    def get_local_path(self, relative_path: str) -> Path | None:
        return None

    def file_exists(self, relative_path: str) -> bool:
        key = self._normalize_key(relative_path)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete_file(self, relative_path: str) -> bool:
        key = self._normalize_key(relative_path)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as exc:
            logger.warning(f"Failed to delete {key} from S3: {exc}")
            return False
