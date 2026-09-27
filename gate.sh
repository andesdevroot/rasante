#!/usr/bin/env bash
# Gate único del proyecto. Si esto no sale en verde, NO se commitea.
#
# `set -euo pipefail` no es decorativo: sin `pipefail`, `ruff | tail` devuelve el código de salida
# de `tail`, y un gate en rojo pasa desapercibido. Ya ocurrió dos veces.
set -euo pipefail

cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$PATH"
export UV_CACHE_DIR="${PWD}/.uv-cache"

echo "--- pytest ---"
uv run pytest -q
echo "--- ruff ---"
uv run ruff check .
echo "--- mypy (src y tests) ---"
uv run mypy
echo
echo "GATE EN VERDE"
