from datetime import datetime

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    CVM_BASE_URL: str = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/"
    CACHE_DIR: str = "./cache"
    MIN_YEAR: int = 2010
    MAX_YEAR: int = datetime.now().year - 1
    CACHE_TTL_HOURS: int = 24
    PORT: int = 8000
    B3_API_URL: str = (
        "https://sistemaswebb3-listados.b3.com.br/listedCompaniesProxy"
        "/CompanyCall/GetInitialCompanies/eyJsYW5ndWFnZSI6InB0LWJyIn0="
    )
    B3_CACHE_TTL_HOURS: int = 168  # 7 days

    model_config = {"env_prefix": "CVM_"}


settings = Settings()
