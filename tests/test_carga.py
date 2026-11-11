"""A carga tem de traduzir, limpar e relacionar os CSV sem perder nem inventar pedidos."""
import pytest

from delivery_insights import delivery_center as dc


def um(con, sql):
    return con.cursor().execute(sql).fetchone()[0]


def test_nenhum_pedido_se_perde_nem_duplica(con, brutos):
    n = len(brutos["orders"])
    assert um(con, "SELECT count(*) FROM pedidos") == n
    # a view junta loja, hub, canal e entrega: continua com 1 linha por pedido,
    # mesmo havendo pedidos com duas entregas e pedidos sem entrega
    assert um(con, "SELECT count(*) FROM v_pedidos") == n
    assert um(con, "SELECT count(DISTINCT pedido_id) FROM v_pedidos") == n
    assert um(con, "SELECT max(tentativas_entrega) FROM v_pedidos") == 2
    assert um(con, "SELECT count(*) FROM v_pedidos WHERE tentativas_entrega IS NULL") == 10


def test_horario_convertido_para_brasilia(con):
    # a amostra só tem pedidos às 15h, 16h, 22h e 23h UTC
    horas = {h for (h,) in con.cursor().execute("SELECT DISTINCT hora FROM v_pedidos").fetchall()}
    assert horas == {12, 13, 19, 20}


def test_valores_absurdos_viram_nulo_mas_o_pedido_continua(con, brutos):
    assert um(con, "SELECT max(valor) FROM pedidos") <= dc.VALOR_MAXIMO
    assert um(con, "SELECT count(*) FROM pedidos WHERE valor IS NULL") == 2   # R$ 1,79 mi e R$ 0
    assert um(con, "SELECT min(tempo_transito_min) FROM pedidos") >= 0
    assert um(con, "SELECT max(tempo_total_min) FROM pedidos") <= 1440
    assert um(con, "SELECT max(distancia_km) FROM entregas") <= 50


def test_rotulos_traduzidos(con):
    def valores(sql):
        return {v for (v,) in con.cursor().execute(sql).fetchall()}

    assert valores("SELECT DISTINCT status FROM pedidos") == {"Finalizado", "Cancelado"}
    assert valores("SELECT DISTINCT segmento FROM lojas") == {"Comida", "Produtos"}
    assert valores("SELECT DISTINCT tipo FROM canais") == {"Marketplace", "Canal próprio"}
    assert valores("SELECT DISTINCT modal FROM entregadores") == {"Moto", "Bicicleta"}
    assert valores("SELECT DISTINCT cidade FROM hubs") == {"São Paulo", "Rio de Janeiro", "Porto Alegre", "Curitiba"}
    assert "Crédito" in valores("SELECT DISTINCT metodo FROM pagamentos")


def test_colunas_do_esquema_existem(con):
    """O texto entregue ao assistente não pode prometer colunas que não existem."""
    colunas = {c for (c,) in con.cursor().execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'v_pedidos'").fetchall()}
    for prometida in ("data_pedido", "mes", "hora", "dia_semana", "finalizado", "loja", "segmento", "hub",
                      "cidade", "uf", "canal", "tipo_canal", "distancia_km", "modal_entrega",
                      "tipo_entregador", "valor", "taxa_entrega", "custo_entrega", "tempo_total_min"):
        assert prometida in colunas and prometida in dc.ESQUEMA


def test_sem_arquivos_e_sem_download_falha_com_mensagem_clara(tmp_path):
    with pytest.raises(FileNotFoundError, match="kaggle.com"):
        dc.criar_conexao(tmp_path, baixar_se_faltar=False)
