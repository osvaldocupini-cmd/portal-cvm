import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api.dependencies import cache, reference_data
from app.models.schemas import (
    CompanyWaccInputsRequest,
    CompanyWaccInputsResponse,
    ErpStatsResponse,
    WACCRequest,
    WACCResponse,
)

router = APIRouter(prefix="/api/v1/wacc", tags=["wacc"])


# ---------------------------------------------------------------------------
# Industries
# ---------------------------------------------------------------------------

@router.get("/industries", response_model=list[str])
def list_industries():
    """List all Damodaran industry sector names."""
    return reference_data.get_industries()


# ---------------------------------------------------------------------------
# ERP Series
# ---------------------------------------------------------------------------

@router.get("/erp", response_model=ErpStatsResponse)
def get_erp():
    """Return FGV ERP statistics and full historical series."""
    stats = reference_data.get_erp_stats()
    series = reference_data.get_erp_series()
    return ErpStatsResponse(
        latest=stats.get("latest"),
        avg_12m=stats.get("avg_12m"),
        avg_5y=stats.get("avg_5y"),
        avg_all=stats.get("avg_all"),
        series=series,
    )


# ---------------------------------------------------------------------------
# Extract D/E and tax rate from CVM
# ---------------------------------------------------------------------------

@router.post("/company-inputs", response_model=CompanyWaccInputsResponse)
async def get_company_wacc_inputs(req: CompanyWaccInputsRequest):
    """Extract D/E ratio and effective tax rate from CVM financial statements."""
    df = await cache.get_year_data(req.year)
    if df.empty:
        raise HTTPException(status_code=404, detail=f"No data for year {req.year}")

    co = df[
        (df["DENOM_CIA"] == req.company) &
        (df["ORDEM_EXERC"] == "ÚLTIMO")
    ]
    if co.empty:
        raise HTTPException(status_code=404, detail=f"Company '{req.company}' not found in {req.year}")

    # Prefer consolidated — CVM uses "DF Consolidado" or "C" depending on version
    co_consol = co[co["con_ind"].isin(["DF Consolidado", "C"])]
    base = co_consol if not co_consol.empty else co

    # tipo_dem uses full Portuguese names in newer data
    bpp = base[base["tipo_dem"].str.contains("Balanço Patrimonial Passivo|BPP", case=False, na=False, regex=True)]
    dre = base[
        base["tipo_dem"].str.contains("Demonstração do Resultado|DRE", case=False, na=False, regex=True) &
        ~base["tipo_dem"].str.contains("Abrangente", case=False, na=False)
    ]

    accounts_found: dict[str, str] = {}

    def _get_by_cd(source: pd.DataFrame, cd: str) -> float | None:
        rows = source[source["CD_CONTA"].astype(str) == cd]
        if not rows.empty:
            val = rows.iloc[0]["VL_CONTA"]
            return float(val) if pd.notna(val) else None
        return None

    def _find_by_pattern(source: pd.DataFrame, patterns: list[str], cd_prefix: str | None = None) -> tuple[float | None, str]:
        sub = source.copy()
        if cd_prefix:
            sub = sub[sub["CD_CONTA"].astype(str).str.startswith(cd_prefix)]
        for pat in patterns:
            hits = sub[sub["DS_CONTA"].str.contains(pat, case=False, na=False)]
            if not hits.empty:
                hits = hits.copy()
                hits["_depth"] = hits["CD_CONTA"].astype(str).str.count(r"\.")
                row = hits.sort_values("_depth").iloc[0]
                val = row["VL_CONTA"]
                if pd.notna(val):
                    return float(val), str(row["CD_CONTA"])
        return None, ""

    # Patrimônio Líquido → CD_CONTA "2.03" is standard
    equity = _get_by_cd(bpp, "2.03")
    if equity is not None:
        accounts_found["equity"] = "2.03"
    else:
        equity, cd_eq = _find_by_pattern(bpp, ["Patrimônio Líquido", "Patrimonio Liquido"])
        if cd_eq:
            accounts_found["equity"] = cd_eq

    # Dívida CP → CD_CONTA "2.01.04" is standard
    debt_cp = _get_by_cd(bpp, "2.01.04")
    if debt_cp is not None:
        accounts_found["debt_cp"] = "2.01.04"
    else:
        debt_cp, cd = _find_by_pattern(bpp, ["Empréstimos", "Financiamentos"], cd_prefix="2.01")
        if cd:
            accounts_found["debt_cp"] = cd

    # Dívida LP → CD_CONTA "2.02.01" is standard
    debt_lp = _get_by_cd(bpp, "2.02.01")
    if debt_lp is not None:
        accounts_found["debt_lp"] = "2.02.01"
    else:
        debt_lp, cd = _find_by_pattern(bpp, ["Empréstimos", "Financiamentos"], cd_prefix="2.02")
        if cd:
            accounts_found["debt_lp"] = cd

    # LAIR → CD_CONTA "3.07" (EBT after financial results, before taxes) is the correct one
    # Fallback to "3.05" (EBIT) if 3.07 not present
    lair = _get_by_cd(dre, "3.07")
    if lair is not None:
        accounts_found["lair"] = "3.07"
    else:
        lair = _get_by_cd(dre, "3.05")
        if lair is not None:
            accounts_found["lair"] = "3.05"
        else:
            lair, cd = _find_by_pattern(dre, ["Tributos sobre o Lucro", "Antes dos Tributos", "Antes do Imposto", "LAIR"])
            if cd:
                accounts_found["lair"] = cd

    # IR + CSLL → CD_CONTA "3.08"
    tax_exp = _get_by_cd(dre, "3.08")
    if tax_exp is not None:
        accounts_found["tax"] = "3.08"
    else:
        tax_exp, cd = _find_by_pattern(dre, ["Imposto de Renda e Contribuição", "IR e CSLL", "Tributos sobre o Lucro"])
        if cd:
            accounts_found["tax"] = cd

    # Compute ratios
    total_debt = (debt_cp or 0.0) + (debt_lp or 0.0) if (debt_cp is not None or debt_lp is not None) else None
    de_ratio = (total_debt / equity) if (total_debt is not None and equity and equity != 0) else None
    eff_tax = None
    if lair and tax_exp is not None and lair != 0:
        eff_tax = abs(tax_exp / lair)
        eff_tax = min(max(eff_tax, 0.0), 1.0)

    return CompanyWaccInputsResponse(
        equity=equity,
        total_debt=total_debt,
        de_ratio=round(de_ratio, 4) if de_ratio is not None else None,
        lair=lair,
        tax_expense=tax_exp,
        effective_tax_rate=round(eff_tax, 4) if eff_tax is not None else None,
        accounts_found=accounts_found,
    )


# ---------------------------------------------------------------------------
# WACC Calculation
# ---------------------------------------------------------------------------

@router.post("/calculate", response_model=WACCResponse)
def calculate_wacc(req: WACCRequest):
    """Calculate WACC for given inputs."""
    ind = reference_data.get_industry_data(req.industry)
    if ind is None:
        raise HTTPException(status_code=404, detail=f"Industry '{req.industry}' not found")

    # Resolve ERP
    if req.erp_mode == "latest":
        erp = reference_data.get_erp_latest()
    elif req.erp_mode == "avg_12m":
        stats = reference_data.get_erp_stats()
        erp = stats.get("avg_12m")
    else:  # avg_custom
        erp = reference_data.get_erp_average(req.erp_start, req.erp_end)

    if erp is None:
        raise HTTPException(status_code=500, detail="ERP data unavailable")

    # Select beta input
    if req.beta_type == "levered":
        beta_input = ind["beta_levered"]
    elif req.beta_type == "unlevered":
        beta_input = ind["beta_unlevered"]
    else:  # unlevered_corrected
        beta_input = ind["beta_unlevered_corrected"]

    if beta_input is None:
        raise HTTPException(status_code=400, detail=f"Beta '{req.beta_type}' not available for this industry")

    # Re-lever beta (skip if user chose levered directly)
    if req.beta_type == "levered":
        beta_relevered = beta_input
    else:
        beta_relevered = beta_input * (1 + (1 - req.tax_rate) * req.de_ratio)

    # Cost of equity
    ke = req.rf + beta_relevered * erp

    # Cost of debt post-tax
    kd_post_tax = req.kd * (1 - req.tax_rate)

    # Capital structure weights
    weight_equity = 1.0 / (1.0 + req.de_ratio) if req.de_ratio >= 0 else 1.0
    weight_debt = req.de_ratio / (1.0 + req.de_ratio) if req.de_ratio >= 0 else 0.0

    # WACC
    wacc = ke * weight_equity + kd_post_tax * weight_debt

    return WACCResponse(
        wacc=round(wacc, 6),
        ke=round(ke, 6),
        kd_post_tax=round(kd_post_tax, 6),
        weight_equity=round(weight_equity, 4),
        weight_debt=round(weight_debt, 4),
        beta_input=round(beta_input, 4),
        beta_relevered=round(beta_relevered, 4),
        erp_used=round(erp, 6),
        rf_used=round(req.rf, 6),
        industry_name=req.industry,
        industry_de_ratio=ind.get("de_ratio"),
        industry_tax_rate=ind.get("effective_tax_rate"),
    )
