-- Usuário que a Prova Real usa para ler o banco: só SELECT, nada de escrita.
-- Roda uma vez, quando o container do MySQL é criado.
CREATE USER IF NOT EXISTS 'prova_leitura'@'%' IDENTIFIED BY 'leitura_local_dev';
GRANT SELECT, SHOW VIEW ON delivery_center.* TO 'prova_leitura'@'%';
FLUSH PRIVILEGES;
