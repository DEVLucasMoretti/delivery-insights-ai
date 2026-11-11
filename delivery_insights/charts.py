"""Gráficos Plotly no sistema visual "Boletim".

Regras: uma cor por função (petróleo = o que se destaca, cinza = o resto), um só
eixo por gráfico, grelha horizontal discreta, valor escrito na própria barra,
tooltip em todos. O título fica fora do gráfico (no cartão HTML), por isso as
funções não recebem título.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

PETROLEO = "#0B5D66"
NEUTRO = "#C4C9C3"
ESCALA = ["#EEF4F3", "#CFE3E1", "#A5CCC9", "#73B0AD", "#45928F", "#20747A", "#0B5D66", "#063F47"]
TINTA = "#16211F"
TINTA_2 = "#4A5653"
MUDO = "#6B7673"
GRELHA = "#E7E3D8"
EIXO = "#DCD7C9"
CLARO = "#F5F2EA"
FONTE = '"Instrument Sans", system-ui, -apple-system, "Segoe UI", sans-serif'

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


_FORMATOS = {
    "moeda": brl_curto, "pct": pct, "numero": numero,
    "minutos": lambda v: f"{numero(v)} min", "km": lambda v: f"{numero(v, 1)} km",
    "decimal": lambda v: numero(v, 2),
}


def _base(fig: go.Figure, altura: int = 320) -> go.Figure:
    fig.update_layout(
        font=dict(family=FONTE, size=12, color=TINTA_2),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        height=altura, margin=dict(l=0, r=24, t=8, b=0),
        showlegend=False, separators=",.",
        hoverlabel=dict(bgcolor=TINTA, bordercolor=TINTA, font=dict(family=FONTE, color=CLARO, size=12)),
        barcornerradius=3,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=EIXO, tickfont=dict(color=MUDO, size=12),
                     automargin=True, title=None, ticks="")
    fig.update_yaxes(gridcolor=GRELHA, gridwidth=1, zeroline=False, showline=False, nticks=5,
                     tickfont=dict(color=MUDO, size=12), automargin=True, title=None)
    return fig


def _cores(valores: pd.Series, destaque: str | None) -> list[str]:
    """Todas as barras em cinza, menos a que se quer que o leitor veja primeiro."""
    if destaque not in ("max", "min") or valores.empty:
        return [PETROLEO] * len(valores)
    alvo = valores.idxmax() if destaque == "max" else valores.idxmin()
    return [PETROLEO if i == alvo else NEUTRO for i in valores.index]


def serie(df: pd.DataFrame, x: str, y: str, moeda: bool = True) -> go.Figure:
    """Linha no tempo, com o pico e o último ponto anotados."""
    prefixo = "R$ " if moeda else ""
    fmt = brl_curto if moeda else numero
    fig = go.Figure(go.Scatter(
        x=df[x], y=df[y], mode="lines", line=dict(color=PETROLEO, width=2),
        fill="tozeroy", fillcolor="rgba(11,93,102,0.06)",
        hovertemplate=f"%{{x|%d/%m/%Y}}<br><b>{prefixo}%{{y:,.0f}}</b><extra></extra>"))
    if len(df) >= 3:
        pico, ultimo = df.loc[df[y].idxmax()], df.iloc[-1]
        pontos = [(pico, "pico ")] + ([(ultimo, "")] if ultimo[x] != pico[x] else [])
        for ponto, rotulo in pontos:
            fig.add_trace(go.Scatter(
                x=[ponto[x]], y=[ponto[y]], mode="markers+text", hoverinfo="skip",
                marker=dict(size=8, color=PETROLEO, line=dict(color="white", width=2)),
                text=[f"<b>{rotulo}{fmt(ponto[y])}</b>"], textposition="top center",
                textfont=dict(color=TINTA, size=12), cliponaxis=False))
    _base(fig, 300)
    fig.update_layout(hovermode="x unified", margin=dict(l=0, r=44, t=26, b=0))
    fig.update_yaxes(rangemode="tozero", tickprefix=prefixo, tickformat="~s")
    meses = pd.date_range(df[x].min(), df[x].max(), freq="MS") if len(df) else []
    if len(meses) >= 2:  # rótulos dos meses em português
        fig.update_xaxes(tickvals=meses, ticktext=[_MESES[m.month - 1] for m in meses])
    else:
        fig.update_xaxes(tickformat="%d/%m")
    return fig


def barras_h(df: pd.DataFrame, categoria: str, valor: str, formato: str = "moeda",
             destaque: str | None = "max") -> go.Figure:
    """Ranking horizontal, maior no topo, com o valor escrito no fim de cada barra."""
    d = df.sort_values(valor, ascending=True).reset_index(drop=True)
    fmt = _FORMATOS[formato]
    cores = _cores(d[valor], destaque)
    rotulos = [fmt(v) for v in d[valor]]
    texto = [f"<b>{r}</b>" if c == PETROLEO and destaque else r for r, c in zip(rotulos, cores)]
    total = d[valor].sum()
    contexto = [f"{pct(v / total, 0)} do total" if formato in ("moeda", "numero") and total else ""
                for v in d[valor]]
    fig = go.Figure(go.Bar(
        x=d[valor], y=d[categoria], orientation="h", marker_color=cores, width=0.6,
        text=texto, textposition="outside", textfont=dict(color=TINTA, size=12), cliponaxis=False,
        customdata=list(zip(rotulos, contexto)),
        hovertemplate="%{y}<br><b>%{customdata[0]}</b> %{customdata[1]}<extra></extra>"))
    _base(fig, altura=max(170, 32 * len(d) + 26))
    fig.update_layout(margin=dict(l=0, r=64, t=4, b=0))
    fig.update_xaxes(visible=False, range=[0, float(d[valor].max()) * 1.02 if len(d) else 1])
    fig.update_yaxes(showgrid=False, tickfont=dict(color=TINTA_2, size=13), ticksuffix="  ",
                     type="category", tickmode="array", tickvals=list(d[categoria]))
    return fig


def barras_v(df: pd.DataFrame, categoria: str, valor: str, formato: str = "numero",
             faixa_y: list | None = None, destaque: str | None = "max") -> go.Figure:
    d = df.reset_index(drop=True)
    fmt = _FORMATOS[formato]
    cores = _cores(d[valor], destaque)
    rotulos = [fmt(v) for v in d[valor]]
    texto = [f"<b>{r}</b>" if c == PETROLEO and destaque else r for r, c in zip(rotulos, cores)]
    fig = go.Figure(go.Bar(
        x=d[categoria], y=d[valor], marker_color=cores, width=0.55,
        text=texto, textposition="outside", textfont=dict(color=TINTA, size=12), cliponaxis=False,
        customdata=rotulos, hovertemplate="%{x}<br><b>%{customdata}</b><extra></extra>"))
    _base(fig, 300)
    fig.update_layout(margin=dict(l=0, r=8, t=26, b=0))
    fig.update_xaxes(type="category", tickfont=dict(color=TINTA_2, size=12))
    fig.update_yaxes(range=faixa_y, visible=False)
    return fig


def _contorno_do_pico(fig: go.Figure, matriz: pd.DataFrame) -> None:
    if matriz.size == 0 or matriz.max().max() <= 0:
        return
    col = int(matriz.max(axis=0).values.argmax())
    lin = int(matriz.iloc[:, col].values.argmax())
    fig.add_shape(type="rect", x0=col - 0.5, x1=col + 0.5, y0=lin - 0.5, y1=lin + 0.5,
                  line=dict(color=TINTA, width=2), fillcolor="rgba(0,0,0,0)")


def calor_hora_dia(df: pd.DataFrame) -> go.Figure:
    dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    m = (df.pivot(index="dia_semana", columns="hora", values="pedidos")
           .reindex(index=dias, columns=range(24)).fillna(0))
    fig = go.Figure(go.Heatmap(
        z=m.values, x=[f"{h}h" for h in m.columns], y=m.index, colorscale=ESCALA,
        xgap=3, ygap=3, colorbar=dict(title=dict(text="Pedidos", font=dict(size=11)), thickness=8,
                                      outlinewidth=0, len=0.9, tickfont=dict(color=MUDO, size=11)),
        hovertemplate="%{y}, %{x}<br><b>%{z:,.0f} pedidos</b><extra></extra>"))
    _base(fig, 290)
    _contorno_do_pico(fig, m)
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(color=TINTA_2, size=12), ticksuffix="  ",
                     tickmode="linear", dtick=1, ticks="")
    fig.update_xaxes(dtick=2, showline=False)
    return fig


def linha_hora(df: pd.DataFrame, coluna: str, referencia: float, formato: str = "minutos") -> go.Figure:
    """Uma medida por hora do dia; anota só o pior horário (o mais alto) e a referência do período."""
    fmt = _FORMATOS[formato]
    rotulos = [fmt(v) for v in df[coluna]]
    fig = go.Figure(go.Scatter(
        x=df["hora"], y=df[coluna], mode="lines", line=dict(color=PETROLEO, width=2),
        customdata=list(zip(rotulos, df["pedidos"])),
        hovertemplate="%{x}h<br><b>%{customdata[0]}</b><br>%{customdata[1]:,.0f} pedidos<extra></extra>"))
    if len(df):
        pior = df.loc[df[coluna].idxmax()]
        fig.add_trace(go.Scatter(
            x=[pior["hora"]], y=[pior[coluna]], mode="markers+text", hoverinfo="skip",
            marker=dict(size=8, color=PETROLEO, line=dict(color="white", width=2)),
            text=[f"<b>{fmt(pior[coluna])} às {int(pior['hora'])}h</b>"],
            textposition="top center", textfont=dict(color=TINTA, size=12), cliponaxis=False))
    if referencia is not None and not pd.isna(referencia):
        fig.add_hline(y=referencia, line=dict(color=MUDO, width=1, dash="dot"),
                      annotation_text=f"período {fmt(referencia)}", annotation_position="bottom right",
                      annotation_font=dict(color=TINTA_2, size=11))
    _base(fig, 300)
    fig.update_layout(margin=dict(l=0, r=24, t=26, b=0))
    fig.update_yaxes(rangemode="tozero", ticksuffix=" min" if formato == "minutos" else "")
    fig.update_xaxes(dtick=2, tick0=0, ticksuffix="h", range=[-0.6, 23.6])
    return fig


def _e_fracao(nome: str, valores: pd.Series) -> bool:
    pista = any(p in nome.lower() for p in ("pct", "taxa", "participacao", "percent", "share", "rate", "coberto"))
    return pista and len(valores) > 0 and valores.min() >= 0 and valores.max() <= 1


def do_agente(df: pd.DataFrame, tipo: str, x: str, y: str, titulo: str = "") -> go.Figure:
    """Gráfico pedido pelo assistente a partir do resultado de uma consulta (o título vai no cartão)."""
    if x not in df.columns or y not in df.columns:
        raise ValueError(f"Colunas disponíveis: {', '.join(df.columns)}")
    d = df[[x, y]].dropna()
    fracao = _e_fracao(y, d[y])
    if tipo == "linha":
        modelo = "%{y:.1%}" if fracao else "%{y:,.2f}"
        fig = go.Figure(go.Scatter(
            x=d[x], y=d[y], mode="lines+markers", line=dict(color=PETROLEO, width=2),
            marker=dict(size=7, color=PETROLEO, line=dict(color="white", width=2)),
            hovertemplate=f"%{{x}}<br><b>{modelo}</b><extra></extra>"))
        _base(fig, 300)
        fig.update_yaxes(rangemode="tozero", tickformat=".0%" if fracao else None)
        if pd.api.types.is_datetime64_any_dtype(d[x]):
            fig.update_xaxes(tickformat="%d/%m/%y")
        elif x.lower() == "hora":
            fig.update_xaxes(ticksuffix="h", dtick=2, tick0=0, range=[-0.6, 23.6])
        return fig
    d = d.head(20)
    d[x] = d[x].astype(str)
    return barras_h(d, x, y, formato="pct" if fracao else ("moeda" if "gmv" in y.lower() else "decimal"))
