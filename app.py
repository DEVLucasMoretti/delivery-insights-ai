"""Prova Real: painel + assistente.  Rodar com:  streamlit run app.py

Estrutura: cabeçalho e navegação -> recorte (filtros) -> indicadores -> achado -> abas.
Cada aba é uma função curta que só escolhe métricas e gráficos; o visual vem de
delivery_insights/ui.py (HTML/CSS) e delivery_insights/charts.py (Plotly).
"""

from __future__ import annotations

import os
from datetime import timedelta
from itertools import count

import streamlit as st
from PIL import Image

try:  # carrega ANTHROPIC_API_KEY de um arquivo .env, se existir
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from delivery_insights import FONTE_DADOS, NOME, TAGLINE, agent, charts, db, demo, metrics, ui
from delivery_insights.charts import brl, brl_curto, numero, pct
from delivery_insights.metrics import DATA_MAX, DATA_MIN, Filtros

st.set_page_config(page_title=NOME, page_icon=Image.new("RGB", (64, 64), ui.PETROLEO),
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)

try:  # no Streamlit Cloud a chave vem dos "secrets"
    if "ANTHROPIC_API_KEY" in st.secrets and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

LIMITE_PERGUNTAS = int(os.getenv("LIMITE_PERGUNTAS_SESSAO", "20"))  # protege a chave numa demo pública
GRAFICO = dict(theme=None, config={"displayModeBar": False})
PERIODOS = {"30 dias": 30, "90 dias": 90, "Todo o período": None, "Escolher datas": None}
ABAS = ["Resumo", "Consumo", "Clientes", "Entrega"]
_n_cartao = count()  # chave única por cartão: é por ela que o CSS encontra o cartão


@st.cache_resource(show_spinner="Preparando os dados…")
def conexao():
    return db.criar_conexao()


con = conexao()


@st.cache_data
def opcoes(coluna: str) -> list[str]:
    return db.consultar(con, f"SELECT DISTINCT {coluna} FROM v_pedidos ORDER BY 1")[coluna].tolist()


def html(conteudo: str) -> None:
    st.html(conteudo)


def caixa(alvo=st):
    return alvo.container(border=True, key=f"cartao_{next(_n_cartao)}")


def cartao(titulo: str, fig=None, sub: str = "", nota: str = "", alvo=st):
    """Cartão de gráfico: título em forma de pergunta ou conclusão, gráfico e nota de rodapé."""
    with caixa(alvo):
        html(ui.cartao_titulo(titulo, sub))
        if fig is not None:
            st.plotly_chart(fig, key=f"grafico_{next(_n_cartao)}", **GRAFICO)
        if nota:
            html(ui.nota(nota))


# ------------------------------ cabeçalho e navegação ------------------------------
pergunta_do_link = st.query_params.get("pergunta")  # ?pergunta=... abre o assistente já com a pergunta
com_ia = agent.tem_credenciais()

c_marca, c_nav, c_pilulas = st.columns([5, 3, 4], vertical_alignment="center")
with c_marca:
    html(ui.cabecalho_marca(NOME, TAGLINE))
with c_nav:
    pagina = st.segmented_control("Navegação", ["Painel", "Perguntar"], label_visibility="collapsed",
                                  default="Perguntar" if pergunta_do_link else "Painel", key="pagina") or "Painel"
with c_pilulas:
    html(ui.pilulas([(FONTE_DADOS["pilula"], False)] + ([] if com_ia else [("Modo demonstração", True)])))
html('<hr class="pr-filete">')


# ----------------------------------- painel -----------------------------------
def limpar_recorte():
    st.session_state.update(f_periodo="Todo o período", f_cidades=[], f_culinarias=[])


def recorte() -> Filtros:
    c_periodo, c_filtros, c_ativos = st.columns([6, 2, 4], vertical_alignment="center")
    periodo = c_periodo.segmented_control("Período", list(PERIODOS), default="90 dias", key="f_periodo",
                                          label_visibility="collapsed") or "90 dias"
    with c_filtros.popover("Recorte", width="stretch"):
        cidades = st.multiselect("Cidade", opcoes("cidade"), placeholder="Todas", key="f_cidades")
        culinarias = st.multiselect("Culinária", opcoes("culinaria"), placeholder="Todas", key="f_culinarias")
        inicio, fim = DATA_MIN, DATA_MAX
        if periodo == "Escolher datas":
            datas = st.date_input("Datas", (DATA_MIN, DATA_MAX), min_value=DATA_MIN, max_value=DATA_MAX,
                                  format="DD/MM/YYYY")
            if len(datas) == 2:
                inicio, fim = datas
        st.caption(f"Os últimos dias contam até {DATA_MAX:%d/%m/%Y}, último dia dos dados.")
    dias = PERIODOS[periodo]
    if dias:
        inicio = DATA_MAX - timedelta(days=dias - 1)
    ativos = [(c, True) for c in cidades] + [(c, True) for c in culinarias]
    if ativos:
        with c_ativos:
            html(ui.pilulas(ativos))
    return Filtros(inicio, fim, tuple(cidades), tuple(culinarias))


def variacao(atual: dict, anterior: dict | None, chave: str, comparacao: str,
             pontos: bool = False, menor_e_melhor: bool = False) -> tuple | None:
    """(texto, estado, comparação) em relação ao período anterior, em % ou em pontos percentuais."""
    if not anterior:
        return None
    a, b = atual.get(chave), anterior.get(chave)
    if a is None or b is None or a != a or b != b or b == 0:
        return None
    delta = (a - b) * 100 if pontos else (a / b - 1) * 100
    texto = f"{delta:+.1f}".replace(".", ",") + (" p.p." if pontos else "%")
    if abs(delta) < 0.05:
        return texto, "neu", comparacao
    bom = (delta < 0) if menor_e_melhor else (delta > 0)
    return texto, "pos" if bom else "neg", comparacao


def bloco_indicadores(f: Filtros, k: dict, ant: dict | None):
    dias = (f.fim - f.inicio).days + 1
    comp = "vs. período anterior"
    s = metrics.serie_kpis(con, f, "day" if dias <= 45 else "week")
    if len(s) > 4 and dias > 45:
        s = s.iloc[1:-1]  # semanas incompletas nas pontas distorcem a forma da linha

    def ind(rotulo, valor, ajuda, chave=None, serie=None, **kw):
        # os cartões largos dizem com o que se compara; a faixa compacta mostra só a variação
        return dict(rotulo=rotulo, valor=valor, ajuda=ajuda, serie=[] if serie is None else list(serie),
                    var=variacao(k, ant, chave, comp if serie is not None else "", **kw) if ant else None)

    html(ui.indicadores(
        heroi=ind("Vendas (GMV)", brl_curto(k["gmv"]), "Valor total dos pedidos entregues.", "gmv", s["gmv"]),
        apoio=[
            ind("Pedidos", numero(k["pedidos"]), "Pedidos feitos no período, incluindo cancelados.",
                "pedidos", s["pedidos"]),
            ind("Ticket médio", brl(k["ticket_medio"], 2), "Vendas divididas pelos pedidos entregues.",
                "ticket_medio", s["ticket_medio"]),
            ind("Clientes ativos", numero(k["clientes_ativos"]), "Quem fez pelo menos um pedido no período.",
                "clientes_ativos", s["clientes_ativos"]),
        ],
        saude=[
            ind("No prazo", pct(k["pct_no_prazo"]), "Pedidos que chegaram dentro do tempo prometido.",
                "pct_no_prazo", pontos=True),
            ind("Cancelados", pct(k["taxa_cancelamento"]), "Pedidos cancelados sobre pedidos feitos.",
                "taxa_cancelamento", pontos=True, menor_e_melhor=True),
            ind("Nota média", numero(k["avaliacao_media"], 2), "De 1 a 5, entre os clientes que avaliaram.",
                "avaliacao_media"),
            ind("Comissão", pct(k["take_rate"]), "Take rate: receita da plataforma dividida pelas vendas.",
                "take_rate", pontos=True),
        ]))


def principal_achado(f: Filtros, k: dict) -> str | None:
    """Maior desvio em relação à média do período: o pior horário para o prazo de entrega."""
    sla = metrics.sla_por_hora(con, f)
    media = k["pct_no_prazo"]
    if sla.empty or media != media:
        return None
    pior = sla.loc[sla["pct_no_prazo"].idxmin()]
    queda = (media - pior["pct_no_prazo"]) * 100
    if queda < 1:
        return None
    return (f"Às <b>{int(pior['hora'])}h</b>, só <b>{pct(pior['pct_no_prazo'], 0)}</b> dos pedidos chegam no prazo: "
            f"<b>{numero(queda, 0)} p.p.</b> abaixo da média do período ({pct(media, 0)}).")


def aba_resumo(f: Filtros, k: dict):
    dias = (f.fim - f.inicio).days
    grao = "day" if dias <= 45 else "week"
    s = metrics.serie_temporal(con, f, grao)
    if grao == "week" and len(s) > 4:
        s = s.iloc[1:-1]
    cartao(f"Como as vendas andaram, {'dia a dia' if grao == 'day' else 'semana a semana'}?",
           charts.serie(s, "periodo", "gmv"), sub="Vendas (GMV) em reais, pedidos entregues")
    a, b = st.columns(2)
    cartao("Que culinárias vendem mais?", alvo=a, sub="Vendas (GMV) no período",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria", "gmv"))
    cartao("Onde está a venda?", alvo=b, sub="Vendas (GMV) por cidade",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "cidade"), "cidade", "gmv"))
    with caixa():
        html(ui.cartao_titulo("Os restaurantes que mais vendem", "Os 10 primeiros em vendas no período"))
        top = metrics.top_restaurantes(con, f)
        top = top.assign(pedidos=top.pedidos.map(numero), gmv=top.gmv.map(brl),
                         avaliacao_media=top.avaliacao_media.map(lambda v: numero(v, 2)),
                         taxa_cancelamento=top.taxa_cancelamento.map(pct))
        top.columns = ["Restaurante", "Culinária", "Cidade", "Pedidos", "Vendas", "Nota", "Cancelados"]
        st.dataframe(top, hide_index=True, width="stretch")
    html(ui.link_pergunta("Qual foi o GMV por cidade?"))


def aba_consumo(f: Filtros, k: dict):
    mapa = metrics.mapa_hora_dia(con, f)
    pico = mapa.loc[mapa["pedidos"].idxmax()]
    cartao("Quando o pedido acontece?", charts.calor_hora_dia(mapa),
           sub=f"Pedidos por dia da semana e hora · pico: {pico['dia_semana']} às {int(pico['hora'])}h")
    a, b = st.columns([3, 2])
    cartao("Quem pede o quê, por idade?", alvo=a, sub="Participação de cada culinária nos pedidos da faixa etária",
           fig=charts.calor_culinaria_faixa(metrics.culinaria_por_faixa(con, f)))
    cartao("Onde o ticket é mais alto?", alvo=b, sub="Ticket médio por culinária",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria", "ticket_medio",
                               formato="moeda"))
    a, b = st.columns(2)
    pg = metrics.por_dimensao(con, f, "forma_pagamento")
    pg["participacao"] = pg["pedidos"] / pg["pedidos"].sum()
    cartao("Como se paga?", alvo=a, sub="Participação de cada forma de pagamento nos pedidos",
           fig=charts.barras_h(pg, "forma_pagamento", "participacao", formato="pct"))
    fx = metrics.por_dimensao(con, f, "faixa_etaria").sort_values("faixa_etaria")
    cartao("Que idade pede mais?", alvo=b, sub="Pedidos por faixa etária",
           fig=charts.barras_v(fx, "faixa_etaria", "pedidos"))
    html(ui.link_pergunta("Que culinária cada faixa etária prefere?"))


def aba_clientes(f: Filtros, k: dict):
    a, b = st.columns([3, 2])
    co = metrics.coortes(con, f)
    cartao("Quem chega, volta?", alvo=a, fig=None if co.empty else charts.calor_coortes(co),
           sub="Clientes novos que voltam a pedir, mês a mês",
           nota="Cada linha é a turma que fez o primeiro pedido naquele mês. "
                "Usa o período completo dos dados, sem o filtro de datas.")
    seg = metrics.segmentos(con, f)
    cartao("Como a base se divide?", alvo=b, sub="Clientes por recência e frequência",
           fig=charts.barras_h(seg, "segmento", "clientes", formato="numero"),
           nota=f"Recência contada até {f.fim:%d/%m/%Y}; frequência dentro do recorte.")
    rc = metrics.recompra_30d(con, f)
    if not rc.empty:
        media = (rc["recompra_30d"] * rc["clientes_novos"]).sum() / rc["clientes_novos"].sum()
        rc["mes"] = [charts._MESES[d.month - 1] for d in rc["coorte"]]
        cartao(f"{pct(media, 0)} fazem o segundo pedido em até 30 dias",
               charts.barras_v(rc, "mes", "recompra_30d", formato="pct", destaque=None,
                               faixa_y=[0, min(1.1, rc["recompra_30d"].max() * 1.2)]),
               sub="Recompra em 30 dias, por mês do primeiro pedido")
    cartao("De que canal vêm os clientes que mais compram?", sub="Vendas (GMV) por canal de aquisição",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "canal_aquisicao"), "canal_aquisicao", "gmv"))
    html(ui.link_pergunta("Assinantes do clube pedem mais?"))


def aba_entrega(f: Filtros, k: dict):
    sla = metrics.sla_por_hora(con, f)
    a, b = st.columns(2)
    titulo_sla = "A que horas o prazo estoura?"
    if not sla.empty:
        pior = sla.loc[sla["pct_no_prazo"].idxmin()]
        titulo_sla = f"O prazo cai para {pct(pior['pct_no_prazo'], 0)} às {int(pior['hora'])}h"
    cartao(titulo_sla, charts.linha_sla(sla, k["pct_no_prazo"]), alvo=a,
           sub="Pedidos entregues no prazo, por hora do dia")
    atraso = metrics.atraso_vs_avaliacao(con, f)
    desce = len(atraso) > 1 and atraso["avaliacao_media"].is_monotonic_decreasing
    cartao("Cada faixa de atraso derruba a nota" if desce else "Como o atraso afeta a nota?", alvo=b,
           fig=charts.barras_v(atraso, "atraso", "avaliacao_media", formato="nota", faixa_y=[0, 5.8],
                               destaque="min"),
           sub="Nota média (1 a 5) conforme o atraso")
    cid = metrics.por_dimensao(con, f, "cidade")
    a, b = st.columns(2)
    cartao("Onde a entrega cumpre o prometido?", alvo=a, sub="Pedidos no prazo, por cidade",
           fig=charts.barras_h(cid, "cidade", "pct_no_prazo", formato="pct", destaque="min"))
    cartao("Quanto demora a entrega em cada cidade?", alvo=b, sub="Tempo médio de entrega",
           fig=charts.barras_h(cid, "cidade", "tempo_medio_min", formato="minutos"))
    cartao("Onde se cancela mais?", sub="Taxa de cancelamento por culinária",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "culinaria"), "culinaria", "taxa_cancelamento",
                               formato="pct"))
    html(ui.link_pergunta("Em que horários o prazo de entrega falha mais?"))


def painel():
    f = recorte()
    k, ant = metrics.kpis_com_variacao(con, f)
    sub = f"{f.inicio:%d/%m/%Y} a {f.fim:%d/%m/%Y} · " + (
        "comparado ao período anterior de mesma duração" if ant else "sem período anterior nos dados para comparar")
    html(ui.titulo("Como vai a operação", sub))
    if not k["pedidos"]:
        html(ui.vazio("Nenhum pedido neste recorte", "Amplie o período ou tire um filtro."))
        _, meio, _ = st.columns([2, 1, 2])
        meio.button("Limpar recorte", on_click=limpar_recorte, width="stretch")
        return
    bloco_indicadores(f, k, ant)
    frase = principal_achado(f, k)
    if frase:
        html(ui.achado(frase))
    aba_do_link = st.query_params.get("aba", "").lower()  # ?aba=entrega abre direto nessa aba
    inicial = next((a for a in ABAS if a.lower().startswith(aba_do_link)), None) if aba_do_link else None
    for aba, desenhar in zip(st.tabs(ABAS, default=inicial),
                             (aba_resumo, aba_consumo, aba_clientes, aba_entrega)):
        with aba:
            desenhar(f, k)


# -------------------------------- assistente --------------------------------
def mostrar(resp: agent.Resposta):
    with caixa():
        st.markdown(resp.texto.replace("R$", "R\\$"))
        for p in resp.passos:
            if p.figura is not None:
                html(ui.cartao_titulo(p.descricao))
                st.plotly_chart(p.figura, key=f"grafico_{next(_n_cartao)}", **GRAFICO)
        consultas = [p for p in resp.passos if p.ferramenta == "executar_sql" or p.erro]
        if consultas:
            with st.expander(f"Conferir a conta · {len(consultas)} consulta(s)"):
                for p in consultas:
                    st.markdown(f"**{p.descricao or 'Consulta'}**")
                    st.code(p.sql, language="sql")
                    if p.erro:
                        st.warning(p.erro)
                    elif p.resultado is not None:
                        st.dataframe(p.resultado, hide_index=True, width="stretch")
        if resp.modo == "llm":
            html(f'<p class="pr-meta">{resp.modelo} · {resp.segundos:.1f}s · '
                 f'{numero(resp.tokens_entrada + resp.tokens_saida)} tokens</p>')
        elif resp.passos:
            html('<p class="pr-meta">Modo demonstração · SQL escrito à mão, sem modelo de linguagem</p>')


def perguntar(pergunta: str) -> agent.Resposta:
    if not com_ia:
        return demo.responder(pergunta, con)
    if st.session_state.n_perguntas >= LIMITE_PERGUNTAS:
        return agent.Resposta(modo="aviso", texto=f"Esta sessão chegou ao limite de {LIMITE_PERGUNTAS} perguntas, "
                                                  "que protege o custo da demonstração.")
    import anthropic
    try:
        st.session_state.n_perguntas += 1
        resp = agent.responder(pergunta, con, historico=st.session_state.historico)
        st.session_state.historico = resp.mensagens
        return resp
    except anthropic.AuthenticationError:
        motivo = "A chave de API não foi aceita. Confira ANTHROPIC_API_KEY"
    except anthropic.RateLimitError:
        motivo = "O limite de uso da API foi atingido; espere um minuto"
    except anthropic.APIConnectionError:
        motivo = "Não houve conexão com a API"
    except anthropic.APIStatusError as e:
        motivo = f"A API devolveu o erro {e.status_code}"
    return agent.Resposta(modo="aviso", texto=f"Não consegui responder agora. {motivo}. "
                                              "Nenhum número foi inventado: tente de novo ou reformule.")


def nova_conversa():
    st.session_state.update(conversa=[], historico=[])


def assistente():
    st.session_state.setdefault("conversa", [])
    st.session_state.setdefault("historico", [])
    st.session_state.setdefault("n_perguntas", 0)
    intro = ("Escreva a pergunta como falaria com um analista. A resposta vem com o SQL executado e a tabela "
             "que voltou. Considera todo o período, sem o recorte do painel.") if com_ia else (
        f"Modo demonstração. Sem chave de API, as respostas vêm de um catálogo de {len(demo.EXEMPLOS)} perguntas "
        "com SQL escrito à mão; nenhum modelo de linguagem participa. Para perguntas livres, defina "
        "ANTHROPIC_API_KEY e reinicie.")
    c_titulo, c_botao = st.columns([5, 1], vertical_alignment="bottom")
    with c_titulo:
        html(ui.titulo("Pergunte. Confira a conta.", intro=intro))
    if st.session_state.conversa:
        c_botao.button("Nova conversa", on_click=nova_conversa, width="stretch")

    escolhida = None
    if not st.session_state.conversa and not pergunta_do_link:
        html('<p class="pr-rotulo" style="margin:26px 0 8px">Comece por uma destas</p>')
        with st.container(key="sugestoes"):
            cols = st.columns(2)
            for i, ex in enumerate(demo.EXEMPLOS):
                if cols[i % 2].button(ex.pergunta, key=f"ex{i}", width="stretch"):
                    escolhida = ex.pergunta

    for papel, conteudo in st.session_state.conversa:
        if papel == "user":
            html(ui.pergunta(conteudo))
        else:
            mostrar(conteudo)

    digitada = st.chat_input("Ex.: por que o prazo é pior em algumas cidades?" if com_ia
                             else "Escolha ou digite uma pergunta do catálogo")
    pergunta = digitada or escolhida
    if pergunta_do_link and not st.session_state.conversa:
        pergunta = pergunta_do_link
    if pergunta:
        st.session_state.conversa.append(("user", pergunta))
        html(ui.pergunta(pergunta))
        with st.spinner("Consultando os dados…"):
            resp = perguntar(pergunta)
        st.session_state.conversa.append(("assistant", resp))
        if pergunta == pergunta_do_link:
            mostrar(resp)  # veio de um link: não há sugestões para esconder
        else:
            st.rerun()  # redesenha a conversa já sem as sugestões


if pagina == "Painel":
    painel()
else:
    assistente()
html(ui.rodape(FONTE_DADOS["frase"]))
