"""Gerador reprodutível de dados SINTÉTICOS de um marketplace de delivery de comida.

Nenhum dado aqui é real: clientes, restaurantes e pedidos são simulados com uma
seed fixa, para que qualquer pessoa obtenha exatamente os mesmos números.

Os dados não são ruído puro. O gerador embute padrões de negócio plausíveis que
o dashboard e o agente conseguem depois "descobrir":

- picos de almoço e jantar, que variam por tipo de culinária;
- fins de semana mais fortes que dias úteis;
- preferência de culinária diferente por faixa etária;
- atrasos concentrados nos horários de pico e em cidades com mais trânsito;
- atrasos que derrubam a avaliação e aumentam o cancelamento;
- clientes que deixam de pedir ao longo do tempo (churn).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

INICIO = pd.Timestamp("2025-01-01")
FIM = pd.Timestamp("2025-12-31")

# cidade, uf, peso (share de clientes), fator de preço, fator de trânsito
CIDADES = [
    ("São Paulo", "SP", 0.27, 1.12, 1.25),
    ("Rio de Janeiro", "RJ", 0.16, 1.08, 1.20),
    ("Belo Horizonte", "MG", 0.10, 0.98, 1.05),
    ("Brasília", "DF", 0.08, 1.10, 0.95),
    ("Curitiba", "PR", 0.08, 1.00, 0.95),
    ("Porto Alegre", "RS", 0.07, 1.00, 1.00),
    ("Salvador", "BA", 0.07, 0.92, 1.10),
    ("Recife", "PE", 0.06, 0.90, 1.15),
    ("Fortaleza", "CE", 0.06, 0.88, 1.00),
    ("Campinas", "SP", 0.05, 1.02, 0.90),
]

FAIXAS = ["18-24", "25-34", "35-44", "45-54", "55+"]
PESO_FAIXAS = [0.22, 0.34, 0.22, 0.13, 0.09]

# Horários de referência dos picos de consumo
PICOS = {"manha": 9.0, "almoco": 12.5, "tarde": 16.0, "jantar": 20.0, "noite": 23.3}


@dataclass(frozen=True)
class Culinaria:
    nome: str
    peso: float  # share de restaurantes
    ticket: float  # valor médio dos itens (R$)
    preparo: float  # minutos de preparo
    horarios: dict  # peso de cada pico de consumo
    afinidade: tuple  # multiplicador por faixa etária (18-24 ... 55+)
    prefixos: tuple


CULINARIAS = [
    Culinaria("Lanches", 0.20, 42, 12, {"almoco": 2, "jantar": 5, "noite": 3},
              (1.5, 1.2, 0.9, 0.7, 0.5), ("Burger", "Lanchonete", "Hamburgueria")),
    Culinaria("Pizza", 0.14, 68, 20, {"jantar": 8, "noite": 2},
              (1.1, 1.1, 1.1, 0.9, 0.8), ("Pizzaria", "Forneria")),
    Culinaria("Brasileira", 0.14, 39, 15, {"almoco": 8, "jantar": 2},
              (0.6, 0.9, 1.2, 1.4, 1.5), ("Restaurante", "Cantinho", "Sabor")),
    Culinaria("Marmita", 0.10, 26, 10, {"almoco": 10, "jantar": 1},
              (0.7, 1.0, 1.2, 1.3, 1.2), ("Marmitaria", "Marmitex")),
    Culinaria("Japonesa", 0.09, 92, 22, {"almoco": 2, "jantar": 8},
              (0.9, 1.4, 1.2, 0.8, 0.5), ("Sushi", "Temakeria", "Izakaya")),
    Culinaria("Açaí", 0.08, 29, 6, {"tarde": 7, "jantar": 2, "noite": 1},
              (1.7, 1.1, 0.8, 0.5, 0.3), ("Açaí", "Açaiteria")),
    Culinaria("Saudável", 0.07, 46, 12, {"almoco": 7, "jantar": 3},
              (0.8, 1.4, 1.2, 0.9, 0.7), ("Salad", "Natural", "Fit")),
    Culinaria("Doces & Bolos", 0.07, 34, 8, {"manha": 1, "tarde": 6, "jantar": 3},
              (1.1, 1.0, 1.0, 1.0, 1.1), ("Doceria", "Confeitaria")),
    Culinaria("Italiana", 0.06, 74, 20, {"almoco": 3, "jantar": 7},
              (0.6, 1.0, 1.3, 1.3, 1.2), ("Cantina", "Trattoria")),
    Culinaria("Árabe", 0.05, 48, 14, {"almoco": 4, "jantar": 6},
              (0.8, 1.1, 1.2, 1.1, 0.9), ("Esfiharia", "Empório Árabe")),
]

_PALAVRAS = [
    "da Praça", "do Bairro", "Bela Vista", "do Chef", "Dona Rosa", "Sabor & Arte",
    "da Esquina", "Central", "do Vale", "Ouro Verde", "da Villa", "Imperial",
    "Tropical", "da Serra", "Prime", "do Porto", "Santa Clara", "Boa Mesa",
    "da Família", "Raízes", "Jardim", "do Mercado", "Sol Nascente", "Estação",
    "da Lagoa", "Nativa", "Capital", "do Parque", "Flor de Sal", "Divino",
]
_BAIRROS = [
    "Centro", "Jardins", "Vila Nova", "Boa Vista", "Santa Luzia", "Alto da Serra", "Savassi",
    "Batel", "Moinhos", "Barra", "Aldeota", "Asa Sul", "Cambuí", "Pinheiros", "Tijuca",
    "Graças", "Pituba", "Lourdes", "Água Verde", "Botafogo",
]


def _perfil_horario(pesos: dict) -> np.ndarray:
    """Probabilidade de um pedido cair em cada hora do dia (24 posições)."""
    horas = np.arange(24) + 0.5
    perfil = np.full(24, 0.02)  # pequeno volume fora dos picos
    for pico, peso in pesos.items():
        centro = PICOS[pico]
        dist = np.minimum(np.abs(horas - centro), 24 - np.abs(horas - centro))
        perfil += peso * np.exp(-0.5 * (dist / 1.2) ** 2)
    perfil[2:7] *= 0.05  # madrugada quase parada
    return perfil / perfil.sum()


def gerar(
    seed: int = 42,
    n_clientes: int = 12_000,
    n_restaurantes: int = 600,
    n_candidatos: int = 120_000,
) -> dict[str, pd.DataFrame]:
    """Gera as três tabelas (restaurantes, clientes, pedidos) de forma determinística."""
    rng = np.random.default_rng(seed)
    cid_nome = np.array([c[0] for c in CIDADES])
    cid_uf = np.array([c[1] for c in CIDADES])
    cid_peso = np.array([c[2] for c in CIDADES])
    cid_preco = np.array([c[3] for c in CIDADES])
    cid_transito = np.array([c[4] for c in CIDADES])
    cul_peso = np.array([c.peso for c in CULINARIAS])
    cul_peso = cul_peso / cul_peso.sum()

    # ---------------- Restaurantes ----------------
    r_cid = rng.choice(len(CIDADES), n_restaurantes, p=cid_peso)
    r_cul = rng.choice(len(CULINARIAS), n_restaurantes, p=cul_peso)
    r_nivel = rng.choice([1, 2, 3], n_restaurantes, p=[0.45, 0.40, 0.15])
    r_pop = rng.lognormal(0.0, 0.9, n_restaurantes)  # poucos restaurantes concentram volume
    nomes, vistos = [], set()
    for i in range(n_restaurantes):
        cul = CULINARIAS[r_cul[i]]
        nome = f"{rng.choice(cul.prefixos)} {rng.choice(_PALAVRAS)}"
        if nome in vistos:  # nome repetido vira uma "unidade" de bairro
            nome = f"{nome} ({rng.choice(_BAIRROS)})"
        if nome in vistos:
            nome = f"{nome[:-1]} {i + 1})"
        vistos.add(nome)
        nomes.append(nome)
    restaurantes = pd.DataFrame({
        "restaurante_id": np.arange(1, n_restaurantes + 1),
        "nome": nomes,
        "culinaria": [CULINARIAS[i].nome for i in r_cul],
        "cidade": cid_nome[r_cid],
        "uf": cid_uf[r_cid],
        "nivel_preco": r_nivel,
        "taxa_comissao": np.round(rng.uniform(0.12, 0.23, n_restaurantes), 3),
        "data_cadastro": (pd.Timestamp("2023-01-01")
                          + pd.to_timedelta(rng.integers(0, 720, n_restaurantes), unit="D")).date,
    })

    # ---------------- Clientes ----------------
    c_cid = rng.choice(len(CIDADES), n_clientes, p=cid_peso)
    c_faixa = rng.choice(len(FAIXAS), n_clientes, p=PESO_FAIXAS)
    janela = (pd.Timestamp("2025-12-15") - pd.Timestamp("2023-10-01")).days
    # expoente < 1 -> a base de clientes cresce ao longo do tempo
    c_cadastro = pd.Timestamp("2023-10-01") + pd.to_timedelta(
        (janela * rng.random(n_clientes) ** 0.8).astype(int), unit="D")
    c_clube = rng.random(n_clientes) < 0.18
    c_propensao = rng.gamma(1.2, 1.0, n_clientes) * np.where(c_clube, 1.6, 1.0)
    # tempo de vida: depois disso o cliente deixa de pedir (churn); clube retém mais
    c_vida = 20 + rng.exponential(np.where(c_clube, 520, 300))
    clientes = pd.DataFrame({
        "cliente_id": np.arange(1, n_clientes + 1),
        "cidade": cid_nome[c_cid],
        "uf": cid_uf[c_cid],
        "faixa_etaria": np.array(FAIXAS)[c_faixa],
        "data_cadastro": c_cadastro.date,
        "canal_aquisicao": rng.choice(
            ["Orgânico", "Indicação", "Redes sociais", "Busca paga", "Parcerias"],
            n_clientes, p=[0.36, 0.20, 0.22, 0.14, 0.08]),
        "assinante_clube": c_clube,
    })

    # ---------------- Pedidos ----------------
    ini = np.maximum(c_cadastro.values, INICIO.to_datetime64())
    fim = np.minimum((c_cadastro + pd.to_timedelta(c_vida, unit="D")).values,
                     (FIM + pd.Timedelta(hours=23)).to_datetime64())
    dias_ativos = np.clip((fim - ini) / np.timedelta64(1, "D"), 0, None)
    p_cliente = c_propensao * dias_ativos
    cli = rng.choice(n_clientes, n_candidatos, p=p_cliente / p_cliente.sum())
    dia = (pd.DatetimeIndex(ini[cli])
           + pd.to_timedelta(rng.random(n_candidatos) * dias_ativos[cli], unit="D")).normalize()

    # aceitação por dia da semana e mês (fim de semana, julho e dezembro mais fortes)
    peso_dow = np.array([0.85, 0.82, 0.86, 0.92, 1.15, 1.30, 1.22])
    peso_mes = np.array([0.95, 0.93, 0.96, 0.97, 0.98, 1.0, 1.06, 1.0, 0.99, 1.0, 1.02, 1.08])
    aceita = rng.random(n_candidatos) < (
        peso_dow[dia.day_of_week] / peso_dow.max() * peso_mes[dia.month - 1] / peso_mes.max())
    cli, dia = cli[aceita], dia[aceita]
    n = len(cli)

    # restaurante: dentro da cidade do cliente, ponderado por popularidade x afinidade etária
    afin = np.array([CULINARIAS[c].afinidade for c in r_cul])  # (restaurantes, faixas)
    rest = np.empty(n, dtype=int)
    for ci in range(len(CIDADES)):
        cand = np.flatnonzero(r_cid == ci)
        for fi in range(len(FAIXAS)):
            mask = (c_cid[cli] == ci) & (c_faixa[cli] == fi)
            if mask.any():
                p = r_pop[cand] * afin[cand, fi]
                rest[mask] = rng.choice(cand, mask.sum(), p=p / p.sum())
    cul_idx = r_cul[rest]
    cid_idx = r_cid[rest]

    hora = np.empty(n, dtype=int)
    for k, cul in enumerate(CULINARIAS):
        mask = cul_idx == k
        hora[mask] = rng.choice(24, mask.sum(), p=_perfil_horario(cul.horarios))
    data_hora = dia + pd.to_timedelta(hora * 60 + rng.integers(0, 60, n), unit="m")
    dow = dia.day_of_week.values

    ticket = np.array([c.ticket for c in CULINARIAS])[cul_idx]
    preparo = np.array([c.preparo for c in CULINARIAS])[cul_idx]
    nivel = np.array([0.85, 1.0, 1.35])[r_nivel[rest] - 1]
    valor_itens = np.clip(ticket * nivel * cid_preco[cid_idx] * rng.lognormal(0, 0.35, n), 12, None)

    distancia = np.clip(rng.gamma(2.2, 1.5, n), 0.3, 12)
    clube = c_clube[cli]
    taxa = np.clip(3.99 + 1.1 * distancia + rng.normal(0, 1, n), 0, None)
    taxa[(clube & (valor_itens >= 30)) | (rng.random(n) < 0.12)] = 0.0  # frete grátis

    dias_de_casa = (dia.values - c_cadastro.values[cli]) / np.timedelta64(1, "D")
    cupom = rng.random(n) < np.where(dias_de_casa <= 30, 0.34, 0.14)  # cupom de boas-vindas
    desconto = np.where(
        cupom,
        np.minimum(valor_itens * rng.choice([0.10, 0.15, 0.20, 0.30], n),
                   rng.choice([10.0, 15.0, 20.0], n)),
        0.0)

    # tempo prometido (mostrado ao cliente) vs tempo real de entrega
    transito = cid_transito[cid_idx]
    prometido = np.ceil((preparo + 8 + 3.6 * distancia * np.sqrt(transito) + 9) / 5) * 5
    pico = np.isin(hora, [12, 13, 19, 20, 21])
    real = (preparo * rng.lognormal(0, 0.25, n) + 8
            + 3.6 * distancia * transito * rng.lognormal(0, 0.20, n)
            + pico * rng.gamma(2.0, 3.5, n)
            + np.isin(dow, [4, 5, 6]) * rng.gamma(1.5, 1.5, n))
    atraso = np.clip(real - prometido, 0, None)

    pagamento = np.where(
        (hora >= 11) & (hora <= 14) & (dow < 5),  # vale-refeição forte no almoço de dia útil
        rng.choice(["Pix", "Crédito", "Débito", "Vale-refeição", "Dinheiro"], n,
                   p=[0.28, 0.30, 0.08, 0.30, 0.04]),
        rng.choice(["Pix", "Crédito", "Débito", "Vale-refeição", "Dinheiro"], n,
                   p=[0.36, 0.41, 0.09, 0.07, 0.07]))

    p_cancel = 0.025 + 0.0035 * np.clip(atraso, 0, 60) + 0.012 * (pagamento == "Dinheiro")
    cancelado = rng.random(n) < p_cancel
    nota = np.clip(np.round(4.75 - 0.07 * np.clip(atraso, 0, 40) + rng.normal(0, 0.6, n)), 1, 5)
    avaliou = (~cancelado) & (rng.random(n) < 0.55)

    valor_itens = np.round(valor_itens, 2)
    taxa = np.round(taxa, 2)
    desconto = np.round(desconto, 2)
    comissao = restaurantes["taxa_comissao"].values[rest]
    pedidos = pd.DataFrame({
        "cliente_id": cli + 1,
        "restaurante_id": rest + 1,
        "data_hora": data_hora,
        "status": np.where(cancelado, "Cancelado", "Entregue"),
        "valor_itens": valor_itens,
        "taxa_entrega": taxa,
        "desconto": desconto,
        "valor_total": np.round(valor_itens + taxa - desconto, 2),
        "receita_plataforma": np.where(cancelado, 0.0, np.round(valor_itens * comissao + taxa * 0.3, 2)),
        "cupom_usado": cupom,
        "forma_pagamento": pagamento,
        "plataforma": rng.choice(["Android", "iOS", "Web"], n, p=[0.58, 0.34, 0.08]),
        "distancia_km": np.round(distancia, 1),
        "tempo_prometido_min": prometido.astype(int),
        "tempo_entrega_min": pd.array(np.where(cancelado, -1, np.round(real)).astype(int), dtype="Int64"),
        "avaliacao": pd.array(np.where(avaliou, nota, -1).astype(int), dtype="Int64"),
    })
    pedidos.loc[cancelado, "tempo_entrega_min"] = pd.NA
    pedidos.loc[~avaliou, "avaliacao"] = pd.NA
    pedidos = pedidos.sort_values("data_hora", kind="stable").reset_index(drop=True)
    pedidos.insert(0, "pedido_id", np.arange(1, n + 1))

    return {"restaurantes": restaurantes, "clientes": clientes, "pedidos": pedidos}


if __name__ == "__main__":  # python -m delivery_insights.generate_data
    from pathlib import Path

    destino = Path("data")
    destino.mkdir(exist_ok=True)
    for nome, df in gerar().items():
        df.to_csv(destino / f"{nome}.csv", index=False)
        print(f"{nome}: {len(df):,} linhas -> {destino / (nome + '.csv')}")
