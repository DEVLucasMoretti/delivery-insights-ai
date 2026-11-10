"""Métricas de negócio do marketplace, todas calculadas em SQL sobre a view v_pedidos.

Definições (as mesmas que o agente de IA recebe no prompt):

- GMV              = soma de valor_total dos pedidos ENTREGUES
- Ticket médio     = GMV / pedidos entregues
- Take rate        = receita_plataforma / GMV
- Cancelamento     = pedidos cancelados / pedidos feitos
- No prazo (SLA)   = pedidos entregues com tempo_entrega_min <= tempo_prometido_min
- Clientes ativos  = clientes distintos com pelo menos 1 pedido no período
- Recompra 30 dias = clientes novos que fazem o 2º pedido até 30 dias depois do 1º
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from .db import consultar

DATA_MIN = date(2025, 1, 1)
DATA_MAX = date(2025, 12, 31)


@dataclass(frozen=True)
class Filtros:
    inicio: date = DATA_MIN
    fim: date = DATA_MAX
    cidades: tuple = ()
    culinarias: tuple = ()

    def where(self, com_datas: bool = True) -> tuple[str, list]:
        cond, params = ["TRUE"], []
        if com_datas:
            cond.append("data_pedido BETWEEN ? AND ?")
            params += [self.inicio, self.fim]
        for coluna, valores in (("cidade", self.cidades), ("culinaria", self.culinarias)):
            if valores:
                cond.append(f"{coluna} IN ({', '.join('?' * len(valores))})")
                params += list(valores)
        return " AND ".join(cond), params

    def periodo_anterior(self) -> "Filtros | None":
        """Período imediatamente anterior, com a mesma duração (None se sair dos dados)."""
        dias = (self.fim - self.inicio).days + 1
        inicio = self.inicio - timedelta(days=dias)
        if inicio < DATA_MIN:
            return None
        return Filtros(inicio, self.inicio - timedelta(days=1), self.cidades, self.culinarias)


_KPIS = """
SELECT
    count(*)                                              AS pedidos,
    coalesce(sum(valor_total) FILTER (WHERE entregue), 0) AS gmv,
    avg(valor_total) FILTER (WHERE entregue)              AS ticket_medio,
    count(DISTINCT cliente_id)                            AS clientes_ativos,
    avg(CAST(NOT entregue AS INT))                        AS taxa_cancelamento,
    avg(tempo_entrega_min)                                AS tempo_medio_min,
    avg(CAST(no_prazo AS INT))                            AS pct_no_prazo,
    avg(avaliacao)                                        AS avaliacao_media,
    coalesce(sum(receita_plataforma), 0)                  AS receita,
    sum(receita_plataforma) / nullif(sum(valor_total) FILTER (WHERE entregue), 0) AS take_rate
FROM v_pedidos WHERE {where}
"""


def kpis(con, f: Filtros) -> dict:
    where, params = f.where()
    return consultar(con, _KPIS.format(where=where), params).iloc[0].to_dict()


def kpis_com_variacao(con, f: Filtros) -> tuple[dict, dict | None]:
    """KPIs do período e do período anterior equivalente (para mostrar a variação)."""
    anterior = f.periodo_anterior()
    return kpis(con, f), (kpis(con, anterior) if anterior else None)


def serie_temporal(con, f: Filtros, grao: str = "week") -> pd.DataFrame:
    assert grao in ("day", "week", "month")
    where, params = f.where()
    return consultar(con, f"""
        SELECT CAST(date_trunc('{grao}', data_pedido) AS DATE) AS periodo,
               count(*) AS pedidos,
               sum(valor_total) FILTER (WHERE entregue) AS gmv
        FROM v_pedidos WHERE {where} GROUP BY 1 ORDER BY 1""", params)


def por_dimensao(con, f: Filtros, dimensao: str) -> pd.DataFrame:
    assert dimensao in ("culinaria", "cidade", "faixa_etaria", "forma_pagamento",
                        "plataforma", "canal_aquisicao")
    where, params = f.where()
    return consultar(con, f"""
        SELECT {dimensao},
               count(*) AS pedidos,
               sum(valor_total) FILTER (WHERE entregue) AS gmv,
               avg(valor_total) FILTER (WHERE entregue) AS ticket_medio,
               avg(tempo_entrega_min) AS tempo_medio_min,
               avg(CAST(no_prazo AS INT)) AS pct_no_prazo,
               avg(CAST(NOT entregue AS INT)) AS taxa_cancelamento,
               avg(avaliacao) AS avaliacao_media
        FROM v_pedidos WHERE {where} GROUP BY 1 ORDER BY gmv DESC""", params)


def mapa_hora_dia(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT dia_semana_num, dia_semana, hora, count(*) AS pedidos
        FROM v_pedidos WHERE {where} GROUP BY 1, 2, 3 ORDER BY 1, 3""", params)


def culinaria_por_faixa(con, f: Filtros) -> pd.DataFrame:
    """Participação de cada culinária dentro de cada faixa etária (soma 100% por faixa)."""
    where, params = f.where()
    return consultar(con, f"""
        SELECT faixa_etaria, culinaria, count(*) AS pedidos,
               count(*) / sum(count(*)) OVER (PARTITION BY faixa_etaria) AS participacao
        FROM v_pedidos WHERE {where} GROUP BY 1, 2 ORDER BY 1, 2""", params)


def sla_por_hora(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT hora, count(*) AS pedidos,
               avg(CAST(no_prazo AS INT)) AS pct_no_prazo,
               avg(tempo_entrega_min) AS tempo_medio_min
        FROM v_pedidos WHERE {where} AND entregue
        GROUP BY 1 HAVING count(*) >= 30 ORDER BY 1""", params)


def atraso_vs_avaliacao(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        WITH b AS (
            SELECT avaliacao, tempo_entrega_min - tempo_prometido_min AS atraso
            FROM v_pedidos WHERE {where} AND avaliacao IS NOT NULL)
        SELECT CASE WHEN atraso <= 0 THEN 1 WHEN atraso <= 10 THEN 2
                    WHEN atraso <= 20 THEN 3 ELSE 4 END AS ordem,
               CASE WHEN atraso <= 0 THEN 'No prazo' WHEN atraso <= 10 THEN 'Até 10 min'
                    WHEN atraso <= 20 THEN '11 a 20 min' ELSE 'Mais de 20 min' END AS atraso,
               avg(avaliacao) AS avaliacao_media, count(*) AS avaliacoes
        FROM b GROUP BY 1, 2 ORDER BY 1""", params)


_NOVOS = """
novos AS (  -- clientes cadastrados em 2025, com o mês do 1º pedido entregue
    SELECT cliente_id, min(data_pedido) AS primeiro, CAST(date_trunc('month', min(data_pedido)) AS DATE) AS coorte
    FROM v_pedidos
    WHERE entregue AND {where}
      AND cliente_id IN (SELECT cliente_id FROM clientes WHERE data_cadastro >= DATE '2025-01-01')
    GROUP BY 1)
"""


def coortes(con, f: Filtros) -> pd.DataFrame:
    """Retenção mensal: % dos clientes novos de cada mês que voltam a pedir N meses depois.

    Usa o ano inteiro (ignora o filtro de datas), respeitando cidade e culinária.
    """
    where, params = f.where(com_datas=False)
    return consultar(con, f"""
        WITH {_NOVOS.format(where=where)},
        atividade AS (
            SELECT DISTINCT cliente_id, mes FROM v_pedidos WHERE entregue AND {where}),
        tamanho AS (SELECT coorte, count(*) AS clientes FROM novos GROUP BY 1)
        SELECT n.coorte, datediff('month', n.coorte, a.mes) AS mes_n,
               t.clientes, count(*) / t.clientes AS retencao
        FROM novos n JOIN atividade a USING (cliente_id) JOIN tamanho t USING (coorte)
        GROUP BY 1, 2, 3 ORDER BY 1, 2""", params + params)


def recompra_30d(con, f: Filtros) -> pd.DataFrame:
    """% de clientes novos que fazem o 2º pedido em até 30 dias, por mês do 1º pedido."""
    where, params = f.where(com_datas=False)
    return consultar(con, f"""
        WITH {_NOVOS.format(where=where)},
        segundo AS (
            SELECT n.cliente_id, min(p.data_pedido) AS segundo
            FROM novos n JOIN v_pedidos p USING (cliente_id)
            WHERE p.entregue AND p.data_hora > (
                SELECT min(data_hora) FROM pedidos x
                WHERE x.cliente_id = n.cliente_id AND x.status = 'Entregue')
            GROUP BY 1)
        SELECT n.coorte, count(*) AS clientes_novos,
               avg(CAST(s.segundo IS NOT NULL AND s.segundo <= n.primeiro + 30 AS INT)) AS recompra_30d
        FROM novos n LEFT JOIN segundo s USING (cliente_id)
        WHERE n.primeiro <= DATE '{DATA_MAX}' - 30   -- só quem já teve 30 dias para voltar
        GROUP BY 1 HAVING count(*) >= 30 ORDER BY 1""", params)


def segmentos(con, f: Filtros) -> pd.DataFrame:
    """Segmentação simples por recência e frequência (RFM), com data de referência = fim do filtro."""
    where, params = f.where()
    return consultar(con, f"""
        WITH c AS (
            SELECT cliente_id,
                   datediff('day', max(data_pedido), CAST(? AS DATE)) AS recencia,
                   count(*) AS frequencia, sum(valor_total) AS valor
            FROM v_pedidos WHERE {where} AND entregue GROUP BY 1)
        SELECT CASE WHEN recencia > 90 THEN 5 WHEN recencia > 30 THEN 4
                    WHEN frequencia >= 8 THEN 1 WHEN frequencia >= 3 THEN 2 ELSE 3 END AS ordem,
               CASE WHEN recencia > 90 THEN 'Inativos (90+ dias)'
                    WHEN recencia > 30 THEN 'Em risco (31-90 dias)'
                    WHEN frequencia >= 8 THEN 'Campeões (8+ pedidos)'
                    WHEN frequencia >= 3 THEN 'Fiéis (3-7 pedidos)'
                    ELSE 'Ocasionais (1-2 pedidos)' END AS segmento,
               count(*) AS clientes, sum(valor) AS gmv, avg(frequencia) AS pedidos_por_cliente
        FROM c GROUP BY 1, 2 ORDER BY 1""", [f.fim] + params)


def top_restaurantes(con, f: Filtros, n: int = 10) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT restaurante, culinaria, cidade, count(*) AS pedidos,
               sum(valor_total) FILTER (WHERE entregue) AS gmv,
               avg(avaliacao) AS avaliacao_media,
               avg(CAST(NOT entregue AS INT)) AS taxa_cancelamento
        FROM v_pedidos WHERE {where} GROUP BY 1, 2, 3 ORDER BY gmv DESC LIMIT {int(n)}""", params)
