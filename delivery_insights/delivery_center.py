"""Carrega o conjunto público "Delivery Center: Food & Goods orders in Brazil".

Origem: https://www.kaggle.com/datasets/nosbielcs/brazilian-delivery-center
Publicado pela equipe de dados da Delivery Center (plataforma brasileira que integrava
lojistas de shoppings a marketplaces). Cobre pedidos e entregas de janeiro a abril de 2021.

O que a própria descrição do conjunto diz, e que este projeto repete sem enfeitar:
- o modelo "representa, de forma fictícia", dados processados pela empresa no período;
- não tem a operação completa, e parte das informações foi anonimizada por causa da LGPD
  (nomes de lojas, hubs e canais estão embaralhados).

Licença no Kaggle: "Data files © Original Authors". Por isso os CSV NÃO ficam neste
repositório: são baixados da fonte na primeira execução e guardados em data/ (fora do git).

Limpeza aplicada aqui (tudo o mais fica como veio):
1. Horários: os picos de pedido caem às 15h e às 22h no arquivo, o que só faz sentido se
   estiverem em UTC. Convertemos para o horário de Brasília (UTC-3). É uma inferência nossa.
2. Valor do pedido: 11 pedidos acima de R$ 10.000 (um deles de R$ 1,79 milhão) são tratados
   como erro de registro e ficam com valor nulo. O pedido continua contando como pedido.
3. Tempos: valores negativos ou acima de 24 horas ficam nulos.
4. Rótulos traduzidos para português (FINISHED -> Finalizado, MOTOBOY -> Moto, etc.).
"""

from __future__ import annotations

import io
import os
import urllib.request
import zipfile
from pathlib import Path

import duckdb

URL = "https://www.kaggle.com/api/v1/datasets/download/nosbielcs/brazilian-delivery-center"
PAGINA = "https://www.kaggle.com/datasets/nosbielcs/brazilian-delivery-center"
ARQUIVOS = ("channels", "deliveries", "drivers", "hubs", "orders", "payments", "stores")
PASTA_PADRAO = Path(os.getenv("DELIVERY_CENTER_DIR", Path(__file__).resolve().parents[1] / "data" / "delivery_center"))

VALOR_MAXIMO = 10_000  # R$; acima disto tratamos como erro de registro
FUSO = "INTERVAL 3 HOUR"  # UTC -> horário de Brasília


def arquivos_presentes(pasta: Path = PASTA_PADRAO) -> bool:
    return all((Path(pasta) / f"{n}.csv").exists() for n in ARQUIVOS)


def baixar(pasta: Path = PASTA_PADRAO) -> Path:
    """Baixa o zip do Kaggle (cerca de 29 MB) e extrai só os 7 CSV esperados."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    pedido = urllib.request.Request(URL, headers={"User-Agent": "python-urllib"})
    with urllib.request.urlopen(pedido, timeout=300) as resposta:
        conteudo = resposta.read()
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in ARQUIVOS:  # extrai por nome fixo: nada no zip escolhe onde é gravado
            (pasta / f"{nome}.csv").write_bytes(z.read(f"{nome}.csv"))
    return pasta


def _tempo(coluna: str) -> str:
    return f"CASE WHEN {coluna} BETWEEN 0 AND 1440 THEN round({coluna}, 1) END"


def _sql_tabelas(csv) -> dict[str, str]:
    return {
        "hubs": f"""
            SELECT hub_id, hub_name AS nome,
                   CASE hub_city WHEN 'SÃO PAULO' THEN 'São Paulo' WHEN 'RIO DE JANEIRO' THEN 'Rio de Janeiro'
                                 WHEN 'PORTO ALEGRE' THEN 'Porto Alegre' WHEN 'CURITIBA' THEN 'Curitiba'
                                 ELSE hub_city END AS cidade,
                   hub_state AS uf
            FROM {csv('hubs')}""",
        "lojas": f"""
            SELECT store_id AS loja_id, hub_id, store_name AS nome,
                   CASE store_segment WHEN 'FOOD' THEN 'Comida' ELSE 'Produtos' END AS segmento
            FROM {csv('stores')}""",
        "canais": f"""
            SELECT channel_id AS canal_id, channel_name AS nome,
                   CASE channel_type WHEN 'MARKETPLACE' THEN 'Marketplace' ELSE 'Canal próprio' END AS tipo
            FROM {csv('channels')}""",
        "entregadores": f"""
            SELECT driver_id AS entregador_id,
                   CASE driver_modal WHEN 'MOTOBOY' THEN 'Moto' ELSE 'Bicicleta' END AS modal,
                   CASE driver_type WHEN 'FREELANCE' THEN 'Freelancer' ELSE 'Operador logístico' END AS tipo
            FROM {csv('drivers')}""",
        "entregas": f"""
            SELECT delivery_id AS entrega_id, delivery_order_id AS pedido_id,
                   CAST(driver_id AS BIGINT) AS entregador_id,
                   CASE WHEN delivery_distance_meters BETWEEN 0 AND 50000
                        THEN round(delivery_distance_meters / 1000.0, 2) END AS distancia_km,
                   CASE delivery_status WHEN 'DELIVERED' THEN 'Entregue' WHEN 'CANCELLED' THEN 'Cancelada'
                                        ELSE 'Em rota' END AS status
            FROM {csv('deliveries')}""",
        "pagamentos": f"""
            SELECT payment_id AS pagamento_id, payment_order_id AS pedido_id,
                   payment_amount AS valor, payment_fee AS taxa,
                   CASE WHEN payment_method = 'ONLINE' THEN 'Online'
                        WHEN payment_method LIKE 'VOUCHER%' THEN 'Voucher'
                        WHEN payment_method LIKE 'DEBIT%' THEN 'Débito'
                        WHEN payment_method LIKE '%CREDIT%' THEN 'Crédito'
                        WHEN payment_method = 'MEAL_BENEFIT' THEN 'Vale-refeição'
                        WHEN payment_method = 'MONEY' THEN 'Dinheiro'
                        WHEN payment_method = 'STORE_DIRECT_PAYMENT' THEN 'Direto na loja'
                        ELSE 'Outros' END AS metodo,
                   CASE payment_status WHEN 'PAID' THEN 'Pago' WHEN 'CHARGEBACK' THEN 'Estornado'
                                       ELSE 'Aguardando' END AS status
            FROM {csv('payments')}""",
        "pedidos": f"""
            SELECT order_id AS pedido_id, store_id AS loja_id, channel_id AS canal_id,
                   order_moment_created - {FUSO} AS data_hora,
                   CASE order_status WHEN 'FINISHED' THEN 'Finalizado' ELSE 'Cancelado' END AS status,
                   CASE WHEN order_amount > 0 AND order_amount <= {VALOR_MAXIMO} THEN order_amount END AS valor,
                   order_delivery_fee AS taxa_entrega,
                   order_delivery_cost AS custo_entrega,
                   {_tempo('order_metric_production_time')} AS tempo_preparo_min,
                   {_tempo('order_metric_expediton_speed_time')} AS tempo_expedicao_min,
                   {_tempo('order_metric_transit_time')} AS tempo_transito_min,
                   {_tempo('order_metric_cycle_time')} AS tempo_total_min
            FROM {csv('orders')}""",
    }


VIEW_PEDIDOS = """
CREATE VIEW v_pedidos AS
WITH entrega AS (  -- um pedido pode ter mais de uma tentativa de entrega: fica a de maior id
    SELECT pedido_id, arg_max(entregador_id, entrega_id) AS entregador_id,
           arg_max(distancia_km, entrega_id) AS distancia_km, count(*) AS tentativas_entrega
    FROM entregas GROUP BY 1)
SELECT
    p.*,
    CAST(p.data_hora AS DATE)                      AS data_pedido,
    CAST(date_trunc('month', p.data_hora) AS DATE) AS mes,
    hour(p.data_hora)                              AS hora,
    isodow(p.data_hora)                            AS dia_semana_num,
    CASE isodow(p.data_hora)
        WHEN 1 THEN 'Seg' WHEN 2 THEN 'Ter' WHEN 3 THEN 'Qua' WHEN 4 THEN 'Qui'
        WHEN 5 THEN 'Sex' WHEN 6 THEN 'Sáb' ELSE 'Dom' END AS dia_semana,
    p.status = 'Finalizado'                        AS finalizado,
    CASE WHEN p.valor IS NULL THEN NULL
         WHEN p.valor < 50 THEN 'Até R$ 50'
         WHEN p.valor < 100 THEN 'R$ 50 a 100'
         WHEN p.valor < 200 THEN 'R$ 100 a 200'
         ELSE 'Acima de R$ 200' END                AS faixa_valor,
    l.nome AS loja, l.segmento,
    h.nome AS hub, h.cidade, h.uf,
    c.nome AS canal, c.tipo AS tipo_canal,
    e.distancia_km, e.tentativas_entrega,
    d.modal AS modal_entrega, d.tipo AS tipo_entregador
FROM pedidos p
JOIN lojas l USING (loja_id)
JOIN hubs h USING (hub_id)
JOIN canais c USING (canal_id)
LEFT JOIN entrega e USING (pedido_id)
LEFT JOIN entregadores d USING (entregador_id)
"""

# Descrição entregue ao assistente (e mostrada no README).
ESQUEMA = """
Tabela pedidos (1 linha por pedido, janeiro a abril de 2021, horário de Brasília)
  pedido_id, loja_id, canal_id
  data_hora TIMESTAMP
  status VARCHAR               -- 'Finalizado' ou 'Cancelado'
  valor DOUBLE                 -- R$ do pedido; NULL em registros inválidos
  taxa_entrega DOUBLE          -- R$ cobrados do cliente pela entrega
  custo_entrega DOUBLE         -- R$ que a entrega custou à operação; pode ser NULL
  tempo_preparo_min DOUBLE     -- do pedido criado até ficar pronto na loja
  tempo_expedicao_min DOUBLE   -- de pronto até sair para entrega
  tempo_transito_min DOUBLE    -- de sair para entrega até concluir
  tempo_total_min DOUBLE       -- do pedido criado até concluir (ciclo completo)

Tabela lojas: loja_id, hub_id, nome, segmento ('Comida' ou 'Produtos')
Tabela hubs: hub_id, nome, cidade, uf    -- centro de distribuição, em geral um shopping
Tabela canais: canal_id, nome, tipo ('Marketplace' ou 'Canal próprio')
Tabela entregas: entrega_id, pedido_id, entregador_id, distancia_km, status ('Entregue','Cancelada','Em rota')
Tabela entregadores: entregador_id, modal ('Moto' ou 'Bicicleta'), tipo ('Freelancer' ou 'Operador logístico')
Tabela pagamentos: pagamento_id, pedido_id, valor, taxa, metodo, status ('Pago','Estornado','Aguardando')
  metodo: 'Online','Voucher','Débito','Crédito','Vale-refeição','Dinheiro','Direto na loja','Outros'
  Um pedido pode ter mais de um pagamento.

View v_pedidos (PREFIRA ESTA): pedidos já unidos a loja, hub, canal e entrega, com colunas extra
  data_pedido DATE, mes DATE (1º dia do mês), hora INTEGER (0-23),
  dia_semana VARCHAR ('Seg'..'Dom'), dia_semana_num INTEGER (1=Seg .. 7=Dom),
  finalizado BOOLEAN,
  faixa_valor VARCHAR ('Até R$ 50','R$ 50 a 100','R$ 100 a 200','Acima de R$ 200'; NULL se valor inválido),
  loja, segmento, hub, cidade, uf, canal, tipo_canal,
  distancia_km, tentativas_entrega, modal_entrega, tipo_entregador

Valores de cidade: 'São Paulo','Rio de Janeiro','Porto Alegre','Curitiba'
Os nomes de lojas, hubs e canais foram embaralhados na origem (anonimização); não correspondem a marcas reais.
Não existem dados de clientes, itens do pedido, avaliações nem prazo prometido ao cliente.
""".strip()


def _montar(con: duckdb.DuckDBPyConnection, origem) -> duckdb.DuckDBPyConnection:
    """Aplica a mesma limpeza a qualquer origem e tranca o banco. `origem(nome)` devolve o SQL da tabela crua."""
    for nome, sql in _sql_tabelas(origem).items():
        con.execute(f"CREATE TABLE {nome} AS {sql}")
    con.execute(VIEW_PEDIDOS)
    con.execute("SET enable_external_access = false")
    con.execute("SET lock_configuration = true")
    return con


def ler_csv_brutos(pasta: Path) -> dict:
    """Lê os 7 CSV com os tipos que o DuckDB deteta (datas viram TIMESTAMP). Usado para carregar o MySQL."""
    base = Path(pasta).resolve().as_posix().replace("'", "''")
    con = duckdb.connect(":memory:")
    return {n: con.execute(f"SELECT * FROM read_csv('{base}/{n}.csv', encoding='latin-1', sample_size=-1)").df()
            for n in ARQUIVOS}


def criar_conexao(pasta: Path | None = None, baixar_se_faltar: bool = True) -> duckdb.DuckDBPyConnection:
    """Cria o banco analítico em memória a partir dos CSV."""
    pasta = Path(pasta or PASTA_PADRAO)
    if not arquivos_presentes(pasta):
        if not baixar_se_faltar:
            raise FileNotFoundError(f"CSV do Delivery Center não encontrados em {pasta}. Baixe de {PAGINA}")
        baixar(pasta)
    base = pasta.resolve().as_posix().replace("'", "''")
    return _montar(duckdb.connect(":memory:"),
                   lambda nome: f"read_csv('{base}/{nome}.csv', encoding='latin-1', sample_size=-1)")


def criar_conexao_de_tabelas(brutas: dict) -> duckdb.DuckDBPyConnection:
    """Cria o banco analítico a partir de tabelas já lidas de outro sistema (ex.: o MySQL da operação)."""
    faltam = [n for n in ARQUIVOS if n not in brutas]
    if faltam:
        raise ValueError(f"Faltam as tabelas: {', '.join(faltam)}")
    con = duckdb.connect(":memory:")
    for nome in ARQUIVOS:
        con.register(f"bruto_{nome}", brutas[nome])
    _montar(con, lambda nome: f"bruto_{nome}")
    for nome in ARQUIVOS:  # os DataFrames saem da conexão: só ficam as tabelas limpas
        con.unregister(f"bruto_{nome}")
    return con
