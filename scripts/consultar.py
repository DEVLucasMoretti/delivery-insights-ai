"""Consulta os dados da Prova Real pela linha de comando, com as mesmas proteções do assistente.

É a ferramenta que a Skill do Claude usa (ver .claude/skills/prova-real/SKILL.md), mas também
serve para qualquer pessoa:

    python scripts/consultar.py esquema                      # tabelas, colunas e definições
    python scripts/consultar.py kpis                         # indicadores do período inteiro
    python scripts/consultar.py kpis --cidade Curitiba --segmento Comida --de 2021-04-01 --ate 2021-04-30
    python scripts/consultar.py sql "SELECT cidade, count(*) AS pedidos FROM v_pedidos GROUP BY 1"

Só aceita leitura: o SQL passa pelo mesmo validador do assistente (só SELECT/WITH, até 200
linhas, tempo limite). Com DATABASE_URL definida, lê do MySQL; sem ela, dos arquivos CSV.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

try:
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
except ImportError:
    pass

from delivery_insights import FONTE_DADOS, db, metrics  # noqa: E402
from delivery_insights.sql_guard import SqlBloqueado  # noqa: E402

from delivery_insights.charts import brl, numero, pct  # noqa: E402

# chave -> (rótulo, formatação)
ROTULOS = {
    "pedidos": ("Pedidos", numero),
    "gmv": ("Vendas (GMV)", lambda v: brl(v, 2)),
    "ticket_medio": ("Ticket médio", lambda v: brl(v, 2)),
    "lojas_ativas": ("Lojas ativas", numero),
    "taxa_cancelamento": ("Cancelamento", pct),
    "tempo_mediano_min": ("Tempo total (mediana)", lambda v: f"{numero(v, 1)} min"),
    "pct_ate_60": ("Pedidos em até 60 min", pct),
    "frete_coberto": ("Taxa de entrega / custo da entrega", pct),
    "distancia_mediana_km": ("Distância mediana", lambda v: f"{numero(v, 2)} km"),
}


def tabela_markdown(df, max_linhas: int = 60) -> str:
    """Tabela em Markdown, que o Claude e o terminal leem bem."""
    if df.empty:
        return "(nenhuma linha)"
    d = df.head(max_linhas).astype(object).where(df.head(max_linhas).notna(), "")
    linhas = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    linhas += ["| " + " | ".join(str(v) for v in r) + " |" for r in d.itertuples(index=False)]
    if len(df) > max_linhas:
        linhas.append(f"\n({len(df)} linhas no total; mostrando {max_linhas}. Agregue com GROUP BY.)")
    return "\n".join(linhas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Consulta os dados da Prova Real (somente leitura).")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("esquema", help="mostra tabelas, colunas e definições das métricas")
    k = sub.add_parser("kpis", help="indicadores do recorte")
    k.add_argument("--cidade", action="append", default=[])
    k.add_argument("--segmento", action="append", default=[], help="Comida ou Produtos")
    k.add_argument("--de", type=date.fromisoformat, default=metrics.DATA_MIN, help="AAAA-MM-DD")
    k.add_argument("--ate", type=date.fromisoformat, default=metrics.DATA_MAX, help="AAAA-MM-DD")
    s = sub.add_parser("sql", help="executa uma consulta SELECT em dialeto DuckDB")
    s.add_argument("consulta")
    a = p.parse_args(argv)

    if a.comando == "esquema":
        print(db.ESQUEMA)
        print("\nDefinições das métricas:\n" + metrics.__doc__.split("Definições", 1)[1].split("\n", 1)[1])
        print(f"Origem dos dados: {FONTE_DADOS['frase']}")
        return 0

    con, origem = db.abrir()
    print(f"Fonte: {origem.descricao}\n", file=sys.stderr)
    if a.comando == "kpis":
        f = metrics.Filtros(a.de, a.ate, tuple(a.cidade), tuple(a.segmento))
        for chave, valor in metrics.kpis(con, f).items():
            rotulo, formatar = ROTULOS.get(chave, (chave, str))
            print(f"- {rotulo}: {formatar(valor)}")
        return 0
    try:
        print(tabela_markdown(db.consultar_seguro(con, a.consulta)))
    except SqlBloqueado as e:
        print(f"Consulta bloqueada (somente leitura): {e}", file=sys.stderr)
        return 2
    except Exception as e:  # erro de SQL: devolve a mensagem para quem chamou corrigir
        print(f"Erro na consulta: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
