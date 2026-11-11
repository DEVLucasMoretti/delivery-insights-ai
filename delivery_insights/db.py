"""Banco analítico em memória (DuckDB), de onde ele vem, e as duas formas de consultá-lo."""

from __future__ import annotations

import threading
from dataclasses import dataclass

import duckdb
import pandas as pd

from . import delivery_center, mysql_fonte, sql_guard
from .delivery_center import ESQUEMA  # noqa: F401  (reexportado para o resto do projeto)

TEMPO_LIMITE_S = 15


@dataclass
class Origem:
    tipo: str                                   # "mysql" ou "csv"
    descricao: str                              # texto curto para a tela
    varredura: mysql_fonte.Varredura | None = None


def abrir() -> tuple[duckdb.DuckDBPyConnection, Origem]:
    """Abre a camada analítica. Com DATABASE_URL, lê do MySQL; sem ela, dos CSV públicos."""
    url = mysql_fonte.url_configurada()
    if url:
        v = mysql_fonte.varrer(url)
        if v.faltam:
            raise ValueError(f"O banco {v.banco} não tem as tabelas: {', '.join(v.faltam)}. "
                             "Rode scripts/carregar_mysql.py para criá-las.")
        con = delivery_center.criar_conexao_de_tabelas(mysql_fonte.ler_tabelas(url))
        return con, Origem("mysql", f"MySQL · {v.banco}", v)
    return delivery_center.criar_conexao(), Origem("csv", "Arquivos CSV")


def criar_conexao() -> duckdb.DuckDBPyConnection:
    return abrir()[0]


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
