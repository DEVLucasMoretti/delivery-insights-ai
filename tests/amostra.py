"""Amostra pequena, FEITA À MÃO PARA OS TESTES, no mesmo formato dos CSV do Delivery Center.

Os testes não baixam os 120 MB do Kaggle: usam estes arquivos, que têm as mesmas colunas e
os mesmos tipos de problema do conjunto verdadeiro (horários em UTC, valores absurdos,
tempos negativos, pedidos sem entrega, mais de um pagamento por pedido).
Nenhum número daqui aparece no painel nem no README.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

N = 4000


def escrever(pasta: Path, seed: int = 7) -> Path:
    rng = np.random.default_rng(seed)
    pasta.mkdir(parents=True, exist_ok=True)

    pd.DataFrame({
        "channel_id": [1, 2, 3, 4],
        "channel_name": ["FOOD PLACE", "EATS PLACE", "WHATS PLACE", "OTHER PLACE"],
        "channel_type": ["MARKETPLACE", "MARKETPLACE", "OWN CHANNEL", "OWN CHANNEL"],
    }).to_csv(pasta / "channels.csv", index=False, encoding="latin-1")

    pd.DataFrame({
        "hub_id": [1, 2, 3, 4],
        "hub_name": ["BLUE SHOPPING", "GOLDEN SHOPPING", "SQL SHOPPING", "PHP SHOPPING"],
        "hub_city": ["PORTO ALEGRE", "RIO DE JANEIRO", "SÃO PAULO", "CURITIBA"],
        "hub_state": ["RS", "RJ", "SP", "PR"],
        "hub_latitude": [-30.0, -22.9, -23.5, -25.4], "hub_longitude": [-51.2, -43.2, -46.6, -49.3],
    }).to_csv(pasta / "hubs.csv", index=False, encoding="latin-1")

    n_lojas = 40
    seg = np.where(np.arange(n_lojas) % 4 == 0, "GOOD", "FOOD")
    pd.DataFrame({
        "store_id": np.arange(1, n_lojas + 1), "hub_id": rng.integers(1, 5, n_lojas),
        "store_name": [f"LOJA {i:02d}" for i in range(1, n_lojas + 1)], "store_segment": seg,
        "store_plan_price": 0.0, "store_latitude": -23.5, "store_longitude": -46.6,
    }).to_csv(pasta / "stores.csv", index=False, encoding="latin-1")

    n_ent = 60
    pd.DataFrame({
        "driver_id": np.arange(1, n_ent + 1),
        "driver_modal": np.where(np.arange(n_ent) % 3 == 0, "BIKER", "MOTOBOY"),
        "driver_type": np.where(np.arange(n_ent) % 4 == 0, "LOGISTIC OPERATOR", "FREELANCE"),
    }).to_csv(pasta / "drivers.csv", index=False, encoding="latin-1")

    ids = np.arange(1000, 1000 + N)
    loja = rng.integers(1, n_lojas + 1, N)
    produto = seg[loja - 1] == "GOOD"
    # horário em UTC: almoço (15h) e jantar (22h) de Brasília
    criado = (pd.Timestamp("2021-01-01") + pd.to_timedelta(rng.integers(0, 120, N), unit="D")
              + pd.to_timedelta(rng.choice([15, 16, 22, 23], N) * 60 + rng.integers(0, 60, N), unit="m"))
    cancelado = rng.random(N) < np.where(produto, 0.12, 0.03)
    preparo = rng.gamma(4, np.where(produto, 9, 4), N)
    expedicao = rng.gamma(2, 3.5, N)
    transito = rng.gamma(4, np.where(produto, 6, 4), N)
    ciclo = preparo + expedicao + transito
    valor = np.round(rng.lognormal(np.where(produto, 5.2, 4.2), 0.5, N), 2)
    valor[0], valor[1] = 1_788_306.11, 0.0          # registros absurdos, como no conjunto verdadeiro
    transito[2], ciclo[3] = -4.1, 90_000.0           # tempo negativo e pedido "aberto" por semanas
    custo = np.round(rng.gamma(4, 1.8, N), 2)
    custo_txt = pd.Series(custo).where(rng.random(N) > 0.02)

    def momento(minutos):
        return (criado + pd.to_timedelta(minutos, unit="m")).strftime("%m/%d/%Y %I:%M:%S %p")

    pd.DataFrame({
        "order_id": ids, "store_id": loja, "channel_id": rng.choice([1, 2, 3, 4], N, p=[0.7, 0.15, 0.1, 0.05]),
        "payment_order_id": ids, "delivery_order_id": ids,
        "order_status": np.where(cancelado, "CANCELED", "FINISHED"),
        "order_amount": valor, "order_delivery_fee": np.round(rng.choice([0, 5.99, 6.9, 11.9], N), 2),
        "order_delivery_cost": custo_txt,
        "order_created_hour": criado.hour, "order_created_minute": criado.minute,
        "order_created_day": criado.day, "order_created_month": criado.month, "order_created_year": criado.year,
        "order_moment_created": criado.strftime("%m/%d/%Y %I:%M:%S %p"),
        "order_moment_accepted": momento(1), "order_moment_ready": momento(preparo),
        "order_moment_collected": momento(preparo + 2), "order_moment_in_expedition": momento(preparo + 3),
        "order_moment_delivering": momento(preparo + expedicao), "order_moment_delivered": "",
        "order_moment_finished": momento(np.clip(ciclo, 0, 5000)),
        "order_metric_collected_time": 2.0, "order_metric_paused_time": 1.0,
        "order_metric_production_time": np.round(preparo, 2), "order_metric_walking_time": 1.0,
        "order_metric_expediton_speed_time": np.round(expedicao, 2),
        "order_metric_transit_time": np.round(transito, 2), "order_metric_cycle_time": np.round(ciclo, 2),
    }).to_csv(pasta / "orders.csv", index=False, encoding="latin-1")

    com_entrega = ids[10:]                             # alguns pedidos não têm entrega registrada
    entregas = pd.DataFrame({
        "delivery_order_id": np.concatenate([com_entrega, com_entrega[:50]]),   # 50 com segunda tentativa
    })
    entregas.insert(0, "delivery_id", np.arange(1, len(entregas) + 1))
    entregas["driver_id"] = pd.Series(rng.integers(1, n_ent + 1, len(entregas))).where(
        rng.random(len(entregas)) > 0.04).astype("float")
    entregas["delivery_distance_meters"] = np.round(rng.gamma(2.2, 1100, len(entregas)))
    entregas.loc[0, "delivery_distance_meters"] = 7_251_291.0                   # distância impossível
    entregas["delivery_status"] = rng.choice(["DELIVERED", "CANCELLED", "DELIVERING"], len(entregas),
                                             p=[0.97, 0.025, 0.005])
    entregas.to_csv(pasta / "deliveries.csv", index=False, encoding="latin-1")

    pag = pd.DataFrame({"payment_order_id": np.concatenate([ids, ids[:300]])})   # 300 com dois pagamentos
    pag.insert(0, "payment_id", np.arange(1, len(pag) + 1))
    pag["payment_amount"] = np.round(rng.lognormal(4.2, 0.5, len(pag)), 2)
    pag["payment_fee"] = np.round(pag["payment_amount"] * 0.02, 2)
    pag["payment_method"] = rng.choice(["ONLINE", "VOUCHER", "DEBIT", "CREDIT_STORE", "MEAL_BENEFIT", "MONEY",
                                        "STORE_DIRECT_PAYMENT", "PAYMENT_LINK"], len(pag),
                                       p=[0.7, 0.1, 0.05, 0.04, 0.04, 0.02, 0.03, 0.02])
    pag["payment_status"] = rng.choice(["PAID", "CHARGEBACK", "AWAITING"], len(pag), p=[0.985, 0.01, 0.005])
    pag.to_csv(pasta / "payments.csv", index=False, encoding="latin-1")
    return pasta
