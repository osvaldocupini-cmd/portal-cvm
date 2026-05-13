import asyncio
import json
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd

from app.config import settings

logger = logging.getLogger(__name__)

SEGMENT_LABELS: dict[str, str] = {
    "NM": "Novo Mercado",
    "N1": "Nível 1",
    "N2": "Nível 2",
    "MB": "Bovespa Mais",
    "MA": "Bovespa Mais Nível 2",
    "DRE": "BDR",
    "DR1": "BDR",
    "DR2": "BDR",
    "DR3": "BDR",
}


class B3Service:
    """Downloads and caches B3 listed company data (ticker, governance segment)."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._df: pd.DataFrame | None = None
        self._cache_dir = Path(settings.CACHE_DIR)
        self._parquet_path = self._cache_dir / "b3_companies.parquet"
        self._meta_path = self._cache_dir / "b3_companies.meta.json"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_fresh(self) -> bool:
        if not self._meta_path.exists():
            return False
        meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        downloaded_at = datetime.fromisoformat(meta["downloaded_at"])
        return datetime.now() - downloaded_at < timedelta(hours=settings.B3_CACHE_TTL_HOURS)

    @staticmethod
    def _label_for(market_code: str) -> str:
        code = market_code.strip()
        if code in SEGMENT_LABELS:
            return SEGMENT_LABELS[code]
        return "Tradicional" if not code else code

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def load(self) -> None:
        """Load B3 data into memory, using the on-disk parquet when fresh."""
        async with self._lock:
            if self._df is not None:
                return  # already loaded

            if self._is_fresh() and self._parquet_path.exists():
                logger.info("Loading B3 data from parquet cache")
                self._df = await asyncio.to_thread(pd.read_parquet, str(self._parquet_path))
                logger.info("B3 data loaded from cache: %d companies", len(self._df))
                return

            logger.info("Downloading B3 company data...")
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.get(settings.B3_API_URL)
                response.raise_for_status()

            results = response.json().get("results", [])
            logger.info("Downloaded %d entries from B3", len(results))

            rows = []
            for company in results:
                cnpj_digits = re.sub(r"\D", "", company.get("cnpj", ""))
                if not cnpj_digits:
                    continue
                market_code = company.get("market", "")
                rows.append(
                    {
                        "cnpj_digits": cnpj_digits,
                        "ticker": company.get("issuingCompany", "").strip() or None,
                        "market_segment": self._label_for(market_code),
                    }
                )

            df = pd.DataFrame(rows).drop_duplicates(subset=["cnpj_digits"])
            df = df.set_index("cnpj_digits")

            self._cache_dir.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(df.to_parquet, str(self._parquet_path))
            self._meta_path.write_text(
                json.dumps({"downloaded_at": datetime.now().isoformat()}),
                encoding="utf-8",
            )

            self._df = df
            logger.info("B3 data ready: %d companies", len(self._df))

    async def enrich_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add 'ticker' and 'market_segment' columns to a CVM DataFrame (by CNPJ)."""
        if self._df is None:
            try:
                await self.load()
            except Exception as exc:
                logger.warning("B3 data unavailable for enrichment: %s", exc)
                df = df.copy()
                df["ticker"] = None
                df["market_segment"] = None
                return df

        df = df.copy()
        # Normalize CVM CNPJ (e.g. "33.000.167/0001-01") to digits only
        cnpj_digits = df["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
        df["ticker"] = cnpj_digits.map(self._df["ticker"])
        df["market_segment"] = cnpj_digits.map(self._df["market_segment"])
        return df
