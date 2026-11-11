"""Gráficos Plotly com um único estilo visual.

Regras seguidas: uma cor por função (azul = magnitude), um só eixo por gráfico,
grelha discreta, barras finas com pontas arredondadas, rótulos em tinta neutra e
tooltip em todos os gráficos.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

AZUL = "#2a78d6"
LARANJA = "#eb6834"
ESCALA_AZUL = ["#f3f8fe", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CATEGORICA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
MUDO = "#898781"
GRELHA = "#e1e0d9"
EIXO = "#c3c2b7"
SUPERFICIE = "#fcfcfb"
FONTE = 'system-ui, -apple-system, "Segoe UI", sans-serif'

_MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]


def brl(v: float, casas: int = 0) -> str:
    """Formata em reais no padrão brasileiro: R$ 1.234,56."""
    if v is None or pd.isna(v):
        return "–"
    txt = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {txt}"


def brl_curto(v: float) -> str:
    if v is None or pd.isna(v):
        return "–"
    if abs(v) >= 1e6:
        return f"R$ {v / 1e6:.2f} mi".replace(".", ",")
    if abs(v) >= 1e3:
        return f"R$ {v / 1e3:.1f} mil".replace(".", ",")
    return brl(v)


def numero(v: float, casas: int = 0) -> str:
    if v is None or pd.isna(v):
        return "–"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float, casas: int = 1) -> str:
    if v is None or pd.isna(v):
        return "–"
    return f"{v * 100:.{casas}f}%".replace(".", ",")


def _base(fig: go.Figure, titulo: str = "", altura: int = 340) -> go.Figure:
    fig.update_layout(
        title=dict(text=titulo, font=dict(size=15, color=TINTA), x=0, xanchor="left", pad=dict(l=4)),
        font=dict(family=FONTE, size=12, color=TINTA_2),
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE,
        height=altura, margin=dict(l=8, r=16, t=48 if titulo else 12, b=8),
        showlegend=False, separators=",.",
        hoverlabel=dict(bgcolor="white", bordercolor=GRELHA, font=dict(family=FONTE, color=TINTA, size=12)),
        barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=EIXO, tickfont=dict(color=MUDO), automargin=True, title=None)
    fig.update_yaxes(gridcolor=GRELHA, zeroline=False, tickfont=dict(color=MUDO), automargin=True, title=None)
    return fig


def serie(df: pd.DataFrame, x: str, y: str, titulo: str, moeda: bool = True) -> go.Figure:
    prefixo = "R$ " if moeda else ""
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="lines", line=dict(color=AZUL, width=2),
        fill="tozeroy", fillcolor="rgba(42,120,214,0.08)",
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>{prefixo}%{{y:,.0f}}</b><extra></extra>"))
    _base(fig, titulo)
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(rangemode="tozero", tickprefix=prefixo, tickformat="~s")
    fig.update_xaxes(tickformat="%b")
    return fig


def barras_h(df: pd.DataFrame, categoria: str, valor: str, titulo: str,
             formato: str = "moeda", cor: str = AZUL) -> go.Figure:
    """Ranking horizontal, maior no topo, com o valor escrito no fim de cada barra."""
    d = df.sort_values(valor, ascending=True)
    fmt = {"moeda": brl_curto, "pct": pct, "numero": numero,
           "nota": lambda v: numero(v, 2), "minutos": lambda v: f"{numero(v)} min"}[formato]
    rotulos = [fmt(v) for v in d[valor]]
    fig = go.Figure(go.Bar(
        x=d[valor], y=d[categoria], orientation="h", marker_color=cor, width=0.62,
        text=rotulos, textposition="outside", textfont=dict(color=TINTA_2, size=12), cliponaxis=False,
        customdata=rotulos, hovertemplate="%{y}<br><b>%{customdata}</b><extra></extra>"))
    _base(fig, titulo, altura=max(240, 34 * len(d) + 70))
    fig.update_xaxes(visible=False, range=[0, float(d[valor].max()) * 1.18 if len(d) else 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TINTA_2, size=12))
    return fig


def barras_v(df: pd.DataFrame, categoria: str, valor: str, titulo: str,
             formato: str = "numero", faixa_y: list | None = None) -> go.Figure:
    fmt = {"moeda": brl_curto, "pct": pct, "numero": numero, "nota": lambda v: numero(v, 2)}[formato]
    rotulos = [fmt(v) for v in df[valor]]
    fig = go.Figure(go.Bar(
        x=df[categoria], y=df[valor], marker_color=AZUL, width=0.5,
        text=rotulos, textposition="outside", textfont=dict(color=TINTA_2), cliponaxis=False,
        customdata=rotulos, hovertemplate="%{x}<br><b>%{customdata}</b><extra></extra>"))
    _base(fig, titulo)
    fig.update_xaxes(type="category")
    fig.update_yaxes(range=faixa_y, tickformat=".0%" if formato == "pct" else None)
    return fig


def calor_hora_dia(df: pd.DataFrame, titulo: str) -> go.Figure:
    dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    m = (df.pivot(index="dia_semana", columns="hora", values="pedidos")
           .reindex(index=dias, columns=range(24)).fillna(0))
    fig = go.Figure(go.Heatmap(
        z=m.values, x=[f"{h}h" for h in m.columns], y=m.index, colorscale=ESCALA_AZUL,
        xgap=2, ygap=2, colorbar=dict(title="Pedidos", thickness=10, outlinewidth=0),
        hovertemplate="%{y}, %{x}<br><b>%{z:,.0f} pedidos</b><extra></extra>"))
    _base(fig, titulo, altura=320)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(dtick=2)
    return fig


def calor_culinaria_faixa(df: pd.DataFrame, titulo: str) -> go.Figure:
    m = df.pivot(index="culinaria", columns="faixa_etaria", values="participacao").fillna(0)
    m = m.loc[m.mean(axis=1).sort_values(ascending=False).index]
    texto = [[pct(v, 0) for v in linha] for linha in m.values]
    fig = go.Figure(go.Heatmap(
        z=m.values, x=m.columns, y=m.index, colorscale=ESCALA_AZUL, xgap=2, ygap=2,
        text=texto, texttemplate="%{text}", textfont=dict(size=12), showscale=False,
        hovertemplate="%{y} · %{x} anos<br><b>%{text} dos pedidos da faixa</b><extra></extra>"))
    _base(fig, titulo, altura=400)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=TINTA_2))
    fig.update_xaxes(type="category", ticksuffix=" anos", showline=False)
    return fig


def calor_coortes(df: pd.DataFrame, titulo: str) -> go.Figure:
    d = df[df["mes_n"] >= 1]
    m = d.pivot(index="coorte", columns="mes_n", values="retencao").sort_index()
    rotulo_y = [f"{_MESES[c.month - 1]}/{str(c.year)[2:]}" for c in pd.to_datetime(m.index)]
    texto = [["" if pd.isna(v) else pct(v, 0) for v in linha] for linha in m.values]
    fig = go.Figure(go.Heatmap(
        z=m.values, x=[f"Mês {int(c)}" for c in m.columns], y=rotulo_y, colorscale=ESCALA_AZUL,
        xgap=2, ygap=2, text=texto, texttemplate="%{text}", textfont=dict(size=11),
        showscale=False, hoverongaps=False,
        hovertemplate="Clientes novos de %{y}<br>%{x} depois: <b>%{text}</b> voltaram a pedir<extra></extra>"))
    _base(fig, titulo, altura=400)
    fig.update_yaxes(autorange="reversed", showgrid=False, type="category")
    fig.update_xaxes(type="category", showline=False)
    return fig


def linha_sla(df: pd.DataFrame, media: float, titulo: str) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df["hora"], y=df["pct_no_prazo"], mode="lines+markers",
        line=dict(color=AZUL, width=2), marker=dict(size=8, color=AZUL, line=dict(color=SUPERFICIE, width=2)),
        customdata=df[["pedidos", "tempo_medio_min"]],
        hovertemplate="%{x}h<br><b>%{y:.1%} no prazo</b><br>%{customdata[0]:,.0f} pedidos · "
                      "%{customdata[1]:.0f} min em média<extra></extra>"))
    if media is not None and not pd.isna(media):
        fig.add_hline(y=media, line=dict(color=MUDO, width=1, dash="dot"),
                      annotation_text=f"média {pct(media)}", annotation_position="top left",
                      annotation_font=dict(color=TINTA_2, size=11))
    _base(fig, titulo)
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(dtick=2, ticksuffix="h")
    return fig


def do_agente(df: pd.DataFrame, tipo: str, x: str, y: str, titulo: str) -> go.Figure:
    """Gráfico pedido pelo agente de IA a partir do resultado de uma consulta."""
    if x not in df.columns or y not in df.columns:
        raise ValueError(f"Colunas disponíveis: {', '.join(df.columns)}")
    d = df[[x, y]].dropna()
    if tipo == "linha":
        fig = go.Figure(go.Scatter(
            x=d[x], y=d[y], mode="lines+markers", line=dict(color=AZUL, width=2),
            marker=dict(size=8, line=dict(color=SUPERFICIE, width=2)),
            hovertemplate="%{x}<br><b>%{y:,.2f}</b><extra></extra>"))
        _base(fig, titulo)
        fig.update_yaxes(rangemode="tozero")
        return fig
    d = d.head(20)
    d[x] = d[x].astype(str)
    return barras_h(d, x, y, titulo, formato="numero")
