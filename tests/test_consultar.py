"""O script que a Skill do Claude usa: lê, formata, e recusa qualquer escrita."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import consultar  # noqa: E402

from delivery_insights import db  # noqa: E402
from delivery_insights.metrics import Filtros  # noqa: E402


@pytest.fixture()
def amostra(monkeypatch, con):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db, "abrir", lambda: (con, db.Origem("csv", "amostra de teste")))


def test_esquema_traz_tabelas_e_definicoes(capsys):
    assert consultar.main(["esquema"]) == 0
    saida = capsys.readouterr().out
    assert "v_pedidos" in saida and "Vendas (GMV)" in saida and "fictícia" in saida


def test_kpis_em_formato_brasileiro(amostra, capsys):
    assert consultar.main(["kpis", "--cidade", "Curitiba", "--segmento", "Comida"]) == 0
    saida = capsys.readouterr().out
    assert "- Vendas (GMV): R$ " in saida and "e+" not in saida and "%" in saida


def test_sql_devolve_tabela_markdown(amostra, capsys):
    assert consultar.main(["sql", "SELECT segmento, count(*) AS n FROM v_pedidos GROUP BY 1 ORDER BY 1"]) == 0
    saida = capsys.readouterr().out
    assert saida.startswith("| segmento | n |") and "| Comida |" in saida


def test_escrita_e_recusada(amostra, capsys, brutos, con):
    assert consultar.main(["sql", "DELETE FROM pedidos"]) == 2
    assert "somente leitura" in capsys.readouterr().err
    assert con.execute("SELECT count(*) FROM pedidos").fetchone()[0] == len(brutos["orders"])


def test_erro_de_sql_explica_o_motivo(amostra, capsys):
    assert consultar.main(["sql", "SELECT coluna_que_nao_existe FROM v_pedidos"]) == 1
    assert "Erro na consulta" in capsys.readouterr().err


def test_skill_aponta_para_o_script_certo():
    skill = (Path(__file__).resolve().parents[1] / ".claude" / "skills" / "prova-real" / "SKILL.md").read_text("utf-8")
    assert skill.startswith("---\nname: prova-real\ndescription: ")
    assert "scripts/consultar.py" in skill and "somente leitura" in skill


def test_novos_filtros_do_recorte(con):
    from delivery_insights import metrics
    total = metrics.kpis(con, Filtros())["pedidos"]
    marketplace = metrics.kpis(con, Filtros(tipos_canal=("Marketplace",)))["pedidos"]
    assert 0 < marketplace < total
    faixas = metrics.por_dimensao(con, Filtros(), "faixa_valor")
    assert set(faixas.faixa_valor) <= set(metrics.FAIXAS_VALOR)
    f = Filtros(hubs=("BLUE SHOPPING",), modais=("Moto",), faixas_valor=("R$ 50 a 100",))
    assert set(f.ativos()) == {"BLUE SHOPPING", "Moto", "R$ 50 a 100"}
    assert f.periodo_anterior() is None or f.periodo_anterior().hubs == f.hubs
