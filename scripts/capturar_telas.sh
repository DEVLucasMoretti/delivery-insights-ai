#!/usr/bin/env bash
# Gera as imagens do README a partir da aplicação a correr (Chrome em modo headless).
#   1) streamlit run app.py --server.port 8518 --server.headless true
#   2) abra http://localhost:8518 uma vez no navegador (para os dados ficarem em cache)
#   3) bash scripts/capturar_telas.sh
set -uo pipefail

BASE="${BASE:-http://localhost:8518}"
CHROME="${CHROME:-/c/Program Files/Google/Chrome/Application/chrome.exe}"
DESTINO="$(cd "$(dirname "$0")/.." && pwd -W 2>/dev/null || pwd)/docs/img"
mkdir -p "$DESTINO"

captura() {  # nome  altura  caminho
  local tentativa tamanho
  for tentativa in 1 2 3 4 5 6; do
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars --window-size="1440,$2" \
      --virtual-time-budget=30000 --user-data-dir="${TMPDIR:-${TEMP:-/tmp}}/chrome-capturas" \
      --screenshot="$DESTINO/$1.png" "$BASE/$3" >/dev/null 2>&1
    tamanho=$(wc -c < "$DESTINO/$1.png")
    # uma página que ainda estava a carregar sai quase em branco (ficheiro pequeno): tenta de novo
    if [ "$tamanho" -gt 60000 ]; then echo "ok     $1.png ($tamanho bytes)"; return 0; fi
  done
  echo "FALHOU $1.png"; return 1
}

captura painel      1700 ""
captura consumo     1560 "?aba=consumo"
captura clientes    1500 "?aba=clientes"
captura operacao    1320 "?aba=opera"
captura assistente  1180 "?pergunta=Em%20que%20hor%C3%A1rios%20o%20prazo%20de%20entrega%20falha%20mais%3F"
