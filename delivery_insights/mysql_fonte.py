"""Ligação ao banco operacional (MySQL) da empresa.

Como funciona, em três passos:

1. **Varredura**: com um usuário que só tem permissão de leitura, a Prova Real lê o
   catálogo do banco (information_schema): que tabelas existem, quantas linhas e colunas
   têm, e quais permissões o usuário tem. Se o usuário puder escrever, avisa na tela.
2. **Leitura**: copia as 7 tabelas da operação (pedidos, entregas, lojas, hubs...).
3. **Camada analítica**: aplica a mesma limpeza da versão com CSV e monta um banco DuckDB
   em memória. Painel e assistente consultam essa cópia, nunca o MySQL diretamente.

Por que copiar em vez de consultar o MySQL a cada pergunta? Porque é o padrão em empresas:
análises pesadas não rodam no banco que atende os pedidos em tempo real. Assim o assistente
nunca pesa no sistema da operação, e o acesso dele continua só de leitura em três camadas
(usuário do MySQL, validador de SQL e DuckDB trancado).

Configuração: variável de ambiente DATABASE_URL, no formato
    mysql+pymysql://usuario:senha@host:3306/banco
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import pandas as pd

from .delivery_center import ARQUIVOS

VARIAVEL = "DATABASE_URL"
_ESCRITA = {"INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "INDEX", "GRANT OPTION",
            "ALL PRIVILEGES", "ALL", "TRUNCATE", "REFERENCES", "TRIGGER", "EVENT", "FILE", "SUPER"}


@dataclass
class Varredura:
    banco: str
    endereco: str               # host:porta/banco, sem usuário nem senha
    tabelas: pd.DataFrame       # tabela, linhas, colunas, esperada
    somente_leitura: bool
    privilegios: list[str] = field(default_factory=list)
    faltam: list[str] = field(default_factory=list)

    @property
    def pedidos(self) -> int:
        linha = self.tabelas[self.tabelas.tabela == "orders"]
        return int(linha.linhas.iloc[0]) if len(linha) else 0


def url_configurada() -> str | None:
    return os.getenv(VARIAVEL) or None


def _motor(url: str):
    from sqlalchemy import create_engine
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


def _privilegios(linhas_grant: list[str]) -> set[str]:
    """Extrai os privilégios de linhas como "GRANT SELECT, SHOW VIEW ON `banco`.* TO ..."."""
    achados = set()
    for linha in linhas_grant:
        m = re.match(r"GRANT\s+(.+?)\s+ON\s", linha, re.IGNORECASE)
        if m:
            achados |= {p.strip().upper() for p in m.group(1).split(",")}
    return achados


def varrer(url: str) -> Varredura:
    """Lê o catálogo do banco e as permissões do usuário, sem tocar nos dados."""
    from sqlalchemy import text
    motor = _motor(url)
    with motor.connect() as c:
        banco = c.execute(text("SELECT DATABASE()")).scalar()
        if not banco:
            raise ValueError("A DATABASE_URL não indica o banco (falta /nome_do_banco no fim).")
        tabelas = pd.read_sql(text("""
            SELECT t.table_name AS tabela, t.table_rows AS linhas_estimadas,
                   (SELECT count(*) FROM information_schema.columns c
                    WHERE c.table_schema = t.table_schema AND c.table_name = t.table_name) AS colunas
            FROM information_schema.tables t
            WHERE t.table_schema = :banco AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name"""), c, params={"banco": banco})
        tabelas.columns = [col.lower() for col in tabelas.columns]
        # table_rows é uma estimativa no InnoDB: para as tabelas da operação, conta de verdade
        exatas = []
        for nome in tabelas.tabela:
            exatas.append(c.execute(text(f"SELECT count(*) FROM `{nome}`")).scalar() if nome in ARQUIVOS else None)
        tabelas["linhas"] = [e if e is not None else est for e, est in zip(exatas, tabelas.linhas_estimadas)]
        grants = [r[0] for r in c.execute(text("SHOW GRANTS FOR CURRENT_USER()"))]
    privs = _privilegios(grants) - {"USAGE"}
    tabelas["esperada"] = tabelas.tabela.isin(ARQUIVOS)
    u = motor.url
    return Varredura(
        banco=banco, endereco=f"{u.host}:{u.port or 3306}/{banco}",
        tabelas=tabelas[["tabela", "linhas", "colunas", "esperada"]],
        somente_leitura=not (privs & _ESCRITA), privilegios=sorted(privs),
        faltam=[n for n in ARQUIVOS if n not in set(tabelas.tabela)])


def ler_tabelas(url: str) -> dict[str, pd.DataFrame]:
    from sqlalchemy import text
    with _motor(url).connect() as c:
        return {n: pd.read_sql(text(f"SELECT * FROM `{n}`"), c) for n in ARQUIVOS}
