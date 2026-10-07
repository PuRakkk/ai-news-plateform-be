from pathlib import Path
import httpx

from app.core.cipher import validate_outbound_url
from app.core.config import settings
from app.core.log import logger
from app.services.media.storage.base import StorageProvider
from app.services.media.storage.factory import get_storage_provider


class AssetResolver:
    """Safely resolves and downloads branding media assets (watermarks, bumper videos)."""

    def __init__(self, storage: StorageProvider | None = None) -> None:
        self.storage = storage or get_storage_provider()

    async def resolve_asset(self, asset_url_or_path: str | None, destination_dir: Path, filename: str) -> Path | None:
        """Resolve a local storage path or validated outbound URL into a local file."""
        if not asset_url_or_path or not asset_url_or_path.strip():
            return None

        clean_target = asset_url_or_path.strip()

        # 1. Check if it's already a direct existing local filesystem path
        direct_path = Path(clean_target)
        if direct_path.exists() and direct_path.is_file():
            return direct_path

        # 2. Check if it's a relative path in local storage (e.g. 'thumbnails/xxx.png')
        local_stored = self.storage.get_local_path(clean_target)
        if local_stored and local_stored.exists():
            return local_stored

        # 3. Check if it's a URL hosted by this app's storage base URL
        storage_base = settings.STORAGE_BASE_URL.rstrip("/")
        if clean_target.startswith(storage_base):
            rel_part = clean_target[len(storage_base) :].lstrip("/")
            local_stored = self.storage.get_local_path(rel_part)
            if local_stored and local_stored.exists():
                return local_stored

        # 4. Outbound external URL: Validate against SSRF before making any HTTP request
        if clean_target.startswith("http://") or clean_target.startswith("https://"):
            if not validate_outbound_url(clean_target):
                logger.warning(f"Blocked SSRF attempt for brand asset URL: {clean_target}")
                return None

            dest_path = destination_dir / filename
            try:
                async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                    resp = await client.get(clean_target)
                    if resp.status_code == 200 and len(resp.content) > 0:
                        dest_path.write_bytes(resp.content)
                        logger.info(f"Downloaded brand asset: {clean_target} -> {dest_path}")
                        return dest_path
                    else:
                        logger.warning(f"Failed to download asset {clean_target}: status {resp.status_code}")
            except Exception as exc:
                logger.warning(f"Exception downloading brand asset {clean_target}: {exc}")
                return None

        return None
