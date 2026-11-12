"""Peças de interface em HTML/CSS: vermelho de app de delivery, cartões arredondados.

Tudo o que não é gráfico nem widget do Streamlit sai daqui: folha de estilos,
cabeçalho, cartões de indicador com mini-gráfico, faixa de principal achado,
títulos de cartão, estado vazio e balões da conversa.
"""

from __future__ import annotations

import base64
from html import escape

FUNDO = "#F7F7F7"
SUPERFICIE = "#FFFFFF"
AFUNDADO = "#F2F2F2"
BORDA = "#E8E8E8"
TINTA = "#3E3E3E"
TINTA_2 = "#5F5F5F"
MUDO = "#757575"
DESTAQUE = "#EA1D2C"       # vermelho de app de delivery
DESTAQUE_ESCURO = "#C8101E"
LAVADO = "#FDECEE"
POSITIVO = "#1E8E4E"
NEGATIVO = "#C2410C"       # laranja escuro: o vermelho já é a cor da marca, não pode significar "ruim"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@700;800;900&family=Nunito+Sans:opsz,wght@6..12,400;6..12,600;6..12,700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --fundo:#F7F7F7; --sup:#FFFFFF; --afundado:#F2F2F2; --borda:#E8E8E8;
  --tinta:#3E3E3E; --tinta2:#5F5F5F; --mudo:#757575;
  --destaque:#EA1D2C; --destaque-escuro:#C8101E; --lavado:#FDECEE; --pos:#1E8E4E; --neg:#C2410C;
  --titulo:'Nunito', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --sans:'Nunito Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --mono:'JetBrains Mono', ui-monospace, Consolas, monospace;
  --sombra:0 1px 2px rgba(0,0,0,.04), 0 4px 16px rgba(0,0,0,.05);
}
.stApp, .stApp button, .stApp input, .stApp textarea, .stApp p, .stApp label, .stApp li {
  font-family: var(--sans);
}
.stApp { background: var(--fundo); color: var(--tinta); }
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stDecoration"] {
  display: none !important;
}
.block-container { max-width: 1200px; padding: 22px 24px 40px; }
[data-testid="stElementToolbar"] { display: none; }

/* ---------- cabeçalho ---------- */
.pr-marca { display:flex; align-items:center; gap:10px; }
.pr-marca i { width:30px; height:30px; background:var(--destaque); display:inline-flex; border-radius:9px;
  align-items:center; justify-content:center; color:#fff; font-style:normal; font-family:var(--titulo);
  font-weight:900; font-size:17px; }
.pr-marca b { font-family:var(--titulo); font-weight:900; font-size:23px; letter-spacing:-0.01em; color:var(--destaque); }
.pr-marca span { font-size:13px; color:var(--mudo); }
.pr-pilulas { display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
.pr-pilula { font-size:12px; font-weight:600; color:var(--tinta2); border:1px solid var(--borda);
  border-radius:999px; padding:5px 12px; background:var(--sup); white-space:nowrap; }
.pr-pilula.ativa { background:var(--lavado); border-color:#F7C3C8; color:var(--destaque-escuro); }
.pr-filete { border:0; border-top:1px solid var(--borda); margin:14px 0 18px; }

/* ---------- títulos ---------- */
.pr-titulo { font-family:var(--titulo); font-weight:900; font-size:32px; line-height:38px;
  letter-spacing:-0.015em; margin:6px 0 4px; color:var(--tinta); }
.pr-sub { font-size:13px; color:var(--mudo); margin:0 0 4px; }
.pr-intro { font-size:15px; line-height:24px; color:var(--tinta2); max-width:720px; margin:6px 0 0; }

/* ---------- indicadores ---------- */
.pr-kpis { display:grid; grid-template-columns:5fr 7fr; gap:16px; margin:18px 0 16px; }
.pr-rotulo { font-size:12px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; color:var(--mudo); }
.pr-heroi { grid-row:span 2; background:linear-gradient(135deg, #EA1D2C 0%, #C8101E 100%); color:#fff;
  border-radius:20px; padding:26px 28px; box-shadow:0 8px 24px rgba(234,29,44,.25);
  display:flex; flex-direction:column; justify-content:space-between; min-height:268px; }
.pr-heroi .pr-rotulo { color:#FFD9DC; }
.pr-heroi .pr-valor { font-family:var(--titulo); font-weight:900; font-size:62px; line-height:1.02;
  letter-spacing:-0.02em; margin-top:10px; font-variant-numeric:tabular-nums; }
.pr-heroi .pr-var { color:#FFE3E5; }
.pr-heroi .pr-var b { background:rgba(255,255,255,.18); color:#fff; padding:2px 8px; border-radius:999px; }
.pr-heroi .pr-mini { width:100%; height:72px; margin-top:14px; display:block; }
.pr-apoio { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.pr-kpi { background:var(--sup); border:1px solid var(--borda); border-radius:16px; padding:18px 20px;
  min-height:126px; display:flex; flex-direction:column; box-shadow:var(--sombra); }
.pr-kpi .pr-valor { font-family:var(--titulo); font-weight:800; font-size:29px; line-height:1.15;
  margin-top:6px; font-variant-numeric:tabular-nums; color:var(--tinta); white-space:nowrap; }
.pr-kpi .pr-mini { width:120px; height:32px; margin-top:auto; padding-top:8px; display:block; }
.pr-var { font-size:12.5px; color:var(--mudo); margin-top:4px; }
.pr-var.pos b { color:var(--pos); } .pr-var.neg b { color:var(--neg); }
.pr-heroi .pr-var.pos b, .pr-heroi .pr-var.neg b { color:#fff; }  /* no cartão vermelho, a seta diz o sentido */
.pr-saude { background:var(--sup); border:1px solid var(--borda); border-radius:16px; box-shadow:var(--sombra);
  display:grid; grid-template-columns:repeat(4,1fr); }
.pr-saude > div { padding:16px 20px; border-left:1px solid var(--borda); }
.pr-saude > div:first-child { border-left:0; }
.pr-saude .pr-valor { font-family:var(--titulo); font-weight:800; font-size:24px; margin-top:4px;
  font-variant-numeric:tabular-nums; color:var(--tinta); }
@media (max-width: 900px) {
  .pr-kpis, .pr-apoio { grid-template-columns:1fr; }
  .pr-saude { grid-template-columns:repeat(2,1fr); }
  .pr-saude > div:nth-child(3) { border-left:0; }
  .pr-heroi .pr-valor { font-size:46px; }
}

/* ---------- principal achado ---------- */
.pr-achado { background:var(--lavado); border-left:5px solid var(--destaque); border-radius:0 14px 14px 0;
  padding:14px 20px; margin:0 0 22px; }
.pr-achado p { font-size:18px; line-height:26px; color:var(--tinta); margin:4px 0 0; }
.pr-achado .pr-rotulo { color:var(--destaque-escuro); }

/* ---------- cartões ---------- */
[class*="st-key-cartao"] { background:var(--sup); border:1px solid var(--borda) !important;
  border-radius:18px !important; padding:20px 22px 14px !important; box-shadow:var(--sombra); }
.pr-cartao-t { font-family:var(--titulo); font-size:17px; font-weight:800; line-height:23px; color:var(--tinta); margin:0; }
.pr-cartao-s { font-size:13px; color:var(--mudo); margin:2px 0 0; }
.pr-nota { font-size:11.5px; color:var(--mudo); margin:0 0 4px; line-height:17px; }
.pr-link { display:inline-flex; align-items:center; gap:6px; margin:6px 0 2px; font-size:14px; font-weight:700;
  color:var(--destaque) !important; text-decoration:none; background:var(--lavado); border-radius:999px; padding:7px 14px; }
.pr-link:hover { background:var(--destaque); color:#fff !important; }
.pr-vazio { background:var(--sup); border:1px solid var(--borda); border-radius:18px; text-align:center;
  padding:56px 24px 28px; margin-top:18px; box-shadow:var(--sombra); }
.pr-vazio b { font-family:var(--titulo); font-weight:800; font-size:22px; display:block; color:var(--tinta); }
.pr-vazio span { font-size:15px; color:var(--tinta2); }
.pr-rodape { font-size:11.5px; color:var(--mudo); border-top:1px solid var(--borda);
  margin-top:40px; padding-top:14px; line-height:18px; }
.pr-rodape a { color:var(--destaque); }

/* ---------- widgets do Streamlit ---------- */
/* abas como pílulas: o Streamlit 1.67 usa role="tablist" e data-testid="stTab" */
.stTabs [role="tablist"] { gap:8px; border-bottom:0 !important; box-shadow:none !important; flex-wrap:wrap; height:auto; }
.stTabs [role="tablist"]::after, .stTabs [role="tablist"]::before { display:none !important; }
.stTabs [data-testid="stTab"] { padding:8px 20px; height:auto; min-height:38px; border-radius:999px;
  background:var(--sup); border:1px solid var(--borda); box-shadow:none; cursor:pointer; }
.stTabs [data-testid="stTab"] p { font-size:14.5px; font-weight:700; color:var(--tinta2); margin:0; white-space:nowrap; }
.stTabs [data-testid="stTab"]:hover { border-color:var(--destaque); }
.stTabs [data-testid="stTab"][aria-selected="true"] { background:var(--destaque); border-color:var(--destaque); }
.stTabs [data-testid="stTab"][aria-selected="true"] p { color:#fff; }
.stTabs [data-testid="stTabPanel"] { padding-top:20px; }
.stButton button, [data-testid="stPopover"] button { border-radius:999px; border:1px solid var(--borda);
  background:var(--sup); color:var(--tinta); font-weight:700; }
.stButton button:hover, [data-testid="stPopover"] button:hover { border-color:var(--destaque); color:var(--destaque); }
[data-testid="stSegmentedControl"] button[aria-checked="true"], [data-testid="stBaseButton-segmented_controlActive"] {
  background:var(--destaque) !important; border-color:var(--destaque) !important; color:#fff !important; }
[data-testid="stBaseButton-segmented_controlActive"] p { color:#fff !important; }
[data-testid="stDataFrame"] { border:1px solid var(--borda); border-radius:12px; overflow:hidden; }
[data-testid="stExpander"] details { border:1px solid var(--borda); border-radius:12px; background:var(--fundo); }
[data-testid="stExpander"] summary p { font-size:13px; font-weight:700; color:var(--tinta2); }
[data-testid="stChatInput"] { border-radius:999px; border:1px solid var(--borda); background:var(--sup); }
[data-testid="stButtonGroup"] button { border-radius:999px !important; font-weight:700; font-size:13px; }
[data-testid="stButtonGroup"] button:hover { border-color:var(--destaque) !important; color:var(--destaque) !important; }
[class*="st-key-cartao"] [data-testid="stWidgetLabel"] p { font-size:12px; font-weight:700; color:var(--mudo); }
[data-baseweb="tag"] { background:var(--lavado) !important; }
[data-baseweb="tag"] span { color:var(--destaque-escuro) !important; }
code, pre, .stCode { font-family:var(--mono) !important; font-size:13px !important; }

/* ---------- conversa ---------- */
.pr-pergunta { display:flex; justify-content:flex-end; margin:18px 0 10px; }
.pr-pergunta span { background:var(--destaque); color:#fff; border-radius:18px 18px 4px 18px; padding:10px 16px;
  font-size:15px; max-width:75%; }
.pr-meta { font-size:11.5px; color:var(--mudo); margin:0 0 4px; }
.st-key-sugestoes .stButton button { text-align:left; justify-content:flex-start; padding:14px 18px; min-height:58px;
  font-size:15px; border-radius:16px; box-shadow:var(--sombra); }
</style>
"""


def _mini(valores, largura: int = 120, altura: int = 32, cor: str = DESTAQUE, preenchido: bool = False) -> str:
    """Mini-gráfico de linha em SVG (sem eixos): mostra a forma da série, não os valores."""
    v = [float(x) for x in valores if x is not None and x == x]
    if len(v) < 3:
        return ""
    lo, hi = min(v), max(v)
    amp = (hi - lo) or 1.0
    m = 4
    pts = [(m + i * (largura - 2 * m) / (len(v) - 1), altura - m - (x - lo) / amp * (altura - 2 * m))
           for i, x in enumerate(v)]
    linha = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    area = ""
    if preenchido:
        area = (f'<polygon points="{m},{altura} {linha} {largura - m},{altura}" fill="{cor}" opacity="0.16"/>')
    ux, uy = pts[-1]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {largura} {altura}" preserveAspectRatio="none">{area}'
           f'<polyline points="{linha}" fill="none" stroke="{cor}" stroke-width="1.6" '
           f'stroke-linejoin="round" stroke-linecap="round"/>'
           f'<circle cx="{ux:.1f}" cy="{uy:.1f}" r="2.6" fill="{cor}"/></svg>')
    # o st.html remove <svg> embutido; como imagem em data-URI ele passa
    dados = base64.b64encode(svg.encode()).decode()
    return f'<img class="pr-mini" alt="Evolução no período" src="data:image/svg+xml;base64,{dados}">'


def _variacao(var: tuple | None) -> str:
    """var = (texto, 'pos' | 'neg' | 'neu', comparação). Seta + texto: a cor nunca é o único sinal."""
    if not var:
        return '<div class="pr-var">sem comparação</div>'
    texto, estado, comparacao = var
    if estado == "neu":
        seta, texto = "=", texto.lstrip("+-")
    else:
        seta = "▼" if texto.startswith("-") else "▲"
    return f'<div class="pr-var {estado}"><b>{seta} {escape(texto)}</b> {escape(comparacao)}</div>'


def cabecalho_marca(nome: str, tagline: str) -> str:
    return f'<div class="pr-marca"><i>{escape(nome[:1])}</i><b>{escape(nome)}</b><span>{escape(tagline)}</span></div>'


def pilulas(itens: list[tuple[str, bool]]) -> str:
    return '<div class="pr-pilulas">' + "".join(
        f'<span class="pr-pilula{" ativa" if ativa else ""}">{escape(t)}</span>' for t, ativa in itens) + "</div>"


def titulo(texto: str, sub: str = "", intro: str = "") -> str:
    h = f'<h1 class="pr-titulo">{escape(texto)}</h1>'
    if sub:
        h += f'<p class="pr-sub">{escape(sub)}</p>'
    if intro:
        h += f'<p class="pr-intro">{escape(intro)}</p>'
    return h


def indicadores(heroi: dict, apoio: list[dict], saude: list[dict]) -> str:
    """Cada indicador: {rotulo, valor, ajuda, var, serie}. O herói é o número principal da página."""
    h = (f'<div class="pr-heroi" title="{escape(heroi["ajuda"])}"><div>'
         f'<div class="pr-rotulo">{escape(heroi["rotulo"])}</div>'
         f'<div class="pr-valor">{escape(heroi["valor"])}</div>{_variacao(heroi.get("var"))}</div>'
         f'{_mini(heroi.get("serie") or [], 320, 64, "#FFFFFF", preenchido=True)}</div>')
    a = "".join(
        f'<div class="pr-kpi" title="{escape(k["ajuda"])}"><div class="pr-rotulo">{escape(k["rotulo"])}</div>'
        f'<div class="pr-valor">{escape(k["valor"])}</div>{_variacao(k.get("var"))}'
        f'{_mini(k.get("serie") or [])}</div>' for k in apoio)
    s = "".join(
        f'<div title="{escape(k["ajuda"])}"><div class="pr-rotulo">{escape(k["rotulo"])}</div>'
        f'<div class="pr-valor">{escape(k["valor"])}</div>{_variacao(k.get("var"))}</div>' for k in saude)
    return f'<div class="pr-kpis">{h}<div class="pr-apoio">{a}</div><div class="pr-saude">{s}</div></div>'


def achado(frase_html: str) -> str:
    """`frase_html` já vem montada pelo código (pode ter <b>); não recebe texto do usuário."""
    return f'<div class="pr-achado"><div class="pr-rotulo">Principal achado</div><p>{frase_html}</p></div>'


def cartao_titulo(texto: str, sub: str = "") -> str:
    h = f'<p class="pr-cartao-t">{escape(texto)}</p>'
    return h + (f'<p class="pr-cartao-s">{escape(sub)}</p>' if sub else "")


def nota(texto: str) -> str:
    return f'<p class="pr-nota">{escape(texto)}</p>'


def link_pergunta(pergunta: str) -> str:
    from urllib.parse import quote
    return (f'<a class="pr-link" href="?pergunta={quote(pergunta)}" target="_self">'
            f'Perguntar: “{escape(pergunta)}”</a>')


def vazio(titulo_: str, texto: str) -> str:
    return f'<div class="pr-vazio"><b>{escape(titulo_)}</b><span>{escape(texto)}</span></div>'


def pergunta(texto: str) -> str:
    return f'<div class="pr-pergunta"><span>{escape(texto)}</span></div>'


def rodape(texto: str, url: str = "") -> str:
    fonte = f' <a href="{escape(url)}" target="_blank" rel="noopener">Ver a fonte</a>' if url else ""
    return f'<div class="pr-rodape">{escape(texto)}{fonte}</div>'
