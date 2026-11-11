"""As métricas em SQL têm de bater com o mesmo cálculo feito em pandas sobre os CSV crus."""
from datetime import date

import pytest

from delivery_insights import delivery_center as dc
from delivery_insights import metrics
from delivery_insights.metrics import Filtros


def test_kpis_batem_com_pandas(con, brutos):
    o = brutos["orders"]
    fin = o[o.order_status == "FINISHED"]
    valido = fin[(fin.order_amount > 0) & (fin.order_amount <= dc.VALOR_MAXIMO)]
    ciclo = fin.order_metric_cycle_time[fin.order_metric_cycle_time.between(0, 1440)]
    com_custo = fin[fin.order_delivery_cost.notna()]
    k = metrics.kpis(con, Filtros())
    assert k["pedidos"] == len(o)
    assert k["gmv"] == pytest.approx(valido.order_amount.sum())
    assert k["ticket_medio"] == pytest.approx(valido.order_amount.mean())
    assert k["lojas_ativas"] == o.store_id.nunique()
    assert k["taxa_cancelamento"] == pytest.approx((o.order_status == "CANCELED").mean())
    assert k["tempo_mediano_min"] == pytest.approx(ciclo.round(1).median(), abs=0.06)
    assert k["pct_ate_60"] == pytest.approx((ciclo.round(1) <= 60).mean())
    assert k["frete_coberto"] == pytest.approx(com_custo.order_delivery_fee.sum() / com_custo.order_delivery_cost.sum())


def test_filtros_de_cidade_segmento_e_data(con, brutos):
    j = brutos["orders"].merge(brutos["stores"], on="store_id").merge(brutos["hubs"], on="hub_id")
    esperado = j[(j.hub_city == "CURITIBA") & (j.store_segment == "FOOD")]
    f = Filtros(cidades=("Curitiba",), segmentos=("Comida",))
    assert metrics.kpis(con, f)["pedidos"] == len(esperado) > 0
    marco = Filtros(date(2021, 3, 1), date(2021, 3, 31))
    assert 0 < metrics.kpis(con, marco)["pedidos"] < metrics.kpis(con, Filtros())["pedidos"]


def test_soma_das_partes_igual_ao_todo(con):
    f = Filtros()
    total = metrics.kpis(con, f)
    for dim in ("cidade", "segmento", "tipo_canal", "canal", "hub"):
        d = metrics.por_dimensao(con, f, dim)
        assert d.pedidos.sum() == total["pedidos"]
        assert d.gmv.sum() == pytest.approx(total["gmv"])
        assert d.participacao.sum() == pytest.approx(1.0)
    assert metrics.mapa_hora_dia(con, f).pedidos.sum() == total["pedidos"]
    assert metrics.serie_kpis(con, f, "month").pedidos.sum() == total["pedidos"]
    assert metrics.pagamentos(con, f).participacao.sum() == pytest.approx(1.0)


def test_periodo_anterior():
    f = Filtros(date(2021, 4, 1), date(2021, 4, 30))
    ant = f.periodo_anterior()
    assert (ant.inicio, ant.fim) == (date(2021, 3, 2), date(2021, 3, 31))
    assert Filtros().periodo_anterior() is None  # período completo: não há dados antes


def test_recorte_sem_pedidos_nao_quebra(con):
    f = Filtros(date(2020, 12, 31), date(2020, 12, 31), cidades=("Curitiba",))
    assert metrics.kpis(con, f)["pedidos"] == 0 and metrics.kpis(con, f)["gmv"] == 0
    for fn in (metrics.serie_kpis, metrics.tempo_por_hora, metrics.etapas, metrics.distancia_vs_transito,
               metrics.pagamentos, metrics.top_lojas, metrics.mapa_hora_dia):
        fn(con, f)
    assert metrics.por_dimensao(con, f, "cidade").empty


def test_relacoes_embutidas_na_amostra(con):
    """A amostra de teste foi escrita com produtos mais lentos e mais cancelados que comida."""
    seg = metrics.por_dimensao(con, Filtros(), "segmento").set_index("segmento")
    assert seg.loc["Produtos", "tempo_mediano_min"] > seg.loc["Comida", "tempo_mediano_min"]
    assert seg.loc["Produtos", "taxa_cancelamento"] > seg.loc["Comida", "taxa_cancelamento"]
    et = metrics.etapas(con, Filtros())
    assert list(et.etapa) == ["Preparo na loja", "Espera até sair", "Trânsito até o cliente"]
    assert (et.minutos > 0).all()
    dist = metrics.distancia_vs_transito(con, Filtros())
    assert list(dist.ordem) == sorted(dist.ordem) and dist.pedidos.sum() > 0


def test_dimensao_desconhecida_e_recusada(con):
    with pytest.raises(AssertionError):
        metrics.por_dimensao(con, Filtros(), "pedido_id; DROP TABLE pedidos")
