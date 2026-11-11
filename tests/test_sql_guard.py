"""O agente de IA só pode ler. Cada linha aqui é uma tentativa de fugir a essa regra."""
import pytest

from delivery_insights import db
from delivery_insights.sql_guard import SqlBloqueado, com_limite, validar


@pytest.mark.parametrize("sql", [
    "SELECT 1",
    "select cidade, count(*) from v_pedidos group by 1;",
    "WITH a AS (SELECT 1 AS x) SELECT * FROM a",
    "SELECT * FROM v_pedidos WHERE restaurante = 'Drop & Delete Burger; update'",  # texto não é comando
    "-- comentário\nSELECT 1",
])
def test_consultas_de_leitura_passam(sql):
    assert validar(sql)


@pytest.mark.parametrize("sql", [
    "",
    "DROP TABLE pedidos",
    "DELETE FROM pedidos",
    "UPDATE pedidos SET valor_total = 0",
    "INSERT INTO pedidos SELECT * FROM pedidos",
    "SELECT 1; DROP TABLE pedidos",
    "CREATE TABLE x AS SELECT 1",
    "COPY pedidos TO 'saida.csv'",
    "SELECT * FROM read_csv('C:/segredos.csv')",
    "SELECT * FROM read_parquet('s3://bucket/x.parquet')",
    "ATTACH 'outro.db'",
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "INSTALL httpfs",
    "SELECT getenv('ANTHROPIC_API_KEY')",
    "/* disfarce */ DELETE FROM pedidos",
    "WITH a AS (SELECT 1) DELETE FROM pedidos",
])
def test_consultas_perigosas_sao_bloqueadas(sql):
    with pytest.raises(SqlBloqueado):
        validar(sql)


def test_limite_de_linhas(con):
    assert "LIMIT 200" in com_limite("SELECT * FROM pedidos")
    assert len(db.consultar_seguro(con, "SELECT * FROM pedidos")) == 200
    assert len(db.consultar_seguro(con, "SELECT * FROM pedidos LIMIT 5")) == 5


def test_banco_recusa_ficheiros_mesmo_sem_o_validador(con, tmp_path):
    """Segunda camada: a própria ligação não lê ficheiros nem aceita mudar a configuração."""
    ficheiro = tmp_path / "segredo.csv"
    ficheiro.write_text("a\n1\n")
    with pytest.raises(Exception):
        con.execute(f"SELECT * FROM read_csv('{ficheiro.as_posix()}')").fetchall()
    with pytest.raises(Exception):
        con.execute("SET enable_external_access = true")


def test_dados_continuam_intactos_depois_das_tentativas(con, tabelas):
    assert con.execute("SELECT count(*) FROM pedidos").fetchone()[0] == len(tabelas["pedidos"])
