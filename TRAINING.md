# Entrenamiento PPO - v1.0.0

## Requisitos

- Python 3.8+
- TensorFlow (instalado: `pip install tensorflow`)
- rcssserver (RoboCup Soccer Simulator)
- Opcional: rcssmonitor (visualización)

## Cómo entrenar

### Opción 1: Docker (recomendado)

El stack Docker ya tiene servidor + 2 equipos + monitor configurados.

**1. Construir imágenes (solo primera vez):**
```bash
docker compose -f docker/docker-compose.yml build
```

**2. Iniciar entrenamiento:**
```bash
docker compose -f docker/docker-compose.yml -f docker/docker-compose.training.yml up
```

Esto levanta:
- `rcssserver` — simulador
- `team_left` — 11 agentes con `TRAINING=true`
- `team_right` — 11 agentes con `TRAINING=true`
- `rcssmonitor` — visualización VNC en `localhost:5900`

**Solo entrenar un equipo** (el otro como oponente fijo):
```bash
docker compose -f docker/docker-compose.yml run -e TRAINING=true team_left
```

**Verificar logs:**
```bash
docker compose logs -f team_left
```

**Los modelos se guardan en:**
- `ml/weights/` → montado como volumen, persiste aunque el contenedor muera
- `training_logs/` → historial JSON de episodios

### Opción 2: Local (sin Docker)

Requiere rcssserver instalado localmente.

**1. Iniciar el servidor:**
```bash
rcssserver server::auto_mode=true server::synch_mode=false
```

**2. Iniciar el entrenamiento:**

**Windows**:
```batch
start_training.bat
```

**Linux/WSL**:
```bash
chmod +x start_training.sh
./start_training.sh
```

**Manual**:
```bash
export TRAINING=true
python src/main_training.py
```

### Observar métricas

El entrenamiento imprime reportes cada 30s:

```
============================================================
  TRAINING REPORT  -  0:15:30
============================================================
  Episodios:        42
  Avg Reward (100): 2.34
  Avg Length (100): 876.5
  Avg Goals For:    1.2
  Avg Goals Agst:   0.8
  Total Cycles:     36813
  Cycles/sec:       39.6
  Elapsed:          0:15:30
============================================================
```

### 4. Modelos guardados

Los pesos se guardan en `ml/weights/`:
- `midfielder.weights.h5`
- `forward.weights.h5`
- `defender.weights.h5`
- `goalkeeper.weights.h5`

Mejor episodio → guardado automático en `ml/weights/`.

## Hyperparámetros

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| γ (gamma) | 0.99 | Discount factor |
| λ (GAE) | 0.95 | GAE smoothing |
| Clip ε | 0.2 | PPO clipping |
| PPO epochs | 10 | Updates per batch |
| Minibatch | 64 | SGD batch |
| Learning rate | 3e-4 | Adam optimizer |
| Entropy coef | 0.01 | Exploration bonus |
| Train every | 128 cycles | PPO update frequency |
| Save every | 500 cycles | Checkpoint frequency |

## Arquitectura del entrenamiento

```
rcssserver                 ← simulador
    ↑ UDP (6000)
    ↓
11 agent threads           ← 1 por jugador
    ↓
HybridController           ← decide FSM vs ML
    ↓
PPOTrainer                 ← colecciona experiencia
    ↓
TrajectoryBuffer (1024)    ← buffer on-policy
    ↓
PPO Update (GAE + clip)    ← cada 128 ciclos
    ↓
AgentBrainV2 (Transformer) ← red neuronal
```

## Monitoreo avanzado

Los logs detallados están en `training_logs/`:
- `training_history.jsonl` → cada episodio (reward, length, goles)
- `training_final.json` → resumen al finalizar

Para visualizar en tiempo real: `rcssmonitor`

## Evaluación

Para probar el modelo entrenado:

```bash
set TRAINING=false
python src/main.py
```

El agente cargará automáticamente los pesos guardados.
