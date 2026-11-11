import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from delivery_insights import db  # noqa: E402
from delivery_insights.generate_data import gerar  # noqa: E402


@pytest.fixture(scope="session")
def tabelas():
    return gerar(seed=42)


@pytest.fixture(scope="session")
def con(tabelas):
    return db.criar_conexao(tabelas=tabelas)
