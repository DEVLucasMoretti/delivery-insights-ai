"""Métricas de negócio, todas calculadas em SQL sobre a view v_pedidos.

Definições (as mesmas que o assistente recebe no prompt):

- Vendas (GMV)        = soma do valor dos pedidos FINALIZADOS
- Ticket médio        = GMV / pedidos finalizados com valor válido
- Cancelamento        = pedidos cancelados / pedidos feitos
- Tempo total         = minutos do pedido criado até concluído; usamos a MEDIANA, porque
                        alguns pedidos ficam abertos por horas e distorcem a média
- Em até 60 min       = pedidos finalizados com tempo total <= 60 min / finalizados com tempo
- Frete coberto       = taxa de entrega cobrada / custo da entrega (100% = a taxa paga a entrega)
- Lojas ativas        = lojas distintas com pelo menos um pedido no período

O conjunto não tem clientes, avaliações nem prazo prometido, por isso não há
retenção, nota média nem "entregue no prazo".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

import pandas as pd

from .db import consultar

DATA_MIN = date(2020, 12, 31)  # os primeiros pedidos de 01/01 (UTC) caem na noite de 31/12 em Brasília
DATA_MAX = date(2021, 4, 30)
META_MINUTOS = 60

DIMENSOES = ("cidade", "segmento", "tipo_canal", "canal", "hub", "modal_entrega", "tipo_entregador", "faixa_valor")
FAIXAS_VALOR = ("Até R$ 50", "R$ 50 a 100", "R$ 100 a 200", "Acima de R$ 200")

# campo do Filtros -> coluna da view v_pedidos
COLUNAS_FILTRO = {"cidades": "cidade", "segmentos": "segmento", "tipos_canal": "tipo_canal", "canais": "canal",
                  "hubs": "hub", "modais": "modal_entrega", "faixas_valor": "faixa_valor"}


@dataclass(frozen=True)
class Filtros:
    inicio: date = DATA_MIN
    fim: date = DATA_MAX
    cidades: tuple = ()
    segmentos: tuple = ()
    tipos_canal: tuple = ()
    canais: tuple = ()
    hubs: tuple = ()
    modais: tuple = ()
    faixas_valor: tuple = ()

    def where(self, com_datas: bool = True) -> tuple[str, list]:
        cond, params = ["TRUE"], []
        if com_datas:
            cond.append("data_pedido BETWEEN ? AND ?")
            params += [self.inicio, self.fim]
        for campo, coluna in COLUNAS_FILTRO.items():
            valores = getattr(self, campo)
            if valores:
                cond.append(f"{coluna} IN ({', '.join('?' * len(valores))})")
                params += list(valores)
        return " AND ".join(cond), params

    def ativos(self) -> list[str]:
        """Valores escolhidos no recorte, para mostrar como pílulas."""
        return [v for campo in COLUNAS_FILTRO for v in getattr(self, campo)]

    def periodo_anterior(self) -> "Filtros | None":
        """Período imediatamente anterior, com a mesma duração (None se sair dos dados)."""
        dias = (self.fim - self.inicio).days + 1
        inicio = self.inicio - timedelta(days=dias)
        if inicio < DATA_MIN:
            return None
        return replace(self, inicio=inicio, fim=self.inicio - timedelta(days=1))


_MEDIDAS = f"""
    count(*)                                                AS pedidos,
    coalesce(sum(valor) FILTER (WHERE finalizado), 0)       AS gmv,
    avg(valor) FILTER (WHERE finalizado)                    AS ticket_medio,
    count(DISTINCT loja_id)                                 AS lojas_ativas,
    avg(CAST(NOT finalizado AS INT))                        AS taxa_cancelamento,
    median(tempo_total_min) FILTER (WHERE finalizado)       AS tempo_mediano_min,
    avg(CAST(tempo_total_min <= {META_MINUTOS} AS INT)) FILTER (WHERE finalizado) AS pct_ate_60,
    sum(taxa_entrega) FILTER (WHERE finalizado AND custo_entrega IS NOT NULL)
        / nullif(sum(custo_entrega) FILTER (WHERE finalizado), 0) AS frete_coberto,
    median(distancia_km) FILTER (WHERE finalizado)          AS distancia_mediana_km
"""


def kpis(con, f: Filtros) -> dict:
    where, params = f.where()
    return consultar(con, f"SELECT {_MEDIDAS} FROM v_pedidos WHERE {where}", params).iloc[0].to_dict()


def kpis_com_variacao(con, f: Filtros) -> tuple[dict, dict | None]:
    """KPIs do período e do período anterior equivalente (para mostrar a variação)."""
    anterior = f.periodo_anterior()
    return kpis(con, f), (kpis(con, anterior) if anterior else None)


def serie_kpis(con, f: Filtros, grao: str = "week") -> pd.DataFrame:
    """Indicadores principais por dia, semana ou mês (série de vendas e mini-gráficos)."""
    assert grao in ("day", "week", "month")
    where, params = f.where()
    return consultar(con, f"""
        SELECT CAST(date_trunc('{grao}', data_pedido) AS DATE) AS periodo,
               count(*) AS pedidos,
               sum(valor) FILTER (WHERE finalizado) AS gmv,
               avg(valor) FILTER (WHERE finalizado) AS ticket_medio,
               count(DISTINCT loja_id) AS lojas_ativas
        FROM v_pedidos WHERE {where} GROUP BY 1 ORDER BY 1""", params)


def por_dimensao(con, f: Filtros, dimensao: str, limite: int | None = None) -> pd.DataFrame:
    assert dimensao in DIMENSOES
    where, params = f.where()
    corte = f"LIMIT {int(limite)}" if limite else ""
    df = consultar(con, f"""
        SELECT {dimensao}, {_MEDIDAS}
        FROM v_pedidos WHERE {where} AND {dimensao} IS NOT NULL
        GROUP BY 1 ORDER BY gmv DESC {corte}""", params)
    df["participacao"] = df["pedidos"] / df["pedidos"].sum() if len(df) else []
    return df


def mapa_hora_dia(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT dia_semana_num, dia_semana, hora, count(*) AS pedidos
        FROM v_pedidos WHERE {where} GROUP BY 1, 2, 3 ORDER BY 1, 3""", params)


def tempo_por_hora(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT hora, count(*) AS pedidos,
               median(tempo_total_min) AS tempo_mediano_min,
               avg(CAST(tempo_total_min <= {META_MINUTOS} AS INT)) AS pct_ate_60
        FROM v_pedidos WHERE {where} AND finalizado AND tempo_total_min IS NOT NULL
        GROUP BY 1 HAVING count(*) >= 50 ORDER BY 1""", params)


def etapas(con, f: Filtros) -> pd.DataFrame:
    """Onde o tempo vai: mediana de cada etapa do pedido, da loja até a porta."""
    where, params = f.where()
    linha = consultar(con, f"""
        SELECT median(tempo_preparo_min) AS preparo, median(tempo_expedicao_min) AS expedicao,
               median(tempo_transito_min) AS transito
        FROM v_pedidos WHERE {where} AND finalizado""", params).iloc[0]
    return pd.DataFrame({
        "etapa": ["Preparo na loja", "Espera até sair", "Trânsito até o cliente"],
        "minutos": [linha["preparo"], linha["expedicao"], linha["transito"]],
    }).dropna()


def distancia_vs_transito(con, f: Filtros) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT CASE WHEN distancia_km <= 1 THEN 1 WHEN distancia_km <= 2 THEN 2
                    WHEN distancia_km <= 3 THEN 3 WHEN distancia_km <= 5 THEN 4 ELSE 5 END AS ordem,
               CASE WHEN distancia_km <= 1 THEN 'Até 1 km' WHEN distancia_km <= 2 THEN '1 a 2 km'
                    WHEN distancia_km <= 3 THEN '2 a 3 km' WHEN distancia_km <= 5 THEN '3 a 5 km'
                    ELSE 'Mais de 5 km' END AS distancia,
               count(*) AS pedidos, median(tempo_transito_min) AS transito_mediano_min
        FROM v_pedidos
        WHERE {where} AND finalizado AND distancia_km IS NOT NULL AND tempo_transito_min IS NOT NULL
        GROUP BY 1, 2 ORDER BY 1""", params)


def pagamentos(con, f: Filtros) -> pd.DataFrame:
    """Participação de cada método no valor pago (um pedido pode ter mais de um pagamento)."""
    where, params = f.where()
    return consultar(con, f"""
        SELECT g.metodo, count(*) AS pagamentos, sum(g.valor) AS valor,
               sum(g.valor) / sum(sum(g.valor)) OVER () AS participacao
        FROM pagamentos g JOIN v_pedidos p USING (pedido_id)
        WHERE {where} AND g.status = 'Pago' AND g.valor <= 10000
        GROUP BY 1 ORDER BY valor DESC""", params)


def top_lojas(con, f: Filtros, n: int = 10) -> pd.DataFrame:
    where, params = f.where()
    return consultar(con, f"""
        SELECT loja, segmento, cidade, count(*) AS pedidos,
               sum(valor) FILTER (WHERE finalizado) AS gmv,
               median(tempo_total_min) FILTER (WHERE finalizado) AS tempo_mediano_min,
               avg(CAST(NOT finalizado AS INT)) AS taxa_cancelamento
        FROM v_pedidos WHERE {where} GROUP BY 1, 2, 3 ORDER BY gmv DESC NULLS LAST LIMIT {int(n)}""", params)
