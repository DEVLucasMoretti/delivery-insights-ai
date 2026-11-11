"""Modo demonstração: funciona SEM chave de API e SEM modelo de linguagem.

Serve para quem abre o projeto pela primeira vez conseguir ver a experiência do
assistente. Aqui não há IA: cada pergunta do catálogo tem um SQL escrito à mão e
um texto montado a partir do resultado. A interface avisa sempre que está neste modo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from . import charts, db
from .agent import Passo, Resposta
from .charts import brl, numero, pct


@dataclass(frozen=True)
class Exemplo:
    pergunta: str
    descricao: str
    sql: str
    resumo: Callable[[pd.DataFrame], str]
    grafico: tuple | None = None  # (tipo, x, y, título)


def _gmv_cidade(df):
    a, z = df.iloc[0], df.iloc[-1]
    return (f"**{a.cidade}** lidera com {brl(a.gmv)} em vendas ({pct(a.participacao)} do total), "
            f"seguida de {df.iloc[1].cidade} ({brl(df.iloc[1].gmv)}). "
            f"A menor praça é {z.cidade}, com {brl(z.gmv)}. "
            f"O ticket médio vai de {brl(df.ticket_medio.min(), 2)} a {brl(df.ticket_medio.max(), 2)}.")


def _segmento(df):
    d = df.set_index("segmento")
    c, p = d.loc["Comida"], d.loc["Produtos"]
    return (f"**Produtos** demoram bem mais: {numero(p.tempo_mediano_min)} min de mediana, contra "
            f"{numero(c.tempo_mediano_min)} min em comida. Só {pct(p.pct_ate_60)} dos pedidos de produtos "
            f"terminam em até 60 minutos (comida: {pct(c.pct_ate_60)}), e o cancelamento é de "
            f"{pct(p.taxa_cancelamento)} contra {pct(c.taxa_cancelamento)}. "
            f"Comida é {pct(c.pedidos / (c.pedidos + p.pedidos))} dos pedidos.")


def _horario(df):
    top = df.sort_values("pedidos", ascending=False).head(3)
    horas = ", ".join(f"{int(r.hora)}h ({numero(r.pedidos)})" for r in top.itertuples())
    almoco = df[df.hora.between(11, 14)].pedidos.sum() / df.pedidos.sum()
    jantar = df[df.hora.between(18, 21)].pedidos.sum() / df.pedidos.sum()
    return (f"Os horários mais cheios são {horas}. O almoço (11h às 14h) concentra {pct(almoco)} dos pedidos "
            f"e o jantar (18h às 21h), {pct(jantar)}. Horário de Brasília.")


def _canal(df):
    d = df.set_index("tipo_canal")
    m, p = d.loc["Marketplace"], d.loc["Canal próprio"]
    return (f"O **canal próprio** tem ticket médio de {brl(p.ticket_medio, 2)}, contra {brl(m.ticket_medio, 2)} "
            f"nos marketplaces. Mas os marketplaces trazem {pct(m.pedidos / (m.pedidos + p.pedidos))} dos pedidos "
            f"e {pct(m.gmv / (m.gmv + p.gmv))} das vendas.")


def _modal(df):
    d = df.set_index("modal_entrega")
    b, m = d.loc["Bicicleta"], d.loc["Moto"]
    return (f"A bicicleta faz percursos mais curtos (mediana de {numero(b.distancia_mediana_km, 1)} km, contra "
            f"{numero(m.distancia_mediana_km, 1)} km da moto) e o trânsito mediano é de "
            f"{numero(b.transito_mediano_min, 1)} min, contra {numero(m.transito_mediano_min, 1)} min. "
            f"A moto leva {pct(m.pedidos / (m.pedidos + b.pedidos))} das entregas. "
            "A comparação não é de velocidade: cada modal recebe distâncias diferentes.")


def _frete(df):
    a, z = df.iloc[0], df.iloc[-1]
    return (f"Em **{a.cidade}** a taxa cobrada cobre só {pct(a.frete_coberto)} do custo da entrega "
            f"(taxa média de {brl(a.taxa_media, 2)} para um custo de {brl(a.custo_medio, 2)}). "
            f"No outro extremo, {z.cidade} cobre {pct(z.frete_coberto)}.")


def _distancia(df):
    a, z = df.iloc[0], df.iloc[-1]
    return (f"Sim. Até 1 km, o trânsito mediano é de {numero(a.transito_mediano_min, 1)} min; acima de 5 km, "
            f"sobe para {numero(z.transito_mediano_min, 1)} min. "
            f"{pct(df.pedidos.iloc[:2].sum() / df.pedidos.sum())} das entregas ficam em até 2 km.")


def _hub_cancel(df):
    r = df.iloc[0]
    return (f"Entre hubs com pelo menos 2.000 pedidos, o maior cancelamento é o de **{r.hub}** "
            f"({r.cidade}): {pct(r.taxa_cancelamento)} em {numero(r.pedidos)} pedidos. "
            "Os nomes dos hubs foram embaralhados na origem dos dados.")


EXEMPLOS = [
    Exemplo("Qual foi o GMV por cidade?", "Vendas, participação e ticket médio por cidade", """
        SELECT cidade, sum(valor) AS gmv,
               sum(valor) / sum(sum(valor)) OVER () AS participacao,
               avg(valor) AS ticket_medio
        FROM v_pedidos WHERE finalizado GROUP BY 1 ORDER BY gmv DESC""",
            _gmv_cidade, ("barra", "cidade", "gmv", "Vendas (GMV) por cidade")),
    Exemplo("Comida ou produtos: o que demora mais?", "Tempo, pontualidade e cancelamento por segmento", """
        SELECT segmento, count(*) AS pedidos,
               median(tempo_total_min) FILTER (WHERE finalizado) AS tempo_mediano_min,
               avg(CAST(tempo_total_min <= 60 AS INT)) FILTER (WHERE finalizado) AS pct_ate_60,
               avg(CAST(NOT finalizado AS INT)) AS taxa_cancelamento
        FROM v_pedidos GROUP BY 1 ORDER BY 1""", _segmento),
    Exemplo("Em que horário chegam mais pedidos?", "Pedidos por hora do dia", """
        SELECT hora, count(*) AS pedidos FROM v_pedidos GROUP BY 1 ORDER BY 1""",
            _horario, ("linha", "hora", "pedidos", "Pedidos por hora do dia")),
    Exemplo("Marketplace ou canal próprio: onde o ticket é maior?", "Pedidos, vendas e ticket por tipo de canal", """
        SELECT tipo_canal, count(*) AS pedidos, sum(valor) AS gmv, avg(valor) AS ticket_medio
        FROM v_pedidos WHERE finalizado GROUP BY 1 ORDER BY gmv DESC""", _canal),
    Exemplo("Moto ou bicicleta: quem faz as entregas?", "Entregas, distância e trânsito por modal", """
        SELECT modal_entrega, count(*) AS pedidos,
               median(distancia_km) AS distancia_mediana_km,
               median(tempo_transito_min) AS transito_mediano_min
        FROM v_pedidos WHERE finalizado AND modal_entrega IS NOT NULL
        GROUP BY 1 ORDER BY pedidos DESC""", _modal),
    Exemplo("Onde a taxa de entrega não cobre o custo?", "Taxa cobrada sobre custo da entrega, por cidade", """
        SELECT cidade, sum(taxa_entrega) / sum(custo_entrega) AS frete_coberto,
               avg(taxa_entrega) AS taxa_media, avg(custo_entrega) AS custo_medio
        FROM v_pedidos WHERE finalizado AND custo_entrega IS NOT NULL
        GROUP BY 1 ORDER BY frete_coberto""",
            _frete, ("barra", "cidade", "frete_coberto", "Quanto do custo da entrega a taxa cobre")),
    Exemplo("A distância aumenta o tempo de trânsito?", "Trânsito mediano por faixa de distância", """
        SELECT CASE WHEN distancia_km <= 1 THEN '1. Até 1 km' WHEN distancia_km <= 2 THEN '2. 1 a 2 km'
                    WHEN distancia_km <= 3 THEN '3. 2 a 3 km' WHEN distancia_km <= 5 THEN '4. 3 a 5 km'
                    ELSE '5. Mais de 5 km' END AS faixa_distancia,
               count(*) AS pedidos, median(tempo_transito_min) AS transito_mediano_min
        FROM v_pedidos WHERE finalizado AND distancia_km IS NOT NULL AND tempo_transito_min IS NOT NULL
        GROUP BY 1 ORDER BY 1""", _distancia),
    Exemplo("Quais hubs têm mais cancelamentos?", "Taxa de cancelamento dos hubs com 2.000+ pedidos", """
        SELECT hub, cidade, count(*) AS pedidos, avg(CAST(NOT finalizado AS INT)) AS taxa_cancelamento
        FROM v_pedidos GROUP BY 1, 2 HAVING count(*) >= 2000
        ORDER BY taxa_cancelamento DESC LIMIT 10""", _hub_cancel),
]

_IGNORAR = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "que", "qual", "quais", "por",
            "e", "foi", "tem", "mais", "na", "no", "ao", "como", "cada", "para", "um", "uma", "se", "ou",
            "onde", "quem", "nao"}


def _palavras(texto: str) -> set[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return {p[:6] for p in re.findall(r"[a-z]+", sem_acento) if p not in _IGNORAR}


def encontrar(pergunta: str) -> Exemplo | None:
    """Acha o exemplo do catálogo mais parecido com a pergunta (por palavras em comum)."""
    alvo = _palavras(pergunta)
    melhor, pontos = None, 0.0
    for ex in EXEMPLOS:
        chave = _palavras(ex.pergunta)
        p = len(alvo & chave) / max(len(chave), 1)
        if p > pontos:
            melhor, pontos = ex, p
    return melhor if pontos >= 0.5 else None


def responder(pergunta: str, con) -> Resposta:
    ex = encontrar(pergunta)
    if ex is None:
        lista = "\n".join(f"- {e.pergunta}" for e in EXEMPLOS)
        return Resposta(modo="demo", modelo="sem modelo", texto=(
            "Essa não está no catálogo da demonstração. As que respondo aqui:\n\n"
            f"{lista}\n\nPara perguntas livres, defina `ANTHROPIC_API_KEY` e reinicie."))
    df = db.consultar_seguro(con, ex.sql)
    passos = [Passo("executar_sql", ex.descricao, ex.sql.strip(), resultado=df)]
    if df.empty:
        return Resposta(texto="A consulta não devolveu nenhuma linha para estes dados.", passos=passos,
                        modo="demo", modelo="sem modelo")
    if ex.grafico:
        tipo, x, y, titulo = ex.grafico
        passos.append(Passo("criar_grafico", titulo, ex.sql.strip(), resultado=df,
                            figura=charts.do_agente(df, tipo, x, y, titulo)))
    return Resposta(texto=ex.resumo(df), passos=passos, modo="demo", modelo="sem modelo")
