import logging
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def download_dfp_zip(year: int, cache_dir: str | None = None) -> Path:
    """Download DFP ZIP file from CVM for a given year.

    Returns the path to the downloaded ZIP file.
    Skips download if the file already exists locally.
    """
    cache_path = Path(cache_dir or settings.CACHE_DIR)
    cache_path.mkdir(parents=True, exist_ok=True)

    zip_filename = f"dfp_cia_aberta_{year}.zip"
    zip_path = cache_path / zip_filename

    if zip_path.exists():
        logger.info("ZIP already cached: %s", zip_path)
        return zip_path

    url = f"{settings.CVM_BASE_URL}{zip_filename}"
    logger.info("Downloading %s", url)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    zip_path.write_bytes(response.content)
    logger.info("Saved %s (%d bytes)", zip_path, len(response.content))
    return zip_path
