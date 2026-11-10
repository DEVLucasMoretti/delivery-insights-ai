"""Banco analítico em memória (DuckDB) carregado com os dados sintéticos."""

from __future__ import annotations

import threading

import duckdb
import pandas as pd

from . import sql_guard
from .generate_data import gerar

TEMPO_LIMITE_S = 15

VIEW_PEDIDOS = """
CREATE VIEW v_pedidos AS
SELECT
    p.*,
    CAST(p.data_hora AS DATE)                    AS data_pedido,
    CAST(date_trunc('month', p.data_hora) AS DATE) AS mes,
    hour(p.data_hora)                            AS hora,
    isodow(p.data_hora)                          AS dia_semana_num,
    CASE isodow(p.data_hora)
        WHEN 1 THEN 'Seg' WHEN 2 THEN 'Ter' WHEN 3 THEN 'Qua' WHEN 4 THEN 'Qui'
        WHEN 5 THEN 'Sex' WHEN 6 THEN 'Sáb' ELSE 'Dom' END AS dia_semana,
    p.status = 'Entregue'                        AS entregue,
    CASE WHEN p.status = 'Entregue'
         THEN p.tempo_entrega_min <= p.tempo_prometido_min END AS no_prazo,
    r.nome AS restaurante, r.culinaria, r.cidade, r.uf, r.nivel_preco,
    c.faixa_etaria, c.canal_aquisicao, c.assinante_clube
FROM pedidos p
JOIN restaurantes r USING (restaurante_id)
JOIN clientes c USING (cliente_id)
"""

# Descrição do esquema entregue ao agente de IA (e mostrada no README).
ESQUEMA = """
Tabela pedidos (1 linha por pedido, ano de 2025)
  pedido_id, cliente_id, restaurante_id
  data_hora TIMESTAMP
  status VARCHAR                 -- 'Entregue' ou 'Cancelado'
  valor_itens DOUBLE             -- R$ dos itens
  taxa_entrega DOUBLE            -- R$ (0 = frete grátis)
  desconto DOUBLE                -- R$ de cupom
  valor_total DOUBLE             -- valor_itens + taxa_entrega - desconto
  receita_plataforma DOUBLE      -- comissão + parte da taxa de entrega (0 se cancelado)
  cupom_usado BOOLEAN
  forma_pagamento VARCHAR        -- 'Pix','Crédito','Débito','Vale-refeição','Dinheiro'
  plataforma VARCHAR             -- 'Android','iOS','Web'
  distancia_km DOUBLE
  tempo_prometido_min INTEGER    -- prazo mostrado ao cliente
  tempo_entrega_min INTEGER      -- tempo real; NULL se cancelado
  avaliacao INTEGER              -- 1 a 5; NULL se o cliente não avaliou

Tabela restaurantes
  restaurante_id, nome, culinaria, cidade, uf
  nivel_preco INTEGER            -- 1 (barato) a 3 (caro)
  taxa_comissao DOUBLE           -- fração, ex.: 0.18
  data_cadastro DATE

Tabela clientes
  cliente_id, cidade, uf
  faixa_etaria VARCHAR           -- '18-24','25-34','35-44','45-54','55+'
  data_cadastro DATE
  canal_aquisicao VARCHAR        -- 'Orgânico','Indicação','Redes sociais','Busca paga','Parcerias'
  assinante_clube BOOLEAN        -- assinante do clube de frete grátis

View v_pedidos (PREFIRA ESTA): pedidos já unidos a restaurantes e clientes, com colunas extra
  data_pedido DATE, mes DATE (1º dia do mês), hora INTEGER (0-23),
  dia_semana VARCHAR ('Seg'..'Dom'), dia_semana_num INTEGER (1=Seg .. 7=Dom),
  entregue BOOLEAN, no_prazo BOOLEAN (NULL se cancelado),
  restaurante, culinaria, cidade, uf, nivel_preco,
  faixa_etaria, canal_aquisicao, assinante_clube

Valores de culinaria: 'Lanches','Pizza','Brasileira','Marmita','Japonesa','Açaí',
  'Saudável','Doces & Bolos','Italiana','Árabe'
Valores de cidade: 'São Paulo','Rio de Janeiro','Belo Horizonte','Brasília','Curitiba',
  'Porto Alegre','Salvador','Recife','Fortaleza','Campinas'
""".strip()


def criar_conexao(seed: int = 42, tabelas: dict[str, pd.DataFrame] | None = None) -> duckdb.DuckDBPyConnection:
    """Cria o banco em memória, carrega as tabelas e tranca o acesso a ficheiros e rede."""
    tabelas = tabelas or gerar(seed=seed)
    con = duckdb.connect(":memory:")
    for nome, df in tabelas.items():
        con.register("_df", df)
        con.execute(f"CREATE TABLE {nome} AS SELECT * FROM _df")
        con.unregister("_df")
    con.execute(VIEW_PEDIDOS)
    # Depois de carregar: nada de ler ficheiros, instalar extensões ou mudar configuração.
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def consultar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> pd.DataFrame:
    """Consulta interna do dashboard (SQL escrito por nós, com parâmetros)."""
    return con.cursor().execute(sql, params or []).df()


def consultar_seguro(con: duckdb.DuckDBPyConnection, sql: str,
                     max_linhas: int = sql_guard.MAX_LINHAS) -> pd.DataFrame:
    """Consulta vinda do agente de IA: validada, limitada em linhas e em tempo."""
    protegido = sql_guard.com_limite(sql, max_linhas)
    cur = con.cursor()
    relogio = threading.Timer(TEMPO_LIMITE_S, cur.interrupt)
    relogio.start()
    try:
        return cur.execute(protegido).df()
    finally:
        relogio.cancel()
