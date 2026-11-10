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
    return (f"**{a.cidade}** lidera com {brl(a.gmv)} de GMV ({pct(a.participacao)} do total), "
            f"seguida de {df.iloc[1].cidade} ({brl(df.iloc[1].gmv)}). "
            f"A menor praça é {z.cidade}, com {brl(z.gmv)}. "
            f"O ticket médio vai de {brl(df.ticket_medio.min(), 2)} a {brl(df.ticket_medio.max(), 2)}.")


def _faixa(df):
    linhas = [f"- **{r.faixa_etaria} anos:** {r.culinaria} ({pct(r.participacao)} dos pedidos da faixa)"
              for r in df[df.posicao == 1].itertuples()]
    return "A culinária preferida muda com a idade:\n" + "\n".join(linhas)


def _sla(df):
    pior = df.sort_values("pct_no_prazo").head(3)
    horas = ", ".join(f"{int(r.hora)}h ({pct(r.pct_no_prazo)})" for r in pior.itertuples())
    return (f"Os piores horários para o prazo são {horas}. "
            f"No melhor horário, {pct(df.pct_no_prazo.max())} dos pedidos chegam no prazo. "
            "Os atrasos concentram-se nos picos de almoço e jantar: é onde reforçar a oferta de "
            "entregadores ou alargar o prazo prometido traz mais retorno.")


def _cancel(df):
    r = df.iloc[0]
    return (f"Entre restaurantes com pelo menos 150 pedidos, o maior cancelamento é de "
            f"**{r.restaurante}** ({r.culinaria}, {r.cidade}): {pct(r.taxa_cancelamento)} em "
            f"{numero(r.pedidos)} pedidos, com entrega média de {numero(r.tempo_medio_min)} min. "
            "A tabela lista os 10 primeiros.")


def _ticket(df):
    a, z = df.iloc[0], df.iloc[-1]
    var = z.ticket_medio / a.ticket_medio - 1
    return (f"O ticket médio foi de {brl(a.ticket_medio, 2)} em janeiro para {brl(z.ticket_medio, 2)} "
            f"em dezembro ({'+' if var >= 0 else ''}{pct(var)}). No ano, variou entre "
            f"{brl(df.ticket_medio.min(), 2)} e {brl(df.ticket_medio.max(), 2)}.")


def _clube(df):
    s = df[df.assinante_clube].iloc[0]
    n = df[~df.assinante_clube].iloc[0]
    return (f"Sim. Assinantes do clube fazem em média **{numero(s.pedidos_por_cliente, 1)} pedidos** no ano, "
            f"contra {numero(n.pedidos_por_cliente, 1)} dos não assinantes, com ticket médio de "
            f"{brl(s.ticket_medio, 2)} contra {brl(n.ticket_medio, 2)}. "
            f"São {pct(s.clientes / (s.clientes + n.clientes))} dos clientes ativos.")


def _atraso(df):
    a, z = df.iloc[0], df.iloc[-1]
    return (f"Sim, e muito. Pedidos entregues no prazo recebem nota média **{numero(a.avaliacao_media, 2)}**; "
            f"com mais de 20 minutos de atraso a nota cai para **{numero(z.avaliacao_media, 2)}**.")


def _pagamento(df):
    a = df.iloc[0]
    return (f"No almoço de dias úteis (11h às 14h), **{a.forma_pagamento}** lidera com "
            f"{pct(a.participacao)} dos pedidos, seguido de {df.iloc[1].forma_pagamento} "
            f"({pct(df.iloc[1].participacao)}).")


EXEMPLOS = [
    Exemplo("Qual foi o GMV por cidade?", "GMV, participação e ticket médio por cidade", """
        SELECT cidade, sum(valor_total) AS gmv,
               sum(valor_total) / sum(sum(valor_total)) OVER () AS participacao,
               avg(valor_total) AS ticket_medio
        FROM v_pedidos WHERE entregue GROUP BY 1 ORDER BY gmv DESC""",
            _gmv_cidade, ("barra", "cidade", "gmv", "GMV por cidade (R$)")),
    Exemplo("Que culinária cada faixa etária prefere?", "Três culinárias mais pedidas em cada faixa etária", """
        SELECT faixa_etaria, culinaria, count(*) AS pedidos,
               count(*) / sum(count(*)) OVER (PARTITION BY faixa_etaria) AS participacao,
               row_number() OVER (PARTITION BY faixa_etaria ORDER BY count(*) DESC) AS posicao
        FROM v_pedidos GROUP BY 1, 2
        QUALIFY posicao <= 3 ORDER BY 1, posicao""", _faixa),
    Exemplo("Em que horários o prazo de entrega falha mais?", "Percentual de pedidos no prazo por hora do dia", """
        SELECT hora, count(*) AS pedidos, avg(CAST(no_prazo AS INT)) AS pct_no_prazo,
               avg(tempo_entrega_min) AS tempo_medio_min
        FROM v_pedidos WHERE entregue GROUP BY 1 HAVING count(*) >= 500 ORDER BY 1""",
            _sla, ("linha", "hora", "pct_no_prazo", "Pedidos entregues no prazo, por hora do dia")),
    Exemplo("Quais restaurantes têm mais cancelamentos?", "Taxa de cancelamento dos restaurantes com 150+ pedidos", """
        SELECT restaurante, culinaria, cidade, count(*) AS pedidos,
               avg(CAST(NOT entregue AS INT)) AS taxa_cancelamento,
               avg(tempo_entrega_min) AS tempo_medio_min
        FROM v_pedidos GROUP BY 1, 2, 3 HAVING count(*) >= 150
        ORDER BY taxa_cancelamento DESC LIMIT 10""", _cancel),
    Exemplo("Como evoluiu o ticket médio ao longo do ano?", "Ticket médio por mês", """
        SELECT mes, avg(valor_total) AS ticket_medio, count(*) AS pedidos
        FROM v_pedidos WHERE entregue GROUP BY 1 ORDER BY 1""",
            _ticket, ("linha", "mes", "ticket_medio", "Ticket médio por mês (R$)")),
    Exemplo("Assinantes do clube pedem mais?", "Frequência e ticket de assinantes e não assinantes", """
        SELECT assinante_clube, count(DISTINCT cliente_id) AS clientes,
               count(*) / count(DISTINCT cliente_id) AS pedidos_por_cliente,
               avg(valor_total) AS ticket_medio
        FROM v_pedidos WHERE entregue GROUP BY 1 ORDER BY 1 DESC""", _clube),
    Exemplo("O atraso na entrega afeta a avaliação?", "Nota média por faixa de atraso", """
        SELECT CASE WHEN atraso <= 0 THEN '1. No prazo' WHEN atraso <= 10 THEN '2. Até 10 min'
                    WHEN atraso <= 20 THEN '3. 11 a 20 min' ELSE '4. Mais de 20 min' END AS faixa_atraso,
               avg(avaliacao) AS avaliacao_media, count(*) AS avaliacoes
        FROM (SELECT avaliacao, tempo_entrega_min - tempo_prometido_min AS atraso
              FROM v_pedidos WHERE avaliacao IS NOT NULL)
        GROUP BY 1 ORDER BY 1""",
            _atraso, ("barra", "faixa_atraso", "avaliacao_media", "Nota média por atraso na entrega")),
    Exemplo("Qual forma de pagamento domina o almoço?", "Formas de pagamento no almoço de dias úteis", """
        SELECT forma_pagamento, count(*) AS pedidos,
               count(*) / sum(count(*)) OVER () AS participacao
        FROM v_pedidos WHERE hora BETWEEN 11 AND 14 AND dia_semana_num <= 5
        GROUP BY 1 ORDER BY pedidos DESC""", _pagamento),
]

_IGNORAR = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "que", "qual", "quais", "por",
            "e", "foi", "tem", "mais", "na", "no", "ao", "como", "cada", "para", "um", "uma", "se"}


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
            "No modo demonstração (sem chave de API) só consigo responder às perguntas do catálogo:\n\n"
            f"{lista}\n\nPara perguntas livres, configure `ANTHROPIC_API_KEY` (veja o README)."))
    df = db.consultar_seguro(con, ex.sql)
    passos = [Passo("executar_sql", ex.descricao, ex.sql.strip(), resultado=df)]
    if ex.grafico:
        tipo, x, y, titulo = ex.grafico
        passos.append(Passo("criar_grafico", titulo, ex.sql.strip(), resultado=df,
                            figura=charts.do_agente(df, tipo, x, y, titulo)))
    return Resposta(texto=ex.resumo(df), passos=passos, modo="demo", modelo="sem modelo")
