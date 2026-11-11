"""Peças de interface em HTML/CSS: sistema visual "Boletim".

Tudo o que não é gráfico nem widget do Streamlit sai daqui: folha de estilos,
cabeçalho, cartões de indicador com mini-gráfico, faixa de principal achado,
títulos de cartão, estado vazio e balões da conversa.
"""

from __future__ import annotations

import base64
from html import escape

FUNDO = "#F5F2EA"
SUPERFICIE = "#FFFFFF"
AFUNDADO = "#ECE8DD"
BORDA = "#DCD7C9"
TINTA = "#16211F"
TINTA_2 = "#4A5653"
MUDO = "#6B7673"
PETROLEO = "#0B5D66"
LAVADO = "#E3EFEF"
POSITIVO = "#1F7A3F"
NEGATIVO = "#9F2D55"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --fundo:#F5F2EA; --sup:#FFFFFF; --afundado:#ECE8DD; --borda:#DCD7C9;
  --tinta:#16211F; --tinta2:#4A5653; --mudo:#6B7673;
  --petroleo:#0B5D66; --lavado:#E3EFEF; --pos:#1F7A3F; --neg:#9F2D55;
  --serif:'Fraunces', Georgia, serif;
  --sans:'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --mono:'JetBrains Mono', ui-monospace, Consolas, monospace;
}
.stApp, .stApp button, .stApp input, .stApp textarea, .stApp p, .stApp label, .stApp li {
  font-family: var(--sans);
}
.stApp { background: var(--fundo); color: var(--tinta); }
#MainMenu, footer, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stDecoration"] {
  display: none !important;
}
.block-container { max-width: 1200px; padding: 28px 24px 40px; }
[data-testid="stElementToolbar"] { display: none; }

/* ---------- cabeçalho ---------- */
.pr-marca { display:flex; align-items:baseline; gap:10px; }
.pr-marca i { width:10px; height:10px; background:var(--petroleo); display:inline-block; border-radius:2px; }
.pr-marca b { font-family:var(--serif); font-weight:600; font-size:22px; letter-spacing:-0.01em; color:var(--tinta); }
.pr-marca span { font-size:13px; color:var(--mudo); }
.pr-pilulas { display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap; }
.pr-pilula { font-family:var(--mono); font-size:11.5px; color:var(--tinta2); border:1px solid var(--borda);
  border-radius:999px; padding:5px 12px; background:var(--sup); white-space:nowrap; }
.pr-pilula.ativa { background:var(--lavado); border-color:#BFD9D9; color:#084A52; }
.pr-filete { border:0; border-top:1px solid var(--borda); margin:14px 0 18px; }

/* ---------- títulos ---------- */
.pr-titulo { font-family:var(--serif); font-weight:600; font-size:34px; line-height:40px;
  letter-spacing:-0.015em; margin:6px 0 4px; color:var(--tinta); }
.pr-sub { font-family:var(--mono); font-size:12px; color:var(--mudo); margin:0 0 4px; }
.pr-intro { font-size:15px; line-height:24px; color:var(--tinta2); max-width:720px; margin:6px 0 0; }

/* ---------- indicadores ---------- */
.pr-kpis { display:grid; grid-template-columns:5fr 7fr; gap:16px; margin:18px 0 16px; }
.pr-rotulo { font-size:11.5px; font-weight:600; letter-spacing:0.06em; text-transform:uppercase; color:var(--mudo); }
.pr-heroi { grid-row:span 2; background:var(--tinta); color:var(--fundo); border-radius:14px; padding:26px 28px;
  display:flex; flex-direction:column; justify-content:space-between; min-height:268px; }
.pr-heroi .pr-rotulo { color:#A9B5B1; }
.pr-heroi .pr-valor { font-family:var(--serif); font-weight:600; font-size:64px; line-height:1.02;
  letter-spacing:-0.02em; margin-top:10px; font-variant-numeric:tabular-nums; }
.pr-heroi .pr-var { color:#D5DDD9; }
.pr-heroi .pr-var.pos b { color:#8FD9A8; } .pr-heroi .pr-var.neg b { color:#F2A6C0; }
.pr-heroi .pr-mini { width:100%; height:72px; margin-top:14px; display:block; }
.pr-apoio { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.pr-kpi { background:var(--sup); border:1px solid var(--borda); border-radius:14px; padding:18px 20px;
  min-height:126px; display:flex; flex-direction:column; }
.pr-kpi .pr-valor { font-family:var(--serif); font-weight:600; font-size:30px; line-height:1.15;
  margin-top:6px; font-variant-numeric:tabular-nums; color:var(--tinta); }
.pr-kpi .pr-mini { width:120px; height:32px; margin-top:auto; padding-top:8px; display:block; }
.pr-var { font-size:12.5px; color:var(--mudo); margin-top:4px; }
.pr-var.pos b { color:var(--pos); } .pr-var.neg b { color:var(--neg); }
.pr-saude { background:var(--sup); border:1px solid var(--borda); border-radius:14px;
  display:grid; grid-template-columns:repeat(4,1fr); }
.pr-saude > div { padding:16px 20px; border-left:1px solid var(--borda); }
.pr-saude > div:first-child { border-left:0; }
.pr-saude .pr-valor { font-family:var(--serif); font-weight:600; font-size:24px; margin-top:4px;
  font-variant-numeric:tabular-nums; color:var(--tinta); }
@media (max-width: 900px) {
  .pr-kpis, .pr-apoio { grid-template-columns:1fr; }
  .pr-saude { grid-template-columns:repeat(2,1fr); }
  .pr-saude > div:nth-child(3) { border-left:0; }
  .pr-heroi .pr-valor { font-size:48px; }
}

/* ---------- principal achado ---------- */
.pr-achado { background:var(--lavado); border-left:4px solid var(--petroleo); border-radius:0 10px 10px 0;
  padding:14px 20px; margin:0 0 22px; }
.pr-achado p { font-size:18px; line-height:26px; color:var(--tinta); margin:4px 0 0; }
.pr-achado .pr-rotulo { color:#084A52; }

/* ---------- cartões ---------- */
[class*="st-key-cartao"] { background:var(--sup); border:1px solid var(--borda) !important;
  border-radius:14px !important; padding:20px 22px 14px !important; }
.pr-cartao-t { font-size:16px; font-weight:600; line-height:22px; color:var(--tinta); margin:0; }
.pr-cartao-s { font-size:13px; color:var(--mudo); margin:2px 0 0; }
.pr-nota { font-family:var(--mono); font-size:11px; color:var(--mudo); margin:0 0 4px; line-height:17px; }
.pr-link { display:inline-block; margin:6px 0 2px; font-size:14px; font-weight:600; color:var(--petroleo) !important;
  text-decoration:none; border-bottom:1px solid #9CC3C4; padding-bottom:1px; }
.pr-link:hover { color:#084A52 !important; border-color:#084A52; }
.pr-vazio { background:var(--sup); border:1px solid var(--borda); border-radius:14px; text-align:center;
  padding:56px 24px 28px; margin-top:18px; }
.pr-vazio b { font-family:var(--serif); font-weight:600; font-size:22px; display:block; color:var(--tinta); }
.pr-vazio span { font-size:15px; color:var(--tinta2); }
.pr-rodape { font-family:var(--mono); font-size:11px; color:var(--mudo); border-top:1px solid var(--borda);
  margin-top:40px; padding-top:14px; line-height:18px; }

/* ---------- widgets do Streamlit ---------- */
.stTabs [data-baseweb="tab-list"] { gap:28px; border-bottom:1px solid var(--borda); }
.stTabs [data-baseweb="tab"] { padding:10px 0; height:auto; }
.stTabs [data-baseweb="tab"] p { font-size:15px; font-weight:600; color:var(--mudo); }
.stTabs [aria-selected="true"] p { color:var(--tinta); }
.stTabs [data-baseweb="tab-highlight"] { background:var(--petroleo); height:3px; }
.stTabs [data-baseweb="tab-border"] { display:none; }
.stTabs [data-baseweb="tab-panel"] { padding-top:20px; }
.stButton button, [data-testid="stPopover"] button { border-radius:8px; border:1px solid var(--borda);
  background:var(--sup); color:var(--tinta); font-weight:500; }
.stButton button:hover, [data-testid="stPopover"] button:hover { border-color:var(--petroleo); color:var(--petroleo); }
[data-testid="stDataFrame"] { border:1px solid var(--borda); border-radius:10px; overflow:hidden; }
[data-testid="stExpander"] details { border:1px solid var(--borda); border-radius:10px; background:var(--fundo); }
[data-testid="stExpander"] summary p { font-family:var(--mono); font-size:12.5px; color:var(--tinta2); }
[data-testid="stChatInput"] { border-radius:12px; border:1px solid var(--borda); background:var(--sup); }
code, pre, .stCode { font-family:var(--mono) !important; font-size:13px !important; }

/* ---------- conversa ---------- */
.pr-pergunta { display:flex; justify-content:flex-end; margin:18px 0 10px; }
.pr-pergunta span { background:var(--afundado); border-radius:16px 16px 4px 16px; padding:10px 16px;
  font-size:15px; color:var(--tinta); max-width:75%; }
.pr-meta { font-family:var(--mono); font-size:11px; color:var(--mudo); margin:0 0 4px; }
.st-key-sugestoes .stButton button { text-align:left; justify-content:flex-start; padding:14px 16px; min-height:58px;
  font-size:15px; border-radius:12px; }
</style>
"""


def _mini(valores, largura: int = 120, altura: int = 32, cor: str = PETROLEO, preenchido: bool = False) -> str:
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
    return f'<div class="pr-marca"><i></i><b>{escape(nome)}</b><span>{escape(tagline)}</span></div>'


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
         f'{_mini(heroi.get("serie") or [], 320, 64, "#7FC4C4", preenchido=True)}</div>')
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


def rodape(texto: str) -> str:
    return f'<div class="pr-rodape">{escape(texto)}</div>'
