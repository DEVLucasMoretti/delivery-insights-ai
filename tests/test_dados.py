"""Os dados sintéticos têm de ser reprodutíveis e coerentes."""
import pandas as pd

from delivery_insights.generate_data import FIM, INICIO, gerar


def test_mesma_seed_gera_os_mesmos_dados(tabelas):
    de_novo = gerar(seed=42)
    for nome in tabelas:
        pd.testing.assert_frame_equal(tabelas[nome], de_novo[nome])


def test_seed_diferente_gera_dados_diferentes(tabelas):
    assert len(gerar(seed=7)["pedidos"]) != len(tabelas["pedidos"])


def test_chaves_e_periodo(tabelas):
    p = tabelas["pedidos"]
    assert p.pedido_id.is_unique
    assert tabelas["restaurantes"].nome.is_unique
    assert p.cliente_id.isin(tabelas["clientes"].cliente_id).all()
    assert p.restaurante_id.isin(tabelas["restaurantes"].restaurante_id).all()
    assert p.data_hora.min() >= INICIO and p.data_hora.max() < FIM + pd.Timedelta(days=1)


def test_valores_coerentes(tabelas):
    p = tabelas["pedidos"]
    assert ((p.valor_itens + p.taxa_entrega - p.desconto - p.valor_total).abs() < 0.011).all()
    assert (p.valor_total > 0).all()
    cancelados = p[p.status == "Cancelado"]
    assert cancelados.tempo_entrega_min.isna().all() and cancelados.avaliacao.isna().all()
    assert (cancelados.receita_plataforma == 0).all()
    assert p.avaliacao.dropna().between(1, 5).all()


def test_cliente_pede_na_propria_cidade(tabelas):
    j = (tabelas["pedidos"].merge(tabelas["clientes"], on="cliente_id")
         .merge(tabelas["restaurantes"], on="restaurante_id", suffixes=("_cli", "_rest")))
    assert (j.cidade_cli == j.cidade_rest).all()
