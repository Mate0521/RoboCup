#!/usr/bin/env bash
# Commitea y pushea los pesos de entrenamiento a git.
# Uso: ./scripts/push_weights.sh "mensaje opcional"
set -euo pipefail

MSG="${1:-checkpoint pesos $(date +%Y-%m-%d_%H:%M)}"
cd "$(dirname "$0")/.."

git add ml/weights/
git commit -m "$MSG" ml/weights/
git push
echo "✓ Pesos subidos: $MSG"
