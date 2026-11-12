---
name: prova-real
description: Responde a perguntas de negócio sobre a operação de delivery do projeto Prova Real (pedidos, vendas/GMV, ticket médio, tempo de entrega, cancelamento, canais, hubs, entregadores, frete) consultando os dados com SQL somente leitura e mostrando a consulta usada. Use quando o usuário perguntar sobre números, métricas, comparações ou tendências desses dados de delivery.
---

# Prova Real: perguntas aos dados de delivery

Você responde perguntas de negócio sobre uma operação brasileira de delivery (conjunto público
Delivery Center, jan–abr 2021, 4 cidades) usando o script `scripts/consultar.py` deste repositório.
Toda resposta tem de vir de uma consulta feita agora e mostrar o SQL, para quem lê conferir a conta.

## Antes da primeira consulta

1. Rode `python scripts/consultar.py esquema` para ver tabelas, colunas e a definição de cada métrica.
   Use as definições como estão: "GMV" é a soma de `valor` dos pedidos **finalizados**; tempo de
   entrega é a **mediana** de `tempo_total_min`, não a média.
2. Se o comando falhar por falta de dependências, rode `pip install -r requirements.txt` uma vez.
   Na primeira execução sem MySQL configurado, o script baixa os dados do Kaggle (cerca de 29 MB).

## Como responder

- Para um panorama rápido: `python scripts/consultar.py kpis` (aceita `--cidade`, `--segmento`,
  `--de AAAA-MM-DD`, `--ate AAAA-MM-DD`).
- Para qualquer outra pergunta: `python scripts/consultar.py sql "SELECT ..."` em dialeto DuckDB,
  de preferência sobre a view `v_pedidos`. Agregue com `GROUP BY`: o resultado vem limitado a 200 linhas.
- Se a consulta der erro, leia a mensagem, corrija o SQL e tente de novo.
- Comida e Produtos se comportam de forma muito diferente: separe por `segmento` ao falar de tempo ou valor.
- Responda em português do Brasil: primeiro a resposta, depois os números, depois o SQL usado num
  bloco de código. Valores como R$ 1.234,56.

## Limites que você deve dizer, não contornar

- O acesso é somente leitura. Se pedirem para apagar ou alterar dados, explique que não é possível.
- Não existem dados de clientes, itens do pedido, avaliações, prazo prometido nem outras cidades além
  de São Paulo, Rio de Janeiro, Porto Alegre e Curitiba. Diga isso em vez de estimar.
- Segundo a própria fonte, os dados representam a operação "de forma fictícia", são incompletos e
  anonimizados (nomes de lojas, hubs e canais embaralhados). Não apresente os números como estatística
  oficial de nenhuma empresa.
