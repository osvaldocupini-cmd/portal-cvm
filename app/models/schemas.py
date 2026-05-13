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


class CacheRefreshResponse(BaseModel):
    status: str
    rows_loaded: int
