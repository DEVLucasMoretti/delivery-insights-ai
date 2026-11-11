"""Carrega o conjunto Delivery Center num MySQL, fazendo o papel do banco operacional de uma empresa.

    docker compose up -d                  (sobe o MySQL local, ver docker-compose.yml)
    python scripts/carregar_mysql.py      (cria e preenche as 7 tabelas)

Usa um usuário COM permissão de escrita (MYSQL_CARGA_URL), porque precisa criar tabelas.
A aplicação depois lê com outro usuário, que só pode fazer SELECT (DATABASE_URL).
As tabelas mantêm os nomes e colunas originais do conjunto, como estariam no sistema de origem.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import create_engine, text  # noqa: E402

from delivery_insights import delivery_center as dc  # noqa: E402

CHAVES = {"channels": "channel_id", "hubs": "hub_id", "stores": "store_id", "drivers": "driver_id",
          "orders": "order_id", "deliveries": "delivery_id", "payments": "payment_id"}
INDICES = {"orders": ["store_id", "channel_id"], "deliveries": ["delivery_order_id", "driver_id"],
           "payments": ["payment_order_id"], "stores": ["hub_id"]}


def carregar(url: str, pasta: Path | None = None) -> dict[str, int]:
    pasta = Path(pasta or dc.PASTA_PADRAO)
    if not dc.arquivos_presentes(pasta):
        print(f"Baixando o conjunto para {pasta} ...")
        dc.baixar(pasta)
    motor = create_engine(url)
    contagem = {}
    for nome, df in dc.ler_csv_brutos(pasta).items():
        inicio = time.perf_counter()
        # blocos de ~40 mil valores: grandes o bastante para ser rápido, pequenos para caber num pacote do MySQL
        bloco = max(200, 40_000 // max(len(df.columns), 1))
        df.to_sql(nome, motor, if_exists="replace", index=False, chunksize=bloco, method="multi")
        with motor.begin() as c:
            c.execute(text(f"ALTER TABLE `{nome}` ADD PRIMARY KEY (`{CHAVES[nome]}`)"))
            for coluna in INDICES.get(nome, []):
                c.execute(text(f"CREATE INDEX ix_{nome}_{coluna} ON `{nome}` (`{coluna}`)"))
        contagem[nome] = len(df)
        print(f"  {nome:<11} {len(df):>9,} linhas  ({time.perf_counter() - inicio:.0f}s)")
    return contagem


if __name__ == "__main__":
    url = os.getenv("MYSQL_CARGA_URL")
    if not url:
        sys.exit("Defina MYSQL_CARGA_URL (veja .env.example).")
    carregar(url)
    print("Pronto. Agora defina DATABASE_URL com o usuário de leitura e rode: streamlit run app.py")
