import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from app.config import settings
from app.services.cvm_downloader import download_dfp_zip
from app.services.data_processor import process_zip_to_dataframe

logger = logging.getLogger(__name__)


class DataCache:
    """Three-tier cache: in-memory dict -> parquet on disk -> CVM download."""

    def __init__(self) -> None:
        self._store: dict[int, pd.DataFrame] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._cache_dir = Path(settings.CACHE_DIR)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_lock(self, year: int) -> asyncio.Lock:
        if year not in self._locks:
            self._locks[year] = asyncio.Lock()
        return self._locks[year]

    def _parquet_path(self, year: int) -> Path:
        return self._cache_dir / f"dfp_{year}.parquet"

    def _meta_path(self, year: int) -> Path:
        return self._cache_dir / f"dfp_{year}.meta.json"

    def _is_fresh(self, year: int) -> bool:
        meta_path = self._meta_path(year)
        if not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        downloaded_at = datetime.fromisoformat(meta["downloaded_at"])
        return datetime.now() - downloaded_at < timedelta(hours=settings.CACHE_TTL_HOURS)

    def _save_parquet(self, year: int, df: pd.DataFrame) -> None:
        df.to_parquet(self._parquet_path(year), index=False)
        self._meta_path(year).write_text(
            json.dumps({"downloaded_at": datetime.now().isoformat()})
        )

    def _load_parquet(self, year: int) -> pd.DataFrame | None:
        path = self._parquet_path(year)
        if path.exists() and self._is_fresh(year):
            logger.info("Loading parquet cache for %d", year)
            return pd.read_parquet(path)
        return None

    async def _fetch_and_process(self, year: int) -> pd.DataFrame:
        zip_path = await download_dfp_zip(year)
        df = await asyncio.to_thread(process_zip_to_dataframe, zip_path)
        await asyncio.to_thread(self._save_parquet, year, df)
        return df

    async def get_year_data(self, year: int) -> pd.DataFrame:
        """Get DataFrame for a single year, using cache tiers."""
        # Tier 1: in-memory
        if year in self._store:
            return self._store[year]

        async with self._get_lock(year):
            # Double-check after acquiring lock
            if year in self._store:
                return self._store[year]

            # Tier 2: parquet on disk
            df = await asyncio.to_thread(self._load_parquet, year)
            if df is not None:
                self._store[year] = df
                return df

            # Tier 3: download from CVM
            logger.info("Cache miss for year %d, downloading from CVM", year)
            try:
                df = await self._fetch_and_process(year)
            except Exception:
                logger.warning("No data available for year %d", year)
                df = pd.DataFrame()
            self._store[year] = df
            return df

    async def get_data(self, years: list[int]) -> pd.DataFrame:
        """Get combined DataFrame for multiple years."""
        tasks = [self.get_year_data(year) for year in years]
        frames = await asyncio.gather(*tasks)
        frames = [f for f in frames if not f.empty]
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, ignore_index=True)

    async def preload(self, years: list[int]) -> None:
        """Preload years into cache on startup."""
        for year in years:
            try:
                await self.get_year_data(year)
                logger.info("Preloaded year %d", year)
            except Exception:
                logger.exception("Failed to preload year %d", year)

    async def invalidate(self, year: int) -> int:
        """Force re-download for a year. Returns row count."""
        self._store.pop(year, None)
        parquet = self._parquet_path(year)
        if parquet.exists():
            parquet.unlink()
        meta = self._meta_path(year)
        if meta.exists():
            meta.unlink()
        zip_path = self._cache_dir / f"dfp_cia_aberta_{year}.zip"
        if zip_path.exists():
            zip_path.unlink()

        df = await self._fetch_and_process(year)
        self._store[year] = df
        return len(df)

    def get_available_years(self) -> list[int]:
        return list(range(settings.MIN_YEAR, settings.MAX_YEAR + 1))
