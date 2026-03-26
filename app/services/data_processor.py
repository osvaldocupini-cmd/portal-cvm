import logging
import zipfile
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "CNPJ_CIA": "cnpj_cia",
    "DENOM_CIA": "denom_cia",
    "DT_REFER": "dt_refer",
    "DT_INI_EXERC": "dt_ini_exerc",
    "DT_FIM_EXERC": "dt_fim_exerc",
    "ORDEM_EXERC": "ordem_exerc",
    "CD_CONTA": "cd_conta",
    "DS_CONTA": "ds_conta",
    "VL_CONTA": "vl_conta",
    "GRUPO_DFP": "grupo_dfp",
}


def process_zip_to_dataframe(zip_path: Path) -> pd.DataFrame:
    """Extract all CSVs from a CVM DFP ZIP and return a clean DataFrame."""
    logger.info("Processing ZIP: %s", zip_path)

    frames: list[pd.DataFrame] = []

    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            df = pd.read_csv(
                zf.open(name),
                sep=";",
                encoding="ISO-8859-1",
                dtype={"ORDEM_EXERC": "category"},
            )
            frames.append(df)

    if not frames:
        logger.warning("No CSV files found in %s", zip_path)
        return pd.DataFrame()

    data = pd.concat(frames, ignore_index=True)
    logger.info("Concatenated %d rows from %d CSVs", len(data), len(frames))

    # Split GRUPO_DFP into consolidation type and statement type
    if "GRUPO_DFP" in data.columns:
        split = data["GRUPO_DFP"].str.split("-", n=1, expand=True)
        data["con_ind"] = split[0].str.strip()
        data["tipo_dem"] = split[1].str.strip() if 1 in split.columns else ""

    # Filter out penultimate exercise
    if "ORDEM_EXERC" in data.columns:
        data = data[data["ORDEM_EXERC"] != "PENÚLTIMO"]

    return data
