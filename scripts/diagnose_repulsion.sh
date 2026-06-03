#!/usr/bin/env bash
# Script de diagnóstico para el bug de repulsión magnética
# Uso: ./scripts/diagnose_repulsion.sh

echo "🔍 DIAGNÓSTICO DE REPULSIÓN MAGNÉTICA"
echo "======================================"
echo ""
echo "Monitoreando agente #10 (jugador principal)..."
echo "Presiona Ctrl+C para detener"
echo ""

docker logs -f origen 2>&1 | grep -E "\[10\].*CHASE|\[10\].*KICK|\[10\].*SUPPORT|\[10\].*kickable|⚠️|⚽" --line-buffered | while read line; do
    timestamp=$(date +"%H:%M:%S")
    echo "[$timestamp] $line"
done
