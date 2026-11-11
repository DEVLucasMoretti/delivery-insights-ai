"""O corretor da avaliação tem de ser confiável, e as referências têm de ser SQL válido."""
import json
from pathlib import Path

from evals.run_evals import confere, numeros

CASOS = json.loads((Path(__file__).parents[1] / "evals" / "perguntas.json").read_text(encoding="utf-8"))


def test_leitura_de_numeros_brasileiros():
    assert numeros("O GMV foi de R$ 4.801.234,56 em 86.956 pedidos") == [4801234.56, 86956]
    assert numeros("cerca de R$ 4,80 mi e 980,5 mil") == [4.8e6, 980500]
    assert numeros("ticket de R$ 57,05 e taxa de 3,2%") == [57.05, 3.2]


def test_corretor():
    assert confere("numero", 4801234.56, "O GMV total foi de R$ 4.801.234,56.")
    assert confere("numero", 4801234.56, "Aproximadamente R$ 4,80 mi.")
    assert not confere("numero", 4801234.56, "O GMV foi de R$ 3.900.000,00.")
    assert confere("percentual", 0.0318, "A taxa de cancelamento é de 3,2%.")
    assert not confere("percentual", 0.0318, "A taxa de cancelamento é de 13,2%.")
    assert confere("texto", "São Paulo", "A líder é sao paulo, com folga.")
    assert confere("recusa", None, "Não há dados de salários de entregadores nesta base.")
    assert not confere("recusa", None, "O salário médio é de R$ 2.500,00.")


def test_sql_de_referencia_executa_e_devolve_um_valor(con):
    assert len(CASOS) >= 15 and len({c["id"] for c in CASOS}) == len(CASOS)
    for caso in CASOS:
        if caso["sql_referencia"]:
            linhas = con.cursor().execute(caso["sql_referencia"]).fetchall()
            assert len(linhas) == 1 and linhas[0][0] is not None, caso["id"]
