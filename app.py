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

try:  # carrega ANTHROPIC_API_KEY e DATABASE_URL do arquivo .env do projeto, se existir
    from pathlib import Path

    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"))
except ImportError:
    pass

from delivery_insights import FONTE_DADOS, NOME, TAGLINE, agent, charts, db, demo, metrics, ui
from delivery_insights.charts import brl, brl_curto, numero, pct
from delivery_insights.metrics import DATA_MAX, DATA_MIN, Filtros

st.set_page_config(page_title=NOME, page_icon=Image.new("RGB", (64, 64), ui.DESTAQUE),
                   layout="wide", initial_sidebar_state="collapsed")
st.markdown(ui.CSS, unsafe_allow_html=True)

try:  # no Streamlit Cloud a chave vem dos "secrets"
    if "ANTHROPIC_API_KEY" in st.secrets and not os.getenv("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass

LIMITE_PERGUNTAS = int(os.getenv("LIMITE_PERGUNTAS_SESSAO", "20"))  # protege a chave numa demo pública
GRAFICO = dict(theme=None, config={"displayModeBar": False})
PERIODOS = {"30 dias": 30, "60 dias": 60, "Todo o período": None, "Escolher datas": None}
ABAS = ["Resumo", "Demanda", "Canais", "Entrega"]
NOTA_NOMES = "Os nomes de lojas, hubs e canais foram embaralhados na origem dos dados."
_n_cartao = count()  # chave única por cartão: é por ela que o CSS encontra o cartão


@st.cache_resource(show_spinner="Conectando ao banco e preparando os dados…")
def conexao():
    return db.abrir()


try:
    con, origem = conexao()
except Exception as erro:  # banco fora do ar, senha errada, tabelas faltando...
    st.html(ui.vazio("Não consegui ler o banco de dados",
                     f"{type(erro).__name__}: {erro}. Confira DATABASE_URL e se o MySQL está ligado."))
    st.stop()


@st.cache_data
def opcoes(coluna: str) -> list[str]:
    return db.consultar(con, f"SELECT DISTINCT {coluna} FROM v_pedidos ORDER BY 1")[coluna].tolist()


def html(conteudo: str) -> None:
    st.html(conteudo)


def caixa(alvo=st):
    return alvo.container(border=True, key=f"cartao_{next(_n_cartao)}")


# campo do recorte: (rótulo, coluna da view, texto quando vazio)
RECORTE = {
    "cidades": ("Cidade", "cidade", "Todas"),
    "segmentos": ("Segmento", "segmento", "Todos"),
    "tipos_canal": ("Tipo de canal", "tipo_canal", "Todos"),
    "canais": ("Canal de venda", "canal", "Todos"),
    "hubs": ("Hub (centro de distribuição)", "hub", "Todos"),
    "modais": ("Modal de entrega", "modal_entrega", "Todos"),
    "faixas_valor": ("Valor do pedido", "faixa_valor", "Todas"),
}
CAMPO_DA_COLUNA = {coluna: campo for campo, (_, coluna, _) in RECORTE.items()}


def _filtrar_por_chip(campo: str, chave: str):
    """Clique num chip: soma o valor ao filtro do painel. Roda antes do script, por isso pode mexer no filtro."""
    valor = st.session_state.get(chave)
    if valor:
        atuais = list(st.session_state.get(f"f_{campo}", []))
        if valor not in atuais:
            st.session_state[f"f_{campo}"] = atuais + [valor]
    st.session_state[chave] = None


def cartao(titulo: str, fig=None, sub: str = "", nota: str = "", alvo=st, filtra: str | None = None):
    """Cartão de gráfico: título em forma de pergunta ou conclusão, gráfico e nota de rodapé.

    Com `filtra` (uma coluna da view), o cartão ganha chips: clicar num deles filtra o painel inteiro.
    """
    with caixa(alvo):
        html(ui.cartao_titulo(titulo, sub))
        if fig is not None:
            chave = f"grafico_{next(_n_cartao)}"
            st.plotly_chart(fig, key=chave, **GRAFICO)
            if filtra:
                campo = CAMPO_DA_COLUNA[filtra]
                eixo = fig.data[0].y if fig.data[0].orientation == "h" else fig.data[0].x
                ja = set(st.session_state.get(f"f_{campo}", []))
                opcoes_chip = [str(v) for v in reversed(list(eixo)) if str(v) not in ja]
                if fig.data[0].orientation != "h":
                    opcoes_chip.reverse()
                if opcoes_chip:
                    chip = f"chip_{chave}"
                    st.pills("Filtrar o painel por", opcoes_chip, key=chip, selection_mode="single",
                             on_change=_filtrar_por_chip, args=(campo, chip))
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
    html(ui.pilulas([(origem.descricao if origem.tipo == "mysql" else FONTE_DADOS["pilula"], False)]
                    + ([] if com_ia else [("Modo demonstração", True)])))
html('<hr class="pr-filete">')


# ----------------------------------- painel -----------------------------------
def limpar_recorte(periodo: bool = True):
    for campo in RECORTE:
        st.session_state[f"f_{campo}"] = []
    if periodo:
        st.session_state["f_periodo"] = "Todo o período"


def recorte() -> Filtros:
    c_periodo, c_filtros, c_ativos = st.columns([6, 2, 4], vertical_alignment="center")
    periodo = c_periodo.segmented_control("Período", list(PERIODOS), default="30 dias", key="f_periodo",
                                          label_visibility="collapsed") or "30 dias"
    escolhas = {}
    n_ativos = sum(len(st.session_state.get(f"f_{c}", [])) for c in RECORTE)
    with c_filtros.popover(f"Filtros · {n_ativos}" if n_ativos else "Filtros", width="stretch"):
        a, b = st.columns(2)
        for i, (campo, (rotulo, coluna, vazio)) in enumerate(RECORTE.items()):
            alvo = a if i % 2 == 0 else b
            escolhas[campo] = tuple(alvo.multiselect(rotulo, opcoes(coluna), placeholder=vazio, key=f"f_{campo}"))
        inicio, fim = DATA_MIN, DATA_MAX
        if periodo == "Escolher datas":
            datas = st.date_input("Datas", (DATA_MIN, DATA_MAX), min_value=DATA_MIN, max_value=DATA_MAX,
                                  format="DD/MM/YYYY")
            if len(datas) == 2:
                inicio, fim = datas
        st.caption(f"Os últimos dias contam até {DATA_MAX:%d/%m/%Y}, último dia dos dados. "
                   "Dica: os botões por baixo dos gráficos também filtram o painel.")
        if n_ativos:
            st.button("Limpar filtros", on_click=limpar_recorte, args=(False,), width="stretch")
    dias = PERIODOS[periodo]
    if dias:
        inicio = DATA_MAX - timedelta(days=dias - 1)
    f = Filtros(inicio, fim, **escolhas)
    if f.ativos():
        with c_ativos:
            html(ui.pilulas([(v, True) for v in f.ativos()]))
    return f


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
        heroi=ind("Vendas (GMV)", brl_curto(k["gmv"]), "Valor total dos pedidos finalizados.", "gmv", s["gmv"]),
        apoio=[
            ind("Pedidos", numero(k["pedidos"]), "Pedidos feitos no período, incluindo cancelados.",
                "pedidos", s["pedidos"]),
            ind("Ticket médio", brl(k["ticket_medio"], 2), "Valor médio dos pedidos finalizados.",
                "ticket_medio", s["ticket_medio"]),
            ind("Lojas ativas", numero(k["lojas_ativas"]), "Lojas com pelo menos um pedido no período.",
                "lojas_ativas", s["lojas_ativas"]),
        ],
        saude=[
            ind("Tempo total", f"{numero(k['tempo_mediano_min'])} min",
                "Mediana, do pedido criado até concluído.", "tempo_mediano_min", menor_e_melhor=True),
            ind("Em até 60 min", pct(k["pct_ate_60"]), "Pedidos finalizados em 60 minutos ou menos.",
                "pct_ate_60", pontos=True),
            ind("Cancelados", pct(k["taxa_cancelamento"]), "Pedidos cancelados sobre pedidos feitos.",
                "taxa_cancelamento", pontos=True, menor_e_melhor=True),
            ind("Frete coberto", pct(k["frete_coberto"], 0),
                "Taxa de entrega cobrada dividida pelo custo da entrega.", "frete_coberto", pontos=True),
        ]))


_ONDE = {"segmento": lambda v: f"Em pedidos de <b>{v.lower()}</b>", "cidade": lambda v: f"Em <b>{v}</b>",
         "tipo_canal": lambda v: f"Em pedidos de <b>{v.lower()}</b>"}


def principal_achado(f: Filtros, k: dict) -> str | None:
    """O grupo (segmento, cidade ou tipo de canal) cujo tempo total mais se afasta do recorte."""
    geral = k["tempo_mediano_min"]
    if geral != geral or not geral:
        return None
    melhor = None
    for dim in _ONDE:
        d = metrics.por_dimensao(con, f, dim)
        d = d[(d["participacao"] >= 0.05) & d["tempo_mediano_min"].notna()]
        if len(d) < 2:
            continue
        linha = d.loc[d["tempo_mediano_min"].idxmax()]
        razao = linha["tempo_mediano_min"] / geral
        if melhor is None or razao > melhor[0]:
            melhor = (razao, dim, linha)
    if melhor is None or melhor[0] < 1.10:
        return None
    razao, dim, linha = melhor
    return (f"{_ONDE[dim](linha[dim])}, o tempo total é de <b>{numero(linha['tempo_mediano_min'])} min</b> "
            f"(mediana): <b>{numero(razao, 1)}×</b> os {numero(geral)} min do recorte, em "
            f"{numero(linha['pedidos'])} pedidos.")


def tabela(df, colunas: list[str]):
    df = df.copy()
    df.columns = colunas
    st.dataframe(df, hide_index=True, width="stretch")


def aba_resumo(f: Filtros, k: dict):
    dias = (f.fim - f.inicio).days
    grao = "day" if dias <= 45 else "week"
    s = metrics.serie_kpis(con, f, grao)
    if grao == "week" and len(s) > 4:
        s = s.iloc[1:-1]
    cartao(f"Como as vendas andaram, {'dia a dia' if grao == 'day' else 'semana a semana'}?",
           charts.serie(s, "periodo", "gmv"), sub="Vendas (GMV) em reais, pedidos finalizados")
    a, b = st.columns(2)
    cartao("Onde está a venda?", alvo=a, filtra="cidade", sub="Vendas (GMV) por cidade",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "cidade"), "cidade", "gmv"))
    seg = metrics.por_dimensao(con, f, "segmento")
    titulo = "Comida ou produtos?"
    if len(seg) == 2 and seg["gmv"].sum():
        c = seg.set_index("segmento").loc["Comida"]
        titulo = (f"Comida faz {pct(c['participacao'], 0)} dos pedidos e "
                  f"{pct(c['gmv'] / seg['gmv'].sum(), 0)} das vendas")
    cartao(titulo, alvo=b, filtra="segmento", sub="Vendas (GMV) por segmento",
           fig=charts.barras_h(seg, "segmento", "gmv"))
    with caixa():
        html(ui.cartao_titulo("As lojas que mais vendem", "As 10 primeiras em vendas no período"))
        top = metrics.top_lojas(con, f)
        tabela(top.assign(pedidos=top.pedidos.map(numero), gmv=top.gmv.map(brl),
                          tempo_mediano_min=top.tempo_mediano_min.map(lambda v: f"{numero(v)} min"),
                          taxa_cancelamento=top.taxa_cancelamento.map(pct)),
               ["Loja", "Segmento", "Cidade", "Pedidos", "Vendas", "Tempo total", "Cancelados"])
        html(ui.nota(NOTA_NOMES))
    html(ui.link_pergunta("Qual foi o GMV por cidade?"))


def aba_demanda(f: Filtros, k: dict):
    mapa = metrics.mapa_hora_dia(con, f)
    pico = mapa.loc[mapa["pedidos"].idxmax()]
    cartao("Quando o pedido acontece?", charts.calor_hora_dia(mapa),
           sub=f"Pedidos por dia da semana e hora (Brasília) · pico: {pico['dia_semana']} às {int(pico['hora'])}h")
    a, b = st.columns(2)
    cartao("Onde o ticket é mais alto?", alvo=a, filtra="cidade", sub="Ticket médio por cidade",
           fig=charts.barras_h(metrics.por_dimensao(con, f, "cidade"), "cidade", "ticket_medio", formato="moeda"))
    pg = metrics.pagamentos(con, f)
    titulo = "Como se paga?"
    if len(pg):
        titulo = f"{pct(pg['participacao'].iloc[0], 0)} do valor é pago por {pg['metodo'].iloc[0].lower()}"
    cartao(titulo, alvo=b, sub="Participação de cada método no valor pago",
           fig=charts.barras_h(pg, "metodo", "participacao", formato="pct"))
    fx = metrics.por_dimensao(con, f, "faixa_valor")
    fx = fx.set_index("faixa_valor").reindex(metrics.FAIXAS_VALOR).dropna(subset=["pedidos"]).reset_index()
    titulo = "Quanto se gasta por pedido?"
    if len(fx):
        maior = fx.loc[fx["pedidos"].idxmax()]
        titulo = f"{pct(maior['participacao'], 0)} dos pedidos ficam na faixa {maior['faixa_valor'].lower()}"
    cartao(titulo, filtra="faixa_valor", sub="Pedidos por faixa de valor",
           fig=charts.barras_v(fx, "faixa_valor", "pedidos", formato="numero"))
    cartao("Que hubs concentram a venda?", filtra="hub", sub="Vendas (GMV) dos 10 maiores hubs", nota=NOTA_NOMES,
           fig=charts.barras_h(metrics.por_dimensao(con, f, "hub", 10), "hub", "gmv"))
    html(ui.link_pergunta("Em que horário chegam mais pedidos?"))


def aba_canais(f: Filtros, k: dict):
    tipo = metrics.por_dimensao(con, f, "tipo_canal")
    a, b = st.columns(2)
    titulo = "De onde vêm os pedidos?"
    if len(tipo):
        maior = tipo.loc[tipo["pedidos"].idxmax()]
        titulo = f"{pct(maior['participacao'], 0)} dos pedidos vêm de {maior['tipo_canal'].lower()}"
    cartao(titulo, alvo=a, filtra="tipo_canal", sub="Pedidos por tipo de canal",
           fig=charts.barras_h(tipo, "tipo_canal", "pedidos", formato="numero"))
    cartao("Onde o ticket é maior?", alvo=b, filtra="tipo_canal", sub="Ticket médio por tipo de canal",
           fig=charts.barras_h(tipo, "tipo_canal", "ticket_medio", formato="moeda"))
    a, b = st.columns(2)
    cartao("Que canais vendem mais?", alvo=a, filtra="canal", sub="Vendas (GMV) dos 10 maiores canais", nota=NOTA_NOMES,
           fig=charts.barras_h(metrics.por_dimensao(con, f, "canal", 10), "canal", "gmv"))
    cartao("Em que canal o pedido chega mais rápido?", alvo=b, filtra="tipo_canal", sub="Pedidos finalizados em até 60 minutos",
           fig=charts.barras_h(tipo, "tipo_canal", "pct_ate_60", formato="pct", destaque="min"),
           nota="O canal próprio vende mais produtos, que demoram mais do que comida.")
    html(ui.link_pergunta("Marketplace ou canal próprio: onde o ticket é maior?"))


def aba_entrega(f: Filtros, k: dict):
    a, b = st.columns(2)
    et = metrics.etapas(con, f)
    titulo = "Onde o tempo vai?"
    if len(et):
        maior = et.loc[et["minutos"].idxmax()]
        titulo = f"{maior['etapa']} é a etapa mais longa: {numero(maior['minutos'])} min"
    cartao(titulo, alvo=a, sub="Mediana de cada etapa, da loja até o cliente",
           fig=charts.barras_h(et.iloc[::-1], "etapa", "minutos", formato="minutos") if len(et) else None,
           nota="As etapas não somam o tempo total: cada mediana é calculada em separado.")
    hora = metrics.tempo_por_hora(con, f)
    hora = hora[hora["pedidos"] >= 0.01 * hora["pedidos"].sum()]  # madrugada tem poucos pedidos e esperas de horas
    titulo = "A que horas o pedido demora mais?"
    if len(hora):
        pior = hora.loc[hora["tempo_mediano_min"].idxmax()]
        titulo = f"O pedido das {int(pior['hora'])}h é o mais demorado: {numero(pior['tempo_mediano_min'])} min"
    cartao(titulo, charts.linha_hora(hora, "tempo_mediano_min", k["tempo_mediano_min"]), alvo=b,
           sub="Tempo total mediano por hora do pedido",
           nota="Só horas com pelo menos 1% dos pedidos do recorte.")
    a, b = st.columns(2)
    modal = metrics.por_dimensao(con, f, "modal_entrega")
    cartao("Moto ou bicicleta?", alvo=a, filtra="modal_entrega", sub="Distância mediana de cada modal",
           fig=charts.barras_h(modal, "modal_entrega", "distancia_mediana_km", formato="km"),
           nota=" · ".join(f"{r.modal_entrega}: {pct(r.participacao, 0)} das entregas" for r in modal.itertuples()))
    dist = metrics.distancia_vs_transito(con, f)
    cartao("Quanto a distância pesa no trânsito?", alvo=b, sub="Tempo de trânsito mediano por distância",
           fig=charts.barras_v(dist, "distancia", "transito_mediano_min", formato="minutos"))
    cid = metrics.por_dimensao(con, f, "cidade")
    a, b = st.columns(2)
    cartao("Onde o pedido demora mais?", alvo=a, filtra="cidade", sub="Tempo total mediano por cidade",
           fig=charts.barras_h(cid, "cidade", "tempo_mediano_min", formato="minutos"))
    cartao("Onde a taxa não paga a entrega?", alvo=b, filtra="cidade", sub="Taxa cobrada sobre o custo da entrega, por cidade",
           fig=charts.barras_h(cid, "cidade", "frete_coberto", formato="pct", destaque="min"))
    cartao("Onde se cancela mais?", filtra="cidade", sub="Taxa de cancelamento por cidade",
           fig=charts.barras_h(cid, "cidade", "taxa_cancelamento", formato="pct"))
    html(ui.link_pergunta("Onde a taxa de entrega não cobre o custo?"))


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
    for aba, desenhar in zip(st.tabs(ABAS, default=inicial, key="aba_ativa"),
                             (aba_resumo, aba_demanda, aba_canais, aba_entrega)):
        with aba:
            desenhar(f, k)
    banco_conectado()


def banco_conectado():
    """Resultado da varredura do banco: o que existe, quanto tem, e se o acesso é só de leitura."""
    v = origem.varredura
    if v is None:
        return
    with caixa():
        estado = ("Usuário só de leitura: a Prova Real não consegue alterar nada neste banco."
                  if v.somente_leitura else
                  f"Atenção: o usuário tem permissão de escrita ({', '.join(v.privilegios)}). "
                  "Use um usuário só com SELECT.")
        html(ui.cartao_titulo(f"Banco conectado: {v.endereco}",
                              f"{len(v.tabelas)} tabelas encontradas · {numero(v.pedidos)} pedidos lidos"))
        tab = v.tabelas.assign(linhas=v.tabelas.linhas.map(numero),
                               esperada=v.tabelas.esperada.map({True: "Sim", False: "Não"}))
        tab.columns = ["Tabela", "Linhas", "Colunas", "Usada no painel"]
        st.dataframe(tab, hide_index=True, width="stretch")
        html(ui.nota(estado + " Os dados são copiados para uma camada de análise em memória ao abrir a página; "
                     "o painel e o assistente nunca consultam o MySQL diretamente."))


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

    digitada = st.chat_input("Ex.: por que produtos demoram mais do que comida?" if com_ia
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
html(ui.rodape(FONTE_DADOS["frase"], FONTE_DADOS["url"]))
