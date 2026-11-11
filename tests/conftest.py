import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import amostra  # noqa: E402
from delivery_insights import delivery_center  # noqa: E402


@pytest.fixture(scope="session")
def pasta(tmp_path_factory):
    """CSV de teste, no formato do Delivery Center (ver tests/amostra.py)."""
    return amostra.escrever(tmp_path_factory.mktemp("delivery_center"))


@pytest.fixture(scope="session")
def con(pasta):
    return delivery_center.criar_conexao(pasta, baixar_se_faltar=False)


@pytest.fixture(scope="session")
def brutos(pasta):
    """Os CSV crus, para conferir as métricas com um segundo cálculo em pandas."""
    return {n: pd.read_csv(pasta / f"{n}.csv", encoding="latin-1") for n in delivery_center.ARQUIVOS}
