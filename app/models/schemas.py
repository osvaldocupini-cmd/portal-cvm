from typing import Literal

from pydantic import BaseModel, Field


class YearsResponse(BaseModel):
    years: list[int]


class CompanyListResponse(BaseModel):
    companies: list[str]


class StatementTypesResponse(BaseModel):
    statement_types: list[str]


class ConsolidationTypesResponse(BaseModel):
    consolidation_types: list[str]


class QueryRequest(BaseModel):
    years: list[int]
    companies: list[str] | None = None
    statement_types: list[str] | None = None
    consolidation: str | None = None
    cd_conta: list[str] | None = None
    ds_conta: str | None = None
    market_segments: list[str] | None = None
    has_ticker: bool | None = None
    base_year: int | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=100, ge=1, le=5000)


class FinancialRecord(BaseModel):
    denom_cia: str
    cnpj_cia: str
    ticker: str | None = None
    market_segment: str | None = None
    dt_refer: str
    dt_ini_exerc: str | None
    dt_fim_exerc: str | None
    ordem_exerc: str
    cd_conta: str
    ds_conta: str
    vl_conta: float | None
    con_ind: str
    tipo_dem: str


class QueryResponse(BaseModel):
    total_rows: int
    page: int
    page_size: int
    data: list[FinancialRecord]


class ExportRequest(BaseModel):
    years: list[int]
    companies: list[str] | None = None
    statement_types: list[str] | None = None
    consolidation: str | None = None
    cd_conta: list[str] | None = None
    ds_conta: str | None = None
    market_segments: list[str] | None = None
    has_ticker: bool | None = None
    base_year: int | None = None


class CacheRefreshResponse(BaseModel):
    status: str
    rows_loaded: int


# ---------------------------------------------------------------------------
# WACC schemas
# ---------------------------------------------------------------------------

class ErpStatsResponse(BaseModel):
    latest: float | None
    avg_12m: float | None
    avg_5y: float | None
    avg_all: float | None
    series: list[dict]


class CompanyWaccInputsRequest(BaseModel):
    company: str
    year: int


class CompanyWaccInputsResponse(BaseModel):
    equity: float | None = None
    total_debt: float | None = None
    de_ratio: float | None = None
    lair: float | None = None
    tax_expense: float | None = None
    effective_tax_rate: float | None = None
    accounts_found: dict[str, str] = {}


class WACCRequest(BaseModel):
    industry: str
    beta_type: Literal["levered", "unlevered", "unlevered_corrected"]
    de_ratio: float
    tax_rate: float
    rf: float
    erp_mode: Literal["latest", "avg_12m", "avg_custom"]
    erp_start: str | None = None
    erp_end: str | None = None
    kd: float


class WACCResponse(BaseModel):
    wacc: float
    ke: float
    kd_post_tax: float
    weight_equity: float
    weight_debt: float
    beta_input: float
    beta_relevered: float
    erp_used: float
    rf_used: float
    industry_name: str
    industry_de_ratio: float | None
    industry_tax_rate: float | None
