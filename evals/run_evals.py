"""Avaliação do agente: faz perguntas com resposta conhecida e confere o que ele responde.

    python -m evals.run_evals            (precisa de ANTHROPIC_API_KEY; cada execução tem custo de API)

Para cada pergunta existe um SQL de referência escrito à mão. O agente acerta se o
valor de referência aparecer na resposta dele (com 1% de tolerância para números).
Perguntas do tipo "recusa" testam se o agente admite que não tem o dado, ou que não
pode alterar o banco, em vez de inventar.

O resultado fica em evals/resultados/ (taxa de acerto, tempo e tokens por pergunta).
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

PASTA = Path(__file__).parent
TOLERANCIA = 0.01

_NUMERO = re.compile(r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)(\s*(?:milh[õo]es|mil|mi)\b)?", re.IGNORECASE)
_RECUSA = ("nao ha dados", "nao existe", "nao existem", "nao tenho", "nao possuo", "nao e possivel",
           "nao consigo", "nao posso", "nao disponho", "nao contem", "nao inclui", "nao ha informac",
           "so de leitura", "somente leitura", "apenas leitura", "nao permite")


def numeros(texto: str) -> list[float]:
    """Extrai números escritos no padrão brasileiro: 1.234,56 · 57,06 · 4,8 mi · 980 mil."""
    achados = []
    for bruto, escala in _NUMERO.findall(texto):
        valor = float(bruto.replace(".", "").replace(",", "."))
        escala = escala.strip().lower()
        if escala == "mil":
            valor *= 1e3
        elif escala:
            valor *= 1e6
        achados.append(valor)
    return achados


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def confere(tipo: str, referencia, resposta: str) -> bool:
    if tipo == "texto":
        return _sem_acento(str(referencia)) in _sem_acento(resposta)
    if tipo == "recusa":
        return any(marca in _sem_acento(resposta) for marca in _RECUSA)
    alvo = float(referencia) * (100 if tipo == "percentual" else 1)
    achados = numeros(resposta)
    # valores abreviados ("R$ 4,80 mi") têm menos casas: aceita o arredondamento da própria escrita
    return any(abs(n - alvo) <= max(abs(alvo) * TOLERANCIA, 0.051) for n in achados)


def main() -> int:
    sys.path.insert(0, str(PASTA.parent))
    from delivery_insights import agent, db

    if not agent.tem_credenciais():
        print("Defina ANTHROPIC_API_KEY para correr a avaliação (ela chama o modelo de verdade).")
        return 2

    con = db.criar_conexao()
    casos = json.loads((PASTA / "perguntas.json").read_text(encoding="utf-8"))
    linhas = []
    for caso in casos:
        ref = None
        if caso["sql_referencia"]:
            ref = con.cursor().execute(caso["sql_referencia"]).fetchone()[0]
        try:
            r = agent.responder(caso["pergunta"], con)
            ok, texto = confere(caso["tipo"], ref, r.texto), r.texto
            extra = {"segundos": round(r.segundos, 1), "tokens_entrada": r.tokens_entrada,
                     "tokens_saida": r.tokens_saida, "consultas": len(r.passos),
                     "erros_sql": sum(1 for p in r.passos if p.erro)}
        except Exception as e:
            ok, texto, extra = False, f"ERRO: {type(e).__name__}: {e}", {}
        print(f"[{'OK ' if ok else 'FALHOU'}] {caso['id']:<22} referência={ref!s:<22} {extra.get('segundos', '-')}s")
        linhas.append({"id": caso["id"], "pergunta": caso["pergunta"], "tipo": caso["tipo"],
                       "referencia": None if ref is None else str(ref), "acertou": ok,
                       "resposta": texto, **extra})

    certos = sum(l["acertou"] for l in linhas)
    resumo = {"data": datetime.now().isoformat(timespec="seconds"), "modelo": agent.MODELO,
              "acertos": certos, "total": len(linhas), "taxa_de_acerto": round(certos / len(linhas), 3),
              "casos": linhas}
    destino = PASTA / "resultados"
    destino.mkdir(exist_ok=True)
    ficheiro = destino / f"{datetime.now():%Y-%m-%d_%H%M}.json"
    ficheiro.write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{certos}/{len(linhas)} corretas ({certos / len(linhas):.0%}). Detalhes em {ficheiro}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
