#!/usr/bin/env bash
# Gera as imagens do README a partir da aplicação rodando.
#   1) streamlit run app.py --server.port 8518 --server.headless true
#   2) bash scripts/capturar_telas.sh              (ou BASE=http://localhost:8519 bash ...)
# A captura em si está em capturar_telas.py (espera a página terminar de desenhar).
set -euo pipefail
cd "$(dirname "$0")/.."
BASE="${BASE:-http://localhost:8518}" python -X utf8 scripts/capturar_telas.py "$@"
