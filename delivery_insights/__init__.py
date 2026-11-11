"""Prova Real: painel de delivery com assistente que mostra a conta por trás de cada número."""

__version__ = "0.2.0"

NOME = "Prova Real"
TAGLINE = "A resposta e a conta, lado a lado."

# Único lugar que descreve a origem dos dados. A interface (pílula do cabeçalho e
# rodapé) lê daqui, por isso trocar a fonte de dados é mudar só estas linhas.
FONTE_DADOS = {
    "pilula": "Delivery Center · 2021",
    "frase": ("Dados: conjunto público “Delivery Center: Food & Goods orders in Brazil” (Kaggle), jan–abr 2021. "
              "Segundo a própria descrição, representa a operação de forma fictícia, é incompleto e foi "
              "anonimizado. Projeto de portfólio, sem vínculo com a empresa."),
    "url": "https://www.kaggle.com/datasets/nosbielcs/brazilian-delivery-center",
}
