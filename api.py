"""API REST mínima para ligar os dados e o agente a outras ferramentas (n8n, Make, Zapier, Slack...).

Rodar com:  uvicorn api:app --reload      Documentação interativa em:  http://localhost:8000/docs
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from delivery_insights import agent, db, demo, metrics
from delivery_insights.metrics import DATA_MAX, DATA_MIN, Filtros

app = FastAPI(
    title="Delivery Insights AI",
    description="KPIs e perguntas em linguagem natural sobre dados SINTÉTICOS de um marketplace de delivery.",
    version="0.1.0",
)


@lru_cache(maxsize=1)
def conexao():
    return db.criar_conexao()


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=3, max_length=500, examples=["Qual foi o GMV por cidade?"])


class Consulta(BaseModel):
    descricao: str
    sql: str
    linhas: list[dict] | None = None
    erro: str | None = None


class RespostaAPI(BaseModel):
    resposta: str
    modo: str  # "llm" (agente de IA) ou "demo" (SQL pré-definido, sem modelo)
    modelo: str
    segundos: float
    consultas: list[Consulta]


@app.get("/saude")
def saude() -> dict:
    n = conexao().cursor().execute("SELECT count(*) FROM pedidos").fetchone()[0]
    return {"ok": True, "pedidos": n, "agente_de_ia": agent.tem_credenciais(), "dados": "sintéticos"}


@app.get("/kpis")
def kpis(
    inicio: date = DATA_MIN,
    fim: date = DATA_MAX,
    cidade: list[str] = Query(default=[]),
    culinaria: list[str] = Query(default=[]),
) -> dict:
    """Indicadores do período (GMV, pedidos, ticket médio, SLA, cancelamento...)."""
    if inicio > fim:
        raise HTTPException(422, "A data de início tem de ser anterior à data de fim.")
    k = metrics.kpis(conexao(), Filtros(inicio, fim, tuple(cidade), tuple(culinaria)))
    return {c: (None if v != v else round(float(v), 4)) for c, v in k.items()}  # NaN -> null


@app.post("/perguntar", response_model=RespostaAPI)
def perguntar(corpo: Pergunta) -> RespostaAPI:
    """Responde a uma pergunta de negócio e devolve também o SQL usado."""
    con = conexao()
    if agent.tem_credenciais():
        try:
            r = agent.responder(corpo.pergunta, con)
        except Exception as e:  # falha da API do modelo: erro claro em vez de 500 genérico
            raise HTTPException(502, f"Falha ao chamar o modelo de linguagem: {type(e).__name__}") from e
    else:
        r = demo.responder(corpo.pergunta, con)
    consultas = [
        Consulta(descricao=p.descricao, sql=p.sql, erro=p.erro,
                 linhas=None if p.resultado is None else
                 p.resultado.head(50).astype(object).where(p.resultado.head(50).notna(), None).to_dict("records"))
        for p in r.passos if p.ferramenta == "executar_sql"
    ]
    return RespostaAPI(resposta=r.texto, modo=r.modo, modelo=r.modelo,
                       segundos=round(r.segundos, 2), consultas=consultas)
