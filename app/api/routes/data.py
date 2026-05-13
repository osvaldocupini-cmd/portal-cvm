import pandas as pd
from fastapi import APIRouter, HTTPException

from app.api.dependencies import b3_service, cache
from app.models.schemas import FinancialRecord, QueryRequest, QueryResponse

router = APIRouter(prefix="/api/v1", tags=["data"])


def apply_filters(df: pd.DataFrame, req: QueryRequest) -> pd.DataFrame:
    """Apply user filters to the DataFrame."""
    if df.empty:
        return df

    if req.companies:
        df = df[df["DENOM_CIA"].isin(req.companies)]

    if req.statement_types:
        df = df[df["tipo_dem"].isin(req.statement_types)]

    if req.consolidation:
        df = df[df["con_ind"] == req.consolidation]

    if req.cd_conta:
        df = df[df["CD_CONTA"].isin(req.cd_conta)]

    if req.ds_conta:
        df = df[df["DS_CONTA"].str.contains(req.ds_conta, case=False, na=False)]

    return df


def apply_segment_filter(df: pd.DataFrame, req: QueryRequest) -> pd.DataFrame:
    """Filter rows by B3 governance segment using a CNPJ lookup."""
    if not req.market_segments or df.empty:
        return df
    cnpjs = b3_service.get_cnpjs_for_segments(req.market_segments)
    if not cnpjs:
        return df  # B3 data unavailable — skip filter rather than return empty
    cnpj_digits = df["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
    return df[cnpj_digits.isin(cnpjs)]


def apply_ticker_filter(df: pd.DataFrame, req: QueryRequest) -> pd.DataFrame:
    """Filter rows by ticker presence using CNPJ lookup."""
    if req.has_ticker is None or df.empty:
        return df
    cnpjs_with_ticker = b3_service.get_cnpjs_with_ticker()
    if not cnpjs_with_ticker:
        return df  # B3 data unavailable — skip filter
    cnpj_digits = df["CNPJ_CIA"].str.replace(r"\D", "", regex=True)
    if req.has_ticker:
        return df[cnpj_digits.isin(cnpjs_with_ticker)]
    else:
        return df[~cnpj_digits.isin(cnpjs_with_ticker)]


async def apply_base_year_filter(df: pd.DataFrame, req: QueryRequest) -> pd.DataFrame:
    """Keep only companies (by CNPJ) that filed a DFP in the base year."""
    if req.base_year is None or df.empty:
        return df
    base_df = await cache.get_year_data(req.base_year)
    if base_df.empty:
        return df  # base year data unavailable — skip filter
    base_cnpjs = set(base_df["CNPJ_CIA"].unique())
    return df[df["CNPJ_CIA"].isin(base_cnpjs)]


def df_to_records(df: pd.DataFrame) -> list[FinancialRecord]:
    """Convert DataFrame rows to Pydantic models."""
    records = []
    for _, row in df.iterrows():
        records.append(
            FinancialRecord(
                denom_cia=str(row.get("DENOM_CIA", "")),
                cnpj_cia=str(row.get("CNPJ_CIA", "")),
                dt_refer=str(row.get("DT_REFER", "")),
                dt_ini_exerc=str(row.get("DT_INI_EXERC", "")) if pd.notna(row.get("DT_INI_EXERC")) else None,
                dt_fim_exerc=str(row.get("DT_FIM_EXERC", "")) if pd.notna(row.get("DT_FIM_EXERC")) else None,
                ordem_exerc=str(row.get("ORDEM_EXERC", "")),
                cd_conta=str(row.get("CD_CONTA", "")),
                ds_conta=str(row.get("DS_CONTA", "")),
                ticker=str(row["ticker"]) if pd.notna(row.get("ticker")) else None,
                market_segment=str(row["market_segment"]) if pd.notna(row.get("market_segment")) else None,
                vl_conta=float(row["VL_CONTA"]) if pd.notna(row.get("VL_CONTA")) else None,
                con_ind=str(row.get("con_ind", "")),
                tipo_dem=str(row.get("tipo_dem", "")),
            )
        )
    return records


@router.post("/query", response_model=QueryResponse)
async def query_data(req: QueryRequest):
    """Query CVM financial data with filters and pagination."""
    df = await cache.get_data(req.years)

    if df.empty:
        return QueryResponse(total_rows=0, page=req.page, page_size=req.page_size, data=[])

    filtered = apply_filters(df, req)
    filtered = apply_segment_filter(filtered, req)
    filtered = apply_ticker_filter(filtered, req)
    filtered = await apply_base_year_filter(filtered, req)
    total_rows = len(filtered)

    # Pagination
    start = (req.page - 1) * req.page_size
    end = start + req.page_size

    if start >= total_rows:
        raise HTTPException(status_code=400, detail=f"Page {req.page} is out of range (total: {total_rows} rows)")

    page_df = await b3_service.enrich_dataframe(filtered.iloc[start:end])
    records = df_to_records(page_df)

    return QueryResponse(
        total_rows=total_rows,
        page=req.page,
        page_size=req.page_size,
        data=records,
    )
