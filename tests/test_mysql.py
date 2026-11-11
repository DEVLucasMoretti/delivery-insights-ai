"""Leitura a partir de um banco operacional (MySQL).

Os dois primeiros testes rodam sempre: conferem que montar a camada analítica a partir de
tabelas lidas de outro sistema dá exatamente os mesmos números que a partir dos CSV.

O teste de integração só roda com um MySQL de verdade, quando estas variáveis existem:
    TESTE_MYSQL_CARGA_URL    usuário que escreve (carrega a amostra)
    TESTE_MYSQL_LEITURA_URL  usuário que só lê (o que a aplicação usa)
No GitHub Actions elas apontam para um MySQL de serviço (ver .github/workflows/ci.yml).
"""
import os

import pytest

from delivery_insights import db, delivery_center as dc, metrics, mysql_fonte
from delivery_insights.metrics import Filtros


def test_mesmos_numeros_vindo_de_tabelas_ou_de_csv(con, pasta):
    de_tabelas = dc.criar_conexao_de_tabelas(dc.ler_csv_brutos(pasta))
    for f in (Filtros(), Filtros(cidades=("Curitiba",), segmentos=("Comida",))):
        a, b = metrics.kpis(con, f), metrics.kpis(de_tabelas, f)
        assert a.keys() == b.keys()
        for chave in a:
            assert a[chave] == pytest.approx(b[chave], nan_ok=True), chave


def test_tabela_faltando_e_banco_trancado(pasta):
    brutas = dc.ler_csv_brutos(pasta)
    with pytest.raises(ValueError, match="payments"):
        dc.criar_conexao_de_tabelas({k: v for k, v in brutas.items() if k != "payments"})
    con = dc.criar_conexao_de_tabelas(brutas)
    with pytest.raises(Exception):
        con.execute("SET enable_external_access = true")
    with pytest.raises(Exception):  # os DataFrames de origem não ficam acessíveis ao assistente
        con.execute("SELECT * FROM bruto_orders").fetchall()


def test_leitura_de_privilegios():
    assert mysql_fonte._privilegios([
        "GRANT USAGE ON *.* TO `prova_leitura`@`%`",
        "GRANT SELECT, SHOW VIEW ON `delivery_center`.* TO `prova_leitura`@`%`",
    ]) == {"USAGE", "SELECT", "SHOW VIEW"}
    assert "INSERT" in mysql_fonte._privilegios(["GRANT SELECT, INSERT ON `x`.* TO `y`@`%`"])


CARGA = os.getenv("TESTE_MYSQL_CARGA_URL")
LEITURA = os.getenv("TESTE_MYSQL_LEITURA_URL")


@pytest.mark.skipif(not (CARGA and LEITURA), reason="sem MySQL de teste configurado")
def test_integracao_com_mysql(pasta, con, monkeypatch):
    import sys
    from pathlib import Path

    from sqlalchemy import create_engine, text
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import carregar_mysql

    contagem = carregar_mysql.carregar(CARGA, pasta)
    assert contagem["orders"] == 4000

    v = mysql_fonte.varrer(LEITURA)
    assert v.faltam == [] and v.pedidos == 4000
    assert v.somente_leitura and "SELECT" in v.privilegios
    assert "senha" not in v.endereco and "@" not in v.endereco

    # o usuário de leitura não consegue apagar nada no MySQL
    with create_engine(LEITURA).connect() as c, pytest.raises(Exception):
        c.execute(text("DELETE FROM orders"))

    monkeypatch.setenv("DATABASE_URL", LEITURA)
    con_mysql, origem = db.abrir()
    assert origem.tipo == "mysql" and origem.varredura.banco in origem.descricao
    assert metrics.kpis(con_mysql, Filtros())["gmv"] == pytest.approx(metrics.kpis(con, Filtros())["gmv"])
