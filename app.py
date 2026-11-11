"""Delivery Insights AI: dashboard + assistente de IA.  Rodar com:  streamlit run app.py"""

from __future__ import annotations

import os
from datetime import timedelta

import streamlit as st

try:  # carrega ANTHROPIC_API_KEY de um ficheiro .env, se existir
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from delivery_insights import agent, charts, db, demo, metrics
from delivery_insights.charts import brl, brl_curto, numero, pct
from delivery_insights.metrics import DATA_MAX, DATA_MIN, Filtros

st.set_page_config(page_title="Delivery Insights AI", page_icon="🍽️", layout="wide")

try:  # no Streamlit Cloud a chave vem dos "secrets"
    if "ANTHROPIC_API_KEY" in st.secrets and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

LIMITE_PERGUNTAS = int(os.getenv("LIMITE_PERGUNTAS_SESSAO", "20"))  # protege a chave numa demo pública
GRAFICO = dict(theme=None, config={"displayModeBar": False})

st.markdown("""<style>
.block-container {padding-top: 2.2rem; max-width: 1280px;}
[data-testid="stMetric"] {background:#fcfcfb; border:1px solid rgba(11,11,11,.10); border-radius:10px; padding:14px 16px;}
[data-testid="stMetricLabel"] p {color:#52514e; font-size:.82rem;}
[data-testid="stMetricValue"] {font-size:1.55rem;}
.aviso {background:#fff7e0; border:1px solid #f1d98a; border-radius:8px; padding:8px 12px; font-size:.84rem; color:#4d3d00;}
</style>""", unsafe_allow_html=True)


@st.cache_resource(show_spinner="A gerar os dados sintéticos…")
def conexao():
    return db.criar_conexao()


con = conexao()


@st.cache_data
def opcoes(coluna: str) -> list[str]:
    return db.consultar(con, f"SELECT DISTINCT {coluna} FROM v_pedidos ORDER BY 1")[coluna].tolist()


# link direto: ?pergunta=... abre o assistente já com a pergunta feita
pergunta_do_link = st.query_params.get("pergunta")

# ------------------------------- barra lateral -------------------------------
with st.sidebar:
    st.markdown("## 🍽️ Delivery Insights AI")
    pagina = st.radio("Página", ["📊 Painel", "🤖 Pergunte aos dados"], label_visibility="collapsed",
                      index=1 if pergunta_do_link else 0)
    st.markdown('<div class="aviso">⚠️ <b>Dados sintéticos.</b> Simulação reprodutível de um marketplace '
                'de delivery (2025). Nenhum dado é de uma empresa real.</div>', unsafe_allow_html=True)
    st.markdown("### Filtros do painel")
    periodo = st.selectbox("Período", ["Ano inteiro", "Últimos 90 dias", "Últimos 30 dias", "Personalizado"])
    if periodo == "Personalizado":
        datas = st.date_input("Intervalo", (DATA_MIN, DATA_MAX), min_value=DATA_MIN, max_value=DATA_MAX,
                              format="DD/MM/YYYY")
        inicio, fim = (datas[0], datas[-1]) if len(datas) == 2 else (DATA_MIN, DATA_MAX)
    else:
        dias = {"Últimos 90 dias": 90, "Últimos 30 dias": 30}.get(periodo)
        inicio, fim = (DATA_MAX - timedelta(days=dias - 1), DATA_MAX) if dias else (DATA_MIN, DATA_MAX)
    cidades = st.multiselect("Cidade", opcoes("cidade"), placeholder="Todas")
    culinarias = st.multiselect("Culinária", opcoes("culinaria"), placeholder="Todas")
    st.caption("“Últimos N dias” contam até 31/12/2025, o último dia dos dados.")

f = Filtros(inicio, fim, tuple(cidades), tuple(culinarias))


def variacao(atual: dict, anterior: dict | None, chave: str, pontos: bool = False) -> str | None:
    """Texto da variação face ao período anterior (em % ou em pontos percentuais)."""
    if not anterior or anterior.get(chave) in (None, 0) or atual.get(chave) is None:
        return None
    if anterior[chave] != anterior[chave] or atual[chave] != atual[chave]:  # NaN
        return None
    if pontos:
        return f"{(atual[chave] - anterior[chave]) * 100:+.1f} p.p.".replace(".", ",", 1)
    return f"{(atual[chave] / anterior[chave] - 1) * 100:+.1f}%".replace(".", ",")


# ---------------------------------- painel ----------------------------------
def painel():
    st.title("Painel do marketplace")
    k, ant = metrics.kpis_com_variacao(con, f)
    if not k["pedidos"]:
        st.info("Não há pedidos para os filtros escolhidos. Alargue o período ou remova filtros.")
        return
    rodape = "Variação face ao período anterior de mesma duração." if ant else \
        "Sem variação: não há período anterior equivalente dentro dos dados."
    st.caption(f"{f.inicio:%d/%m/%Y} a {f.fim:%d/%m/%Y} · {rodape}")

    c = st.columns(4)
    c[0].metric("GMV", brl_curto(k["gmv"]), variacao(k, ant, "gmv"),
                help="Soma do valor total dos pedidos entregues.")
    c[1].metric("Pedidos", numero(k["pedidos"]), variacao(k, ant, "pedidos"))
    c[2].metric("Ticket médio", brl(k["ticket_medio"], 2), variacao(k, ant, "ticket_medio"),
                help="GMV dividido pelos pedidos entregues.")
    c[3].metric("Clientes ativos", numero(k["clientes_ativos"]), variacao(k, ant, "clientes_ativos"),
                help="Clientes com pelo menos um pedido no período.")
    c = st.columns(4)
    c[0].metric("Entregas no prazo", pct(k["pct_no_prazo"]), variacao(k, ant, "pct_no_prazo", True),
                help="Pedidos entregues dentro do tempo prometido ao cliente.")
    c[1].metric("Cancelamento", pct(k["taxa_cancelamento"]), variacao(k, ant, "taxa_cancelamento", True),
                delta_color="inverse", help="Pedidos cancelados sobre pedidos feitos.")
    c[2].metric("Avaliação média", numero(k["avaliacao_media"], 2), variacao(k, ant, "avaliacao_media"),
                help="Nota de 1 a 5 dada pelos clientes que avaliaram.")
    c[3].metric("Take rate", pct(k["take_rate"]), variacao(k, ant, "take_rate", True),
                help="Receita da plataforma dividida pelo GMV.")

    geral, consumo, clientes, operacao = st.tabs(["Visão geral", "Consumo", "Clientes", "Operação"])

    with geral:
        dias = (f.fim - f.inicio).days
        grao = "day" if dias <= 45 else "week"
        s = metrics.serie_temporal(con, f, grao)
        if grao == "week" and len(s) > 2:
            s = s.iloc[1:-1] if dias >= 300 else s  # semanas incompletas nas pontas distorcem a linha
        st.plotly_chart(charts.serie(s, "periodo", "gmv", f"GMV por {'dia' if grao == 'day' else 'semana'}"),
                        **GRAFICO)
        a, b = st.columns(2)
        a.plotly_chart(charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria", "gmv",
                                       "GMV por culinária"), **GRAFICO)
        b.plotly_chart(charts.barras_h(metrics.por_dimensao(con, f, "cidade"), "cidade", "gmv",
                                       "GMV por cidade"), **GRAFICO)
        st.markdown("##### Restaurantes com maior GMV")
        top = metrics.top_restaurantes(con, f)
        top = top.assign(pedidos=top.pedidos.map(numero), gmv=top.gmv.map(brl),
                         avaliacao_media=top.avaliacao_media.map(lambda v: numero(v, 2)),
                         taxa_cancelamento=top.taxa_cancelamento.map(pct))
        top.columns = ["Restaurante", "Culinária", "Cidade", "Pedidos", "GMV", "Avaliação", "Cancelamento"]
        st.dataframe(top, hide_index=True, width="stretch")

    with consumo:
        st.plotly_chart(charts.calor_hora_dia(metrics.mapa_hora_dia(con, f),
                                              "Quando se pede: pedidos por dia da semana e hora"), **GRAFICO)
        a, b = st.columns([3, 2])
        a.plotly_chart(charts.calor_culinaria_faixa(
            metrics.culinaria_por_faixa(con, f),
            "Quem pede o quê: participação de cada culinária por faixa etária"), **GRAFICO)
        b.plotly_chart(charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria", "ticket_medio",
                                       "Ticket médio por culinária"), **GRAFICO)
        a, b = st.columns(2)
        pg = metrics.por_dimensao(con, f, "forma_pagamento")
        pg["participacao"] = pg["pedidos"] / pg["pedidos"].sum()
        a.plotly_chart(charts.barras_h(pg, "forma_pagamento", "participacao", "Formas de pagamento",
                                       formato="pct"), **GRAFICO)
        fx = metrics.por_dimensao(con, f, "faixa_etaria").sort_values("faixa_etaria")
        b.plotly_chart(charts.barras_v(fx, "faixa_etaria", "pedidos", "Pedidos por faixa etária"), **GRAFICO)

    with clientes:
        a, b = st.columns([3, 2])
        co = metrics.coortes(con, f)
        if co.empty:
            a.info("Sem clientes novos para estes filtros.")
        else:
            a.plotly_chart(charts.calor_coortes(co, "Retenção: clientes novos que voltam a pedir, mês a mês"),
                           **GRAFICO)
        a.caption("Cada linha é o grupo de clientes cadastrados em 2025 que fez o 1º pedido naquele mês. "
                  "Usa o ano inteiro, independentemente do filtro de período.")
        seg = metrics.segmentos(con, f)
        b.plotly_chart(charts.barras_h(seg.iloc[::-1], "segmento", "clientes", "Segmentos de clientes",
                                       formato="numero"), **GRAFICO)
        b.caption(f"Recência contada até {f.fim:%d/%m/%Y}; frequência dentro do período filtrado.")
        rc = metrics.recompra_30d(con, f)
        if not rc.empty:
            rc["mes"] = [charts._MESES[d.month - 1] for d in rc["coorte"]]
            st.plotly_chart(charts.barras_v(rc, "mes", "recompra_30d",
                                            "Recompra em 30 dias, por mês do 1º pedido", formato="pct",
                                            faixa_y=[0, min(1, rc["recompra_30d"].max() * 1.25)]), **GRAFICO)
        canal = metrics.por_dimensao(con, f, "canal_aquisicao")
        st.plotly_chart(charts.barras_h(canal, "canal_aquisicao", "gmv", "GMV por canal de aquisição do cliente"),
                        **GRAFICO)

    with operacao:
        a, b = st.columns(2)
        a.plotly_chart(charts.linha_sla(metrics.sla_por_hora(con, f), k["pct_no_prazo"],
                                        "Entregas no prazo por hora do dia"), **GRAFICO)
        b.plotly_chart(charts.barras_v(metrics.atraso_vs_avaliacao(con, f), "atraso", "avaliacao_media",
                                       "Avaliação média conforme o atraso", formato="nota", faixa_y=[0, 5.6]),
                       **GRAFICO)
        cid = metrics.por_dimensao(con, f, "cidade")
        a, b = st.columns(2)
        a.plotly_chart(charts.barras_h(cid, "cidade", "pct_no_prazo", "Entregas no prazo por cidade",
                                       formato="pct"), **GRAFICO)
        b.plotly_chart(charts.barras_h(cid, "cidade", "tempo_medio_min", "Tempo médio de entrega por cidade",
                                       formato="minutos"), **GRAFICO)
        st.plotly_chart(charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria",
                                        "taxa_cancelamento", "Taxa de cancelamento por culinária",
                                        formato="pct"), **GRAFICO)


# ------------------------------- assistente IA -------------------------------
def mostrar(resp: agent.Resposta):
    st.markdown(resp.texto.replace("R$", "R\\$"))
    for p in resp.passos:
        if p.figura is not None:
            st.plotly_chart(p.figura, **GRAFICO)
    consultas = [p for p in resp.passos if p.ferramenta == "executar_sql" or p.erro]
    if consultas:
        with st.expander(f"Como cheguei a esta resposta ({len(consultas)} consulta(s) SQL)"):
            for p in consultas:
                st.markdown(f"**{p.descricao or 'Consulta'}**")
                st.code(p.sql, language="sql")
                if p.erro:
                    st.warning(p.erro)
                elif p.resultado is not None:
                    st.dataframe(p.resultado, hide_index=True, width="stretch")
    if resp.modo == "llm":
        st.caption(f"{resp.modelo} · {resp.segundos:.1f}s · {numero(resp.tokens_entrada)} tokens de entrada, "
                   f"{numero(resp.tokens_saida)} de saída")
    else:
        st.caption("Modo demonstração: resposta montada por SQL pré-definido, sem modelo de linguagem.")


def perguntar(pergunta: str) -> agent.Resposta:
    if not agent.tem_credenciais():
        return demo.responder(pergunta, con)
    if st.session_state.n_perguntas >= LIMITE_PERGUNTAS:
        return agent.Resposta(modo="demo", texto=f"Limite de {LIMITE_PERGUNTAS} perguntas por sessão atingido "
                                                 "(proteção de custo desta demonstração).")
    import anthropic
    try:
        st.session_state.n_perguntas += 1
        resp = agent.responder(pergunta, con, historico=st.session_state.historico)
        st.session_state.historico = resp.mensagens
        return resp
    except anthropic.AuthenticationError:
        erro = "A chave de API é inválida. Verifique `ANTHROPIC_API_KEY`."
    except anthropic.RateLimitError:
        erro = "Limite de uso da API atingido. Tente de novo daqui a um minuto."
    except anthropic.APIConnectionError:
        erro = "Não consegui ligar à API. Verifique a ligação à internet."
    except anthropic.APIStatusError as e:
        erro = f"A API devolveu um erro ({e.status_code}): {e.message}"
    return agent.Resposta(modo="demo", texto=f"⚠️ {erro}")


def assistente():
    st.title("Pergunte aos dados")
    st.session_state.setdefault("conversa", [])
    st.session_state.setdefault("historico", [])
    st.session_state.setdefault("n_perguntas", 0)
    com_ia = agent.tem_credenciais()
    if com_ia:
        st.caption(f"Agente de IA ({agent.MODELO}) com acesso de leitura ao banco. Ele escreve o SQL, "
                   "executa, e mostra as consultas que usou. Responde sobre o ano inteiro, sem os filtros do painel.")
    else:
        st.markdown('<div class="aviso"><b>Modo demonstração (sem chave de API).</b> As perguntas abaixo são '
                    'respondidas com SQL pré-definido, sem modelo de linguagem. Para perguntas livres com o '
                    'agente de IA, defina <code>ANTHROPIC_API_KEY</code> e reinicie a aplicação.</div>',
                    unsafe_allow_html=True)
        st.write("")

    escolhida = None
    if not st.session_state.conversa:
        st.markdown("**Experimente:**")
        cols = st.columns(2)
        for i, ex in enumerate(demo.EXEMPLOS):
            if cols[i % 2].button(ex.pergunta, key=f"ex{i}", width="stretch"):
                escolhida = ex.pergunta

    for papel, conteudo in st.session_state.conversa:
        with st.chat_message(papel):
            if papel == "user":
                st.markdown(conteudo)
            else:
                mostrar(conteudo)

    digitada = st.chat_input("Ex.: Por que o prazo de entrega é pior em São Paulo?" if com_ia
                             else "Escolha ou escreva uma das perguntas de exemplo")
    pergunta = digitada or escolhida
    if pergunta_do_link and not st.session_state.conversa:
        pergunta = pergunta_do_link
    if pergunta:
        st.session_state.conversa.append(("user", pergunta))
        with st.chat_message("user"):
            st.markdown(pergunta)
        with st.chat_message("assistant"):
            with st.spinner("A consultar os dados…"):
                resp = perguntar(pergunta)
            mostrar(resp)
        st.session_state.conversa.append(("assistant", resp))
        st.rerun()  # redesenha a conversa já sem os botões de exemplo
    if st.session_state.conversa and st.sidebar.button("Limpar conversa"):
        st.session_state.conversa, st.session_state.historico = [], []
        st.rerun()


if pagina.endswith("Painel"):
    painel()
else:
    assistente()
