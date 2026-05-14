import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
BETAS_PATH = DATA_DIR / "damodaran_betas.xls"
ERP_PATH = DATA_DIR / "fgv_erp.xlsx"


class ReferenceDataService:
    """Loads and serves Damodaran sector betas and FGV ERP series."""

    def __init__(self) -> None:
        self._betas_df: pd.DataFrame | None = None
        self._erp_df: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Parse both Excel files into memory. Synchronous — call once at startup."""
        self._load_betas()
        self._load_erp()
        n_ind = len(self._betas_df) if self._betas_df is not None else 0
        n_erp = len(self._erp_df) if self._erp_df is not None else 0
        logger.info("Reference data loaded: %d industries, %d ERP observations", n_ind, n_erp)

    def _load_betas(self) -> None:
        df = pd.read_excel(BETAS_PATH, sheet_name="Industry Averages", header=9)
        # Normalise column names
        df.columns = [str(c).strip() for c in df.columns]
        # Drop aggregate rows
        df = df[~df["Industry Name"].astype(str).str.startswith("Total Market")]
        df = df.dropna(subset=["Industry Name"])
        df = df[df["Industry Name"].astype(str).str.strip() != ""]
        df = df.reset_index(drop=True)
        self._betas_df = df

    def _load_erp(self) -> None:
        df = pd.read_excel(ERP_PATH, sheet_name=0, header=1)
        df.columns = ["mes", "erp"]
        df = df.dropna(subset=["mes", "erp"])
        df["mes"] = pd.to_datetime(df["mes"])
        df = df.sort_values("mes").reset_index(drop=True)
        self._erp_df = df

    # ------------------------------------------------------------------
    # Betas
    # ------------------------------------------------------------------

    def get_industries(self) -> list[str]:
        if self._betas_df is None:
            return []
        return sorted(self._betas_df["Industry Name"].dropna().tolist())

    def get_industry_data(self, name: str) -> dict | None:
        if self._betas_df is None:
            return None
        row = self._betas_df[self._betas_df["Industry Name"] == name]
        if row.empty:
            return None
        r = row.iloc[0]

        def _safe(col: str) -> float | None:
            val = r.get(col)
            try:
                return float(val) if pd.notna(val) else None
            except (TypeError, ValueError):
                return None

        return {
            "industry_name": str(r["Industry Name"]),
            "n_firms": _safe("Number of firms"),
            "beta_levered": _safe("Beta "),
            "beta_unlevered": _safe("Unlevered beta"),
            "beta_unlevered_corrected": _safe("Unlevered beta corrected for cash"),
            "de_ratio": _safe("D/E Ratio"),
            "effective_tax_rate": _safe("Effective Tax rate"),
            "cash_firm_value": _safe("Cash/Firm value"),
            "avg_beta": _safe("Average (2022-2026)"),
        }

    # ------------------------------------------------------------------
    # ERP
    # ------------------------------------------------------------------

    def get_erp_latest(self) -> float | None:
        if self._erp_df is None or self._erp_df.empty:
            return None
        return float(self._erp_df["erp"].iloc[-1])

    def get_erp_average(self, start: str | None = None, end: str | None = None) -> float | None:
        if self._erp_df is None or self._erp_df.empty:
            return None
        df = self._erp_df.copy()
        if start:
            df = df[df["mes"] >= pd.to_datetime(start)]
        if end:
            df = df[df["mes"] <= pd.to_datetime(end)]
        if df.empty:
            return None
        return float(df["erp"].mean())

    def get_erp_stats(self) -> dict:
        if self._erp_df is None or self._erp_df.empty:
            return {}
        df = self._erp_df
        latest_date = df["mes"].iloc[-1]
        avg_12m = self.get_erp_average(
            start=str((latest_date - pd.DateOffset(months=11)).date())[:7],
            end=str(latest_date.date())[:7],
        )
        avg_5y = self.get_erp_average(
            start=str((latest_date - pd.DateOffset(years=5)).date())[:7],
            end=str(latest_date.date())[:7],
        )
        return {
            "latest": self.get_erp_latest(),
            "avg_12m": avg_12m,
            "avg_5y": avg_5y,
            "avg_all": float(df["erp"].mean()),
        }

    def get_erp_series(self) -> list[dict]:
        if self._erp_df is None:
            return []
        return [
            {"date": row["mes"].strftime("%Y-%m"), "erp": round(float(row["erp"]), 6)}
            for _, row in self._erp_df.iterrows()
        ]
