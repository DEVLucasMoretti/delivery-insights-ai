"""As métricas em SQL têm de bater com o mesmo cálculo feito em pandas."""
from datetime import date

import pytest

from delivery_insights import metrics
from delivery_insights.metrics import Filtros


def test_kpis_batem_com_pandas(con, tabelas):
    p = tabelas["pedidos"]
    entregues = p[p.status == "Entregue"]
    k = metrics.kpis(con, Filtros())
    assert k["pedidos"] == len(p)
    assert k["gmv"] == pytest.approx(entregues.valor_total.sum())
    assert k["ticket_medio"] == pytest.approx(entregues.valor_total.mean())
    assert k["clientes_ativos"] == p.cliente_id.nunique()
    assert k["taxa_cancelamento"] == pytest.approx((p.status == "Cancelado").mean())
    assert k["pct_no_prazo"] == pytest.approx(
        (entregues.tempo_entrega_min <= entregues.tempo_prometido_min).mean())
    assert k["avaliacao_media"] == pytest.approx(p.avaliacao.dropna().astype(float).mean())
    assert k["take_rate"] == pytest.approx(p.receita_plataforma.sum() / entregues.valor_total.sum())


def test_filtros_de_cidade_e_data(con, tabelas):
    f = Filtros(date(2025, 3, 1), date(2025, 3, 31), cidades=("Recife",))
    j = tabelas["pedidos"].merge(tabelas["restaurantes"], on="restaurante_id")
    esperado = j[(j.cidade == "Recife") & (j.data_hora >= "2025-03-01") & (j.data_hora < "2025-04-01")]
    assert metrics.kpis(con, f)["pedidos"] == len(esperado)


def test_soma_das_partes_igual_ao_todo(con):
    f = Filtros()
    total = metrics.kpis(con, f)
    for dim in ("cidade", "culinaria", "forma_pagamento"):
        d = metrics.por_dimensao(con, f, dim)
        assert d.pedidos.sum() == total["pedidos"]
        assert d.gmv.sum() == pytest.approx(total["gmv"])
    assert metrics.mapa_hora_dia(con, f).pedidos.sum() == total["pedidos"]
    partes = metrics.culinaria_por_faixa(con, f).groupby("faixa_etaria").participacao.sum()
    assert partes.values == pytest.approx(1.0)


def test_periodo_anterior():
    f = Filtros(date(2025, 12, 2), date(2025, 12, 31))
    ant = f.periodo_anterior()
    assert (ant.inicio, ant.fim) == (date(2025, 11, 2), date(2025, 12, 1))
    assert Filtros().periodo_anterior() is None  # ano inteiro: não há dados antes


def test_filtro_sem_pedidos_nao_quebra(con):
    f = Filtros(date(2025, 1, 1), date(2025, 1, 1), cidades=("Campinas",), culinarias=("Árabe",))
    assert metrics.kpis(con, f)["gmv"] >= 0
    for fn in (metrics.serie_temporal, metrics.sla_por_hora, metrics.atraso_vs_avaliacao,
               metrics.segmentos, metrics.top_restaurantes, metrics.coortes, metrics.recompra_30d):
        fn(con, f)


def test_coortes_e_recompra(con):
    co = metrics.coortes(con, Filtros())
    assert (co[co.mes_n == 0].retencao == 1).all()  # no mês 0 todos pediram, por definição
    assert co.retencao.between(0, 1).all()
    rc = metrics.recompra_30d(con, Filtros())
    assert rc.recompra_30d.between(0, 1).all() and len(rc) >= 10


def test_padroes_de_negocio_embutidos(con):
    """Os padrões que o gerador promete têm de aparecer nas métricas."""
    f = Filtros()
    atraso = metrics.atraso_vs_avaliacao(con, f)
    assert atraso.avaliacao_media.is_monotonic_decreasing  # mais atraso, pior nota
    sla = metrics.sla_por_hora(con, f).set_index("hora").pct_no_prazo
    assert sla[20] < sla[16] and sla[12] < sla[10]  # picos atrasam mais
    faixa = metrics.culinaria_por_faixa(con, f)
    top = faixa.loc[faixa.groupby("faixa_etaria").participacao.idxmax()].set_index("faixa_etaria").culinaria
    assert top["18-24"] == "Lanches" and top["55+"] == "Brasileira"
