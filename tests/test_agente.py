"""Testa o ciclo do agente com um modelo falso (sem rede e sem custo)."""
from types import SimpleNamespace as NS

from delivery_insights import agent, demo


def _msg(stop, *blocos):
    return NS(content=list(blocos), stop_reason=stop, model="modelo-falso",
              usage=NS(input_tokens=10, output_tokens=5, cache_read_input_tokens=0,
                       cache_creation_input_tokens=0))


def _tool(i, nome, **entrada):
    return NS(type="tool_use", id=f"t{i}", name=nome, input=entrada)


class ClienteFalso:
    """Devolve respostas pré-gravadas e guarda o que recebeu, como se fosse a API."""

    def __init__(self, *respostas):
        self.respostas, self.chamadas = list(respostas), []
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kw):
        self.chamadas.append({**kw, "messages": list(kw["messages"])})
        return self.respostas.pop(0)


def test_agente_consulta_e_responde(con):
    cliente = ClienteFalso(
        _msg("tool_use", _tool(1, "executar_sql", descricao="Total de pedidos",
                               sql="SELECT count(*) AS n FROM pedidos")),
        _msg("end_turn", NS(type="text", text="Foram feitos N pedidos.")),
    )
    r = agent.responder("Quantos pedidos?", con, cliente=cliente)
    assert r.texto == "Foram feitos N pedidos."
    assert len(r.passos) == 1 and r.passos[0].erro is None
    assert r.passos[0].resultado.n[0] == con.execute("SELECT count(*) FROM pedidos").fetchone()[0]
    # o resultado da consulta voltou para o modelo, ligado à chamada certa
    volta = cliente.chamadas[1]["messages"][-1]["content"][0]
    assert volta["tool_use_id"] == "t1" and volta["is_error"] is False
    assert r.tokens_entrada == 20 and r.tokens_saida == 10


def test_erro_de_sql_volta_para_o_modelo_corrigir(con):
    cliente = ClienteFalso(
        _msg("tool_use", _tool(1, "executar_sql", descricao="x", sql="SELECT coluna_que_nao_existe FROM pedidos")),
        _msg("tool_use", _tool(2, "executar_sql", descricao="x", sql="SELECT 1 AS ok")),
        _msg("end_turn", NS(type="text", text="Pronto.")),
    )
    r = agent.responder("teste", con, cliente=cliente)
    assert r.passos[0].erro and r.passos[1].erro is None
    assert cliente.chamadas[1]["messages"][-1]["content"][0]["is_error"] is True


def test_tentativa_de_escrita_e_bloqueada(con, brutos):
    cliente = ClienteFalso(
        _msg("tool_use", _tool(1, "executar_sql", descricao="apagar", sql="DELETE FROM pedidos")),
        _msg("end_turn", NS(type="text", text="Não posso alterar dados.")),
    )
    r = agent.responder("apaga tudo", con, cliente=cliente)
    assert "bloqueada" in r.passos[0].erro
    assert con.execute("SELECT count(*) FROM pedidos").fetchone()[0] == len(brutos["orders"])


def test_grafico_e_historico_entre_perguntas(con):
    cliente = ClienteFalso(
        _msg("tool_use", _tool(1, "criar_grafico", titulo="GMV por cidade", tipo="barra", x="cidade", y="gmv",
                               sql="SELECT cidade, sum(valor) AS gmv FROM v_pedidos GROUP BY 1")),
        _msg("end_turn", NS(type="text", text="Veja o gráfico.")),
        _msg("end_turn", NS(type="text", text="Segunda resposta.")),
    )
    r1 = agent.responder("GMV por cidade?", con, cliente=cliente)
    assert r1.passos[0].figura is not None
    agent.responder("E depois?", con, historico=r1.mensagens, cliente=cliente)
    papeis = [m["role"] for m in cliente.chamadas[2]["messages"]]
    assert papeis == ["user", "assistant", "user", "assistant", "user"]


def test_para_quando_o_modelo_nao_conclui(con):
    voltas = [_msg("tool_use", _tool(i, "executar_sql", descricao="x", sql="SELECT 1")) for i in range(3)]
    r = agent.responder("teste", con, cliente=ClienteFalso(*voltas), max_voltas=3)
    assert "Parei" in r.texto and r.mensagens[-1]["role"] == "assistant"


def test_ferramentas_tem_esquema_estrito():
    for f in agent.FERRAMENTAS:
        s = f["input_schema"]
        assert f["strict"] and s["additionalProperties"] is False
        assert set(s["required"]) == set(s["properties"])


def test_modo_demonstracao(con):
    for ex in demo.EXEMPLOS:
        r = demo.responder(ex.pergunta, con)
        assert r.modo == "demo" and r.passos and len(r.texto) > 30
    assert demo.encontrar("qual o gmv de cada cidade") is demo.EXEMPLOS[0]
    assert "catálogo" in demo.responder("qual o salário dos entregadores?", con).texto


def test_prompt_descreve_a_origem_dos_dados_sem_exagerar():
    p = agent.PROMPT_SISTEMA
    assert "Delivery Center" in p and "fictícia" in p and "anonimizado" in p
    assert "sintétic" not in p.lower() and "v_pedidos" in p
