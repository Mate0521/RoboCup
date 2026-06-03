#!/bin/bash
set -e

if [ -n "$GIT_REPO_URL" ]; then
    echo "[ENTRYPOINT] Clonando $GIT_REPO_URL (branch: ${GIT_BRANCH:-main})..."

    git clone --depth 1 --branch "${GIT_BRANCH:-main}" "$GIT_REPO_URL" /app/repo

    cd /app/repo

    if [ -f requirements.txt ]; then
        echo "[ENTRYPOINT] Instalando dependencias..."
        pip install --no-cache-dir -r requirements.txt
    fi

    # Parche automatico: reemplaza SERVER_HOST/HOST hardcodeado por env var,
    # y agrega import os si falta
    echo "[ENTRYPOINT] Parcheando SERVER_HOST para usar SERVER_IP..."
    find /app/repo -name "*.py" | while read -r f; do
        if grep -q 'SERVER_HOST = "localhost"' "$f" 2>/dev/null; then
            if ! grep -q '^import os' "$f" 2>/dev/null && ! grep -q '^from os' "$f" 2>/dev/null; then
                sed -i '1s/^/import os\n/' "$f"
            fi
            sed -i 's/SERVER_HOST = "localhost"/SERVER_HOST = os.environ.get("SERVER_IP", "localhost")/g' "$f"
        fi
        if grep -q 'HOST = "localhost"' "$f" 2>/dev/null; then
            if ! grep -q '^import os' "$f" 2>/dev/null && ! grep -q '^from os' "$f" 2>/dev/null; then
                sed -i '1s/^/import os\n/' "$f"
            fi
            sed -i 's/HOST = "localhost"/HOST = os.environ.get("SERVER_IP", "localhost")/g' "$f"
        fi
    done

    # Parche: reemplaza team_name hardcodeado con la variable TEAM
    if [ -n "$TEAM" ]; then
        echo "[ENTRYPOINT] Parcheando team_name a $TEAM ..."
        find /app/repo -name "*.py" -exec sed -i "s/team_name=\"[^\"]*\"/team_name=\"$TEAM\"/g" {} \; 2>/dev/null || true
        find /app/repo -name "*.py" -exec sed -i "s/team_name='[^']*'/team_name='$TEAM'/g" {} \; 2>/dev/null || true
    fi

    # Buscar script de inicio
    for script in start.sh run_all.sh manager.py main.py; do
        if [ -f "$script" ]; then
            echo "[ENTRYPOINT] Ejecutando $script ..."
            chmod +x "$script" 2>/dev/null || true

            case "$script" in
                *.sh) exec bash "$script" ;;
                *.py) exec python "$script" ;;
                *)    exec bash "$script" ;;
            esac
        fi
    done

    echo "[ENTRYPOINT] No se encontro start.sh / run_all.sh / manager.py / main.py"
    exit 1
else
    echo "[ENTRYPOINT] GIT_REPO_URL no definido. Modo por defecto no disponible."
    exit 1
fi

