"""Agente de IA que responde a perguntas de negócio em linguagem natural (text-to-SQL).

Como funciona, em quatro passos:

1. a pergunta do usuário vai para o Claude junto com o esquema das tabelas e
   as definições das métricas (prompt de sistema);
2. o modelo decide que consulta fazer e chama a ferramenta `executar_sql`
   (tool use / function calling);
3. o SQL passa pelas proteções (só leitura, limite de linhas e de tempo), corre
   no DuckDB e o resultado volta para o modelo. Se der erro, o modelo recebe a
   mensagem de erro e corrige a consulta sozinho;
4. o ciclo repete até o modelo ter dados suficientes para responder.

Tudo o que o agente fez (SQL, tabelas, gráficos, tokens, tempo) fica registado
em `Resposta.passos`, para a interface mostrar ao usuário: nada de caixa preta.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

import pandas as pd

from . import charts, db
from .sql_guard import SqlBloqueado

MODELO = os.getenv("DELIVERY_AI_MODEL", "claude-opus-5-5")
MAX_VOLTAS = 8
LINHAS_PARA_O_MODELO = 60

PROMPT_SISTEMA = f"""Você é o analista de dados de uma operação brasileira de delivery que liga lojas \
de shoppings a marketplaces e entrega comida e produtos a partir de hubs. Quem pergunta são pessoas de \
negócio (operações, logística, comercial) que não escrevem SQL e precisam de respostas em que possam \
confiar para tomar decisões.

Os dados vêm do conjunto público "Delivery Center: Food & Goods orders in Brazil" (Kaggle), publicado pela \
própria empresa. Cobrem janeiro a abril de 2021 em quatro cidades. Segundo a descrição do conjunto, ele \
representa a operação de forma fictícia, não é completo e foi parcialmente anonimizado: os nomes de lojas, \
hubs e canais estão embaralhados. Estão num banco DuckDB com o esquema abaixo.

<esquema>
{db.ESQUEMA}
</esquema>

<definicoes_de_metricas>
- Vendas (GMV) = soma de valor dos pedidos finalizados (finalizado = TRUE).
- Ticket médio = média de valor dos pedidos finalizados.
- Taxa de cancelamento = pedidos cancelados / total de pedidos feitos.
- Tempo de entrega: use a MEDIANA de tempo_total_min (função median), não a média. Uma parte dos pedidos \
fica aberta por horas e distorce a média. Diga que é mediana quando citar o número.
- Em até 60 min = pedidos finalizados com tempo_total_min <= 60 / pedidos finalizados com tempo_total_min.
- Frete coberto = soma de taxa_entrega / soma de custo_entrega, nos pedidos finalizados com custo_entrega.
- Lojas ativas = lojas distintas com pelo menos um pedido no período.
</definicoes_de_metricas>

Como trabalhar:
- Todo número que você afirmar tem de vir de uma consulta feita nesta conversa com a ferramenta \
executar_sql. Não estime de cabeça: quem lê vai agir com base no número.
- Escreva SQL no dialeto DuckDB. O acesso é só de leitura e cada consulta devolve no máximo \
{LINHAS_PARA_O_MODELO} linhas para você, por isso agregue (GROUP BY) em vez de pedir linhas cruas.
- Se a consulta der erro, leia a mensagem, corrija e tente de novo.
- Comida e Produtos se comportam de forma muito diferente (ticket, tempo, cancelamento). Ao analisar \
tempo ou valor, separe por segmento ou diga qual está usando.
- Perguntas do tipo "por quê" pedem investigação: quebre a métrica por dimensões \
(cidade, segmento, hub, canal, hora, modal de entrega, distância) até achar o que explica a diferença.
- Ao comparar grupos, olhe o tamanho da amostra: uma loja com 5 pedidos não sustenta conclusão.
- Use criar_grafico quando uma imagem ajudar (ranking, evolução no tempo). Um gráfico por resposta basta.
- Se a pergunta for ambígua, escolha a interpretação mais útil e diga qual foi. Se os dados não \
permitem responder (por exemplo, não existem clientes, itens do pedido, avaliações, prazo prometido \
nem outros anos), diga isso claramente em vez de inventar.

Como responder:
- Em português do Brasil, direto: comece pela resposta, depois os números que a sustentam, e feche \
com uma recomendação prática quando fizer sentido.
- Valores em reais no formato R$ 1.234,56 e percentuais com uma casa decimal.
- Seja breve: a interface já mostra o SQL e as tabelas que você usou, não precisa repeti-los."""

FERRAMENTAS = [
    {
        "name": "executar_sql",
        "description": (
            "Executa uma consulta SQL de leitura (SELECT ou WITH) no banco DuckDB e devolve o "
            "resultado em CSV. Use para obter qualquer número antes de afirmá-lo."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "descricao": {"type": "string",
                              "description": "Uma frase curta, para o usuário, sobre o que esta consulta calcula."},
                "sql": {"type": "string", "description": "Uma única instrução SELECT/WITH em dialeto DuckDB."},
            },
            "required": ["descricao", "sql"],
            "additionalProperties": False,
        },
    },
    {
        "name": "criar_grafico",
        "description": (
            "Mostra ao usuário um gráfico construído a partir de uma consulta SQL. "
            "A consulta deve devolver poucas linhas já agregadas, com uma coluna para o eixo x "
            "(categoria ou data) e uma coluna numérica para o eixo y."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título do gráfico, dizendo o que ele mostra."},
                "sql": {"type": "string", "description": "SELECT que devolve os dados do gráfico."},
                "tipo": {"type": "string", "enum": ["barra", "linha"],
                         "description": "barra para rankings e comparações; linha para evolução no tempo."},
                "x": {"type": "string", "description": "Nome da coluna de categorias ou datas."},
                "y": {"type": "string", "description": "Nome da coluna numérica."},
            },
            "required": ["titulo", "sql", "tipo", "x", "y"],
            "additionalProperties": False,
        },
    },
]


@dataclass
class Passo:
    """Uma chamada de ferramenta feita pelo agente."""
    ferramenta: str
    descricao: str
    sql: str
    resultado: pd.DataFrame | None = None
    figura: object | None = None
    erro: str | None = None


@dataclass
class Resposta:
    texto: str
    passos: list[Passo] = field(default_factory=list)
    mensagens: list = field(default_factory=list)  # histórico para a próxima pergunta
    modo: str = "llm"
    modelo: str = MODELO
    tokens_entrada: int = 0
    tokens_saida: int = 0
    segundos: float = 0.0


def tem_credenciais() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))


def _executar(con, nome: str, entrada: dict) -> tuple[str, bool, Passo]:
    """Corre uma ferramenta. Devolve (texto para o modelo, é_erro, registo do passo)."""
    sql = str(entrada.get("sql", ""))
    passo = Passo(nome, str(entrada.get("descricao") or entrada.get("titulo") or ""), sql)
    try:
        if nome == "executar_sql":
            df = db.consultar_seguro(con, sql)
            passo.resultado = df
            amostra = df.head(LINHAS_PARA_O_MODELO)
            nota = "" if len(df) <= len(amostra) else (
                f"\n(mostrando {len(amostra)} de {len(df)}+ linhas; agregue para ver o conjunto todo)")
            return f"{len(df)} linha(s)\n{amostra.to_csv(index=False)}{nota}", False, passo
        if nome == "criar_grafico":
            df = db.consultar_seguro(con, sql)
            passo.resultado = df
            passo.figura = charts.do_agente(df, entrada["tipo"], entrada["x"], entrada["y"], entrada["titulo"])
            return f"Gráfico mostrado ao usuário ({len(df)} pontos).", False, passo
        raise ValueError(f"Ferramenta desconhecida: {nome}")
    except SqlBloqueado as e:
        passo.erro = f"Consulta bloqueada pelas proteções: {e}"
    except Exception as e:  # erro de SQL, coluna inexistente, tempo esgotado...
        passo.erro = f"{type(e).__name__}: {e}"
    return passo.erro, True, passo


def responder(pergunta: str, con, historico: list | None = None, cliente=None,
              max_voltas: int = MAX_VOLTAS) -> Resposta:
    """Responde a uma pergunta, deixando o modelo consultar os dados quantas vezes precisar."""
    if cliente is None:
        import anthropic
        cliente = anthropic.Anthropic()

    inicio = time.perf_counter()
    mensagens = list(historico or []) + [{"role": "user", "content": pergunta}]
    resposta = Resposta(texto="", mensagens=mensagens)
    r = None
    for _ in range(max_voltas):
        r = cliente.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            # o prompt de sistema e as ferramentas não mudam: ficam em cache entre perguntas
            system=[{"type": "text", "text": PROMPT_SISTEMA, "cache_control": {"type": "ephemeral"}}],
            tools=FERRAMENTAS,
            messages=mensagens,
            output_config={"effort": "medium"},
            # se o modelo principal recusar por política, a API tenta o modelo de reserva
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        resposta.modelo = r.model
        resposta.tokens_entrada += (r.usage.input_tokens + (r.usage.cache_read_input_tokens or 0)
                                    + (r.usage.cache_creation_input_tokens or 0))
        resposta.tokens_saida += r.usage.output_tokens
        mensagens.append({"role": "assistant", "content": r.content})
        if r.stop_reason != "tool_use":
            break
        resultados = []
        for bloco in r.content:
            if bloco.type != "tool_use":
                continue
            texto, erro, passo = _executar(con, bloco.name, bloco.input)
            resposta.passos.append(passo)
            resultados.append({"type": "tool_result", "tool_use_id": bloco.id,
                               "content": texto, "is_error": erro})
        mensagens.append({"role": "user", "content": resultados})

    texto = "\n\n".join(b.text for b in r.content if b.type == "text").strip()
    if r.stop_reason == "refusal":
        texto = texto or "O modelo recusou-se a responder a esta pergunta."
    elif r.stop_reason == "tool_use":
        texto = "Parei depois de várias consultas sem chegar a uma conclusão. Tente uma pergunta mais específica."
        mensagens.pop()  # não deixa resultados de ferramenta pendurados no histórico
        mensagens.pop()
        mensagens.append({"role": "assistant", "content": texto})
    elif r.stop_reason == "max_tokens":
        texto += "\n\n(resposta cortada por limite de tamanho)"
    resposta.texto = texto
    resposta.segundos = time.perf_counter() - inicio
    return resposta
