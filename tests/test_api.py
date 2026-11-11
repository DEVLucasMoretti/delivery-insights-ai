"""A API responde sem chave (modo demonstração) e valida a entrada."""
import pytest
from fastapi.testclient import TestClient

import api


@pytest.fixture()
def cliente(con, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(api, "conexao", lambda: con)
    return TestClient(api.app)


def test_saude(cliente):
    r = cliente.get("/saude").json()
    assert r["ok"] and r["pedidos"] == 4000 and r["agente_de_ia"] is False and "Delivery Center" in r["dados"]


def test_kpis_com_filtros(cliente):
    tudo = cliente.get("/kpis").json()
    sp = cliente.get("/kpis", params={"cidade": "São Paulo", "segmento": "Comida", "inicio": "2021-02-01", "fim": "2021-02-28"}).json()
    assert 0 < sp["gmv"] < tudo["gmv"]
    assert cliente.get("/kpis", params={"inicio": "2021-02-28", "fim": "2021-02-01"}).status_code == 422


def test_perguntar_em_modo_demonstracao(cliente):
    r = cliente.post("/perguntar", json={"pergunta": "Qual foi o GMV por cidade?"})
    corpo = r.json()
    assert r.status_code == 200 and corpo["modo"] == "demo"
    assert "São Paulo" in corpo["resposta"] and len(corpo["consultas"][0]["linhas"]) == 4
    assert cliente.post("/perguntar", json={"pergunta": ""}).status_code == 422
