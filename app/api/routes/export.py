import pandas as pd
from fastapi import APIRouter
from fastapi.responses import Response

from app.api.dependencies import cache
from app.api.routes.data import apply_filters, apply_segment_filter, apply_ticker_filter
from app.models.schemas import ExportRequest, QueryRequest
from app.utils.excel import dataframe_to_excel_bytes

router = APIRouter(prefix="/api/v1", tags=["export"])

EXPORT_COLUMNS = [
    "CNPJ_CIA", "DENOM_CIA", "DT_REFER", "DT_INI_EXERC", "DT_FIM_EXERC",
    "ORDEM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA", "con_ind", "tipo_dem",
]


@router.post("/export")
async def export_data(req: ExportRequest):
    """Export filtered CVM data as an Excel file."""
    df = await cache.get_data(req.years)

    if df.empty:
        return Response(
            content=dataframe_to_excel_bytes(pd.DataFrame()),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=cvm_data.xlsx"},
        )

    # Reuse the same filter logic from data route
    query_req = QueryRequest(
        years=req.years,
        companies=req.companies,
        statement_types=req.statement_types,
        consolidation=req.consolidation,
        cd_conta=req.cd_conta,
        ds_conta=req.ds_conta,
        market_segments=req.market_segments,
        has_ticker=req.has_ticker,
    )
    filtered = apply_filters(df, query_req)
    filtered = apply_segment_filter(filtered, query_req)
    filtered = apply_ticker_filter(filtered, query_req)

    # Select only relevant columns that exist
    cols = [c for c in EXPORT_COLUMNS if c in filtered.columns]
    export_df = filtered[cols]

    years_str = "_".join(str(y) for y in req.years)
    filename = f"cvm_data_{years_str}.xlsx"

    return Response(
        content=dataframe_to_excel_bytes(export_df),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
