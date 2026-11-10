"""Guardrails para o SQL escrito pelo agente de IA.

O modelo de linguagem nunca recebe acesso de escrita. Antes de qualquer consulta
chegar ao banco, ela passa por aqui:

1. tem de ser UMA única instrução;
2. tem de começar por SELECT ou WITH;
3. não pode conter comandos que alteram dados, leem ficheiros ou mudam configuração;
4. o resultado é sempre limitado a um número máximo de linhas.

A ligação DuckDB também é aberta com acesso externo desligado (ver db.py), por
isso estas regras são a segunda camada de defesa, não a única.
"""

from __future__ import annotations

import re

MAX_LINHAS = 200

_PROIBIDO = re.compile(
    r"\b(insert|update|delete|drop|create|alter|truncate|replace|merge|attach|detach|copy|"
    r"export|import|install|load|pragma|call|set|reset|vacuum|checkpoint|grant|revoke|"
    r"read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|read_text|read_blob|"
    r"glob|getenv|duckdb_secrets|sniff_csv)\b",
    re.IGNORECASE,
)


class SqlBloqueado(ValueError):
    """A consulta foi recusada pelos guardrails."""


def _sem_comentarios_e_textos(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)  # o conteúdo de textos não conta como comando


def validar(sql: str) -> str:
    """Devolve o SQL limpo se for uma consulta de leitura segura; senão lança SqlBloqueado."""
    if not sql or not sql.strip():
        raise SqlBloqueado("Consulta vazia.")
    limpo = sql.strip().rstrip(";").strip()
    esqueleto = _sem_comentarios_e_textos(limpo)
    if ";" in esqueleto:
        raise SqlBloqueado("Só é permitida uma instrução por consulta.")
    if not re.match(r"^\s*(select|with)\b", esqueleto, re.IGNORECASE):
        raise SqlBloqueado("Só são permitidas consultas de leitura (SELECT ou WITH).")
    achado = _PROIBIDO.search(esqueleto)
    if achado:
        raise SqlBloqueado(f"Comando não permitido: {achado.group(1).upper()}.")
    return limpo


def com_limite(sql: str, max_linhas: int = MAX_LINHAS) -> str:
    """Valida e embrulha a consulta para nunca devolver mais que `max_linhas`."""
    return f"SELECT * FROM (\n{validar(sql)}\n) AS consulta LIMIT {int(max_linhas)}"
