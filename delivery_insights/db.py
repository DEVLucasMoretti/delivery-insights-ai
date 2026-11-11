"""Banco analítico em memória (DuckDB) e as duas formas de consultá-lo."""

from __future__ import annotations

import threading

import duckdb
import pandas as pd

from . import sql_guard
from .delivery_center import ESQUEMA, criar_conexao  # noqa: F401  (reexportados para o resto do projeto)

TEMPO_LIMITE_S = 15


def consultar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    """Consulta interna do painel (SQL escrito por nós, com parâmetros)."""
    return con.cursor().execute(sql, params or []).df()


def consultar_seguro(con: duckdb.DuckDBPyConnection, sql: str,
                     max_linhas: int = sql_guard.MAX_LINHAS) -> pd.DataFrame:
    """Consulta vinda do assistente: validada, limitada em linhas e em tempo."""
    protegido = sql_guard.com_limite(sql, max_linhas)
    cur = con.cursor()
    relogio = threading.Timer(TEMPO_LIMITE_S, cur.interrupt)
    relogio.start()
    try:
        return cur.execute(protegido).df()
    finally:
        relogio.cancel()
