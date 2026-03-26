from fastapi import APIRouter, Query

from app.api.dependencies import cache
from app.models.schemas import (
    CompanyListResponse,
    ConsolidationTypesResponse,
    StatementTypesResponse,
    YearsResponse,
)

router = APIRouter(prefix="/api/v1", tags=["metadata"])


@router.get("/years", response_model=YearsResponse)
async def list_years():
    """Return the list of available years for DFP data."""
    return YearsResponse(years=cache.get_available_years())


@router.get("/companies", response_model=CompanyListResponse)
async def list_companies(
    years: str = Query(..., description="Comma-separated years, e.g. 2023,2024"),
    q: str = Query(default="", description="Search filter for company name"),
):
    """Return distinct company names for the given years, with optional search."""
    year_list = [int(y.strip()) for y in years.split(",")]
    df = await cache.get_data(year_list)

    if df.empty:
        return CompanyListResponse(companies=[])

    companies = df["DENOM_CIA"].dropna().unique().tolist()

    if q:
        q_lower = q.lower()
        companies = [c for c in companies if q_lower in c.lower()]

    companies.sort()
    return CompanyListResponse(companies=companies)


@router.get("/statement-types", response_model=StatementTypesResponse)
async def list_statement_types(
    years: str = Query(..., description="Comma-separated years"),
):
    """Return distinct financial statement types for the given years."""
    year_list = [int(y.strip()) for y in years.split(",")]
    df = await cache.get_data(year_list)

    if df.empty:
        return StatementTypesResponse(statement_types=[])

    types = df["tipo_dem"].dropna().unique().tolist()
    types.sort()
    return StatementTypesResponse(statement_types=types)


@router.get("/consolidation-types", response_model=ConsolidationTypesResponse)
async def list_consolidation_types(
    years: str = Query(..., description="Comma-separated years"),
):
    """Return distinct consolidation types for the given years."""
    year_list = [int(y.strip()) for y in years.split(",")]
    df = await cache.get_data(year_list)

    if df.empty:
        return ConsolidationTypesResponse(consolidation_types=[])

    types = df["con_ind"].dropna().unique().tolist()
    types.sort()
    return ConsolidationTypesResponse(consolidation_types=types)
