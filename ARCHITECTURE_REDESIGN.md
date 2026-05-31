# Rediseño Arquitectónico — RoboCup 2D Soccer Simulation Team

## Tabla de Contenidos

1. [Diagnóstico del Estado Actual](#1-diagnóstico)
2. [Arquitectura en 8 Capas](#2-arquitectura-en-8-capas)
3. [Nueva Estructura de Carpetas](#3-nueva-estructura-de-carpetas)
4. [Algoritmos de Pathfinding](#4-algoritmos-de-pathfinding)
5. [Coordinación Multiagente — Arquitectura Híbrida](#5-coordinación-multiagente)
6. [Red Neuronal — Nueva Arquitectura](#6-red-neuronal)
7. [Sistema de Pases y Evaluación](#7-sistema-de-pases)
8. [Control de Espacios — Voronoi + Influence Maps](#8-control-de-espacios)
9. [Predicción y Modelado del Mundo](#9-predicción)
10. [Tácticas Colectivas](#10-tácticas-colectivas)
11. [Sistema de Recuperación (Gegenpress)](#11-recuperación)
12. [Entrenamiento — Estrategia Completa](#12-entrenamiento)
13. [Métricas Avanzadas](#13-métricas)
14. [Plan de Implementación por Fases](#14-plan-de-implementación)
15. [Impacto Esperado](#15-impacto-esperado)

---

## 1. Diagnóstico

### Problemas Identificados en el Código Actual

| # | Problema | Localización | Severidad |
|---|---|---|---|
| 1 | **Sin posicionamiento inicial correcto** | `decision.py:116` — solo usa `move` en reset_modes pero sin verificación de sincronización | CRÍTICO |
| 2 | **Sin localización absoluta** | `perception.py` — nunca estima `self_x`, `self_y` desde los flags del `see` | CRÍTICO |
| 3 | **FSM sin tiempo de reacción** | `fsm.py:183` — `SEARCH_TURN_STEP = 30°` fijo sin adaptación | ALTO |
| 4 | **Sin modelo de predicción** | No existe ningún sistema de predicción de balón o rivales | CRÍTICO |
| 5 | **Red neuronal subdimensionada** | `model.py` — 3 capas densas (128→64→32), sin attention, sin recurrencia | ALTO |
| 6 | **Sin sistema de pases** | `fsm.py:279` — `_default_kick()` patea al arco siempre, sin evaluación | CRÍTICO |
| 7 | **Sin coordinación multiagente** | Cada agente decide sin comunicación ni blackboard | CRÍTICO |
| 8 | **Sin zonificación dinámica** | `role_assignment.py` — zonas estáticas, no se adaptan | ALTO |
| 9 | **Sin pressing organizado** | No hay lógica de recuperación colectiva | ALTO |
| 10 | **Sin control de espacios** | No hay Voronoi, Influence Maps ni ocupancy grids | MEDIO |
| 11 | **State vector limitado** | `state_vector.py` — 58 features, sin información de velocidades angulares ni predicciones | ALTO |
| 12 | **Reward function simple** | `reward.py` — recompensa densa básica sin shaping ni intrinsic motivation | MEDIO |
| 13 | **Sin self-play** | `online_trainer.py` — solo entrena contra el mismo servidor | ALTO |
| 14 | **Sin lógica de arquero** | `fsm.py:96-134` — _goalkeeper_step rudimentario | ALTO |

---

## 2. Arquitectura en 8 Capas

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ACTION EXECUTION LAYER (8)                          │
│               actuators.py — Command Generation + Smoothing                │
├─────────────────────────────────────────────────────────────────────────────┤
│                        MOTION PLANNING LAYER (7)                           │
│           pathfinding.py — A*, Theta*, Flow Fields + Collision             │
├─────────────────────────────────────────────────────────────────────────────┤
│                   REINFORCEMENT LEARNING LAYER (6)                         │
│     ppo_trainer.py / sac_trainer.py — PPO + Prioritized Replay + Hindsight │
├─────────────────────────────────────────────────────────────────────────────┤
│                   MULTI-AGENT COORDINATION LAYER (5)                       │
│    blackboard.py / coordinator.py — Blackboard + Role Switching + Comms    │
├─────────────────────────────────────────────────────────────────────────────┤
│                         STRATEGIC LAYER (4)                                │
│  strategy.py / tactics.py — Formación, pressing, game plan, transitions   │
├─────────────────────────────────────────────────────────────────────────────┤
│                          TACTICAL LAYER (3)                                │
│   hybrid_fsm.py — Behavior Trees + HFSM + Voronoi + Space Control         │
├─────────────────────────────────────────────────────────────────────────────┤
│                         PREDICTION LAYER (2)                               │
│    predictor.py — Ball trajectory, rival motion, pass lanes, open space    │
├─────────────────────────────────────────────────────────────────────────────┤
│                         PERCEPTION LAYER (1)                               │
│  perception.py / localizer.py — World state, self-localization, filtering  │
│                                                                             │
│                          COMUNICACIÓN (BASE)                               │
│               client.py / parser.py — UDP + protocolo S-Expression         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Decisión por Ciclo (200ms / 100ms)

```
Servidor UDP
    │
    ▼
┌─────────────────┐
│  1. PERCEPTION  │  ← Recibe see, sense_body, hear
│   • Parsear      │
│   • Localizar    │  ← Estimación propia vía flags (Landmark EKF)
│   • Predecir     │  ← Predicción balón, rivales
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. SELF-AWARE  │  ← ¿Quién soy? Rol, zona, responsabilidad
│   • Identity     │
│   • Zone check   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. PREDICT      │  ← ¿Qué pasará en 5-10 ciclos?
│   • Ball traj.   │
│   • Rival moves  │
│   • Space eval   │
└────────┬────────┘
         │
         ▼
┌─────────────────────────┐
│  4. BLACKBOARD SYNC     │  ← Comunicación implícita (sin decir)
│   • Leer blackboard     │
│   • Publicar intención  │
│   • Coordinar roles     │
└────────┬───────────────┘
         │
         ▼
┌─────────────────┐
│  5. STRATEGY     │  ← ¿Qué contexto global?
│   • Game plan    │  ← posesión / pressing / transición
│   • Formation    │
│   • Phase        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  6. TACTICS      │  ← ¿Qué hacer localmente?
│   • HFSM/BT       │
│   • Voronoi      │  ← Control de espacio
│   • Pass eval    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  7. MOTION PLAN  │  ← ¿Cómo llegar?
│   • A* / Theta*  │
│   • Flow field   │
│   • Collision    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  8. ACTUATORS    │  ← Ejecutar comando
│   • Smooth       │
│   • Send UDP     │
└────────┬────────┘
         │
         ▼
    Servidor UDP
```

---

## 3. Nueva Estructura de Carpetas

```
src/
├── main.py                         # Entry point (sin cambios)
├── agent.py                        # Refactorizado: 8-capas
│
├── comunication/                   # Sin cambios mayores
│   ├── client.py                   # + reconexión inteligente
│   └── parser.py                   # + parsing de flags para localización
│
├── perception/                     # ← NUEVO: Capa 1-2
│   ├── __init__.py
│   ├── world_state.py              # Estado global del mundo (refactor)
│   ├── play_modes.py               # Todos los play modes
│   ├── localizer.py                # ← NUEVO: EKF para self_x, self_y
│   ├── object_tracker.py           # ← NUEVO: Tracking de objetos visibles
│   └── filtering.py                # ← NUEVO: Filtro de ruido UDP
│
├── prediction/                     # ← NUEVO: Capa 3
│   ├── __init__.py
│   ├── ball_predictor.py           # Trayectoria del balón (física)
│   ├── rival_predictor.py          # Predicción de movimiento rival (Kalman)
│   ├── pass_lane_evaluator.py      # Líneas de pase disponibles
│   └── space_predictor.py          # Espacios libres futuros
│
├── coordination/                   # ← NUEVO: Capa 4-5
│   ├── __init__.py
│   ├── blackboard.py               # Pizarra compartida (thread-safe dict)
│   ├── coordinator.py              # Coordinador central de roles
│   ├── role_manager.py             # Gestión de roles dinámicos
│   └── communication_protocol.py   # Protocolo say/hear estructurado
│
├── strategy/                       # ← NUEVO: Capa 5
│   ├── __init__.py
│   ├── game_plan.py                # Plan de juego global
│   ├── possession.py               # Estrategia de posesión
│   ├── pressing.py                 # Estrategia de pressing
│   ├── transition.py               # Transiciones ataque↔defensa
│   └── formation_433.py            # Formación 4-3-3 dinámica
│
├── tactics/                        # ← NUEVO: Capa 6
│   ├── __init__.py
│   ├── hybrid_fsm.py               # HFSM + Behavior Tree
│   ├── voronoi_control.py          # Diagramas de Voronoi
│   ├── influence_maps.py           # Mapas de influencia
│   ├── pass_evaluation.py          # Sistema de scoring de pases
│   ├── space_control.py            # Ocupancy grids
│   └── set_pieces.py               # Jugadas de estrategia
│
├── planning/                       # ← NUEVO: Capa 7
│   ├── __init__.py
│   ├── astar.py                    # A* adaptado a campos continuos
│   ├── theta_star.py               # Theta* para ángulos más naturales
│   ├── flow_field.py               # Flow fields para movimiento colectivo
│   ├── collision_avoidance.py      # Evitación de colisiones
│   └── smooth_motion.py            # Suavizado de trayectorias
│
├── modules/                        # ← Refactorizado
│   ├── __init__.py
│   ├── actuators.py                # + comandos avanzados
│   ├── state_vector.py             # → 128 features
│   └── game_rules.py               # + reglas extendidas
│
├── ml/                             # ← Refactorizado
│   ├── __init__.py
│   ├── model_v2.py                 # ← NUEVO: Transformer + Attention
│   ├── ppo_trainer.py              # ← NUEVO: PPO online
│   ├── sac_trainer.py              # ← NUEVO: SAC offline
│   ├── replay_buffer.py            # ← NUEVO: Prioritized Replay
│   ├── reward_shaping.py           # ← NUEVO: Reward shaping avanzado
│   ├── self_play.py                # ← NUEVO: Self-play
│   ├── imitation.py                # ← NUEVO: Behavioral Cloning
│   └── curriculum.py               # ← NUEVO: Curriculum Learning
│
├── metrics/                        # ← NUEVO
│   ├── __init__.py
│   ├── game_analyzer.py            # Analizador de partidos en vivo
│   ├── possession_tracker.py       # Tracking de posesión
│   ├── pass_analyzer.py            # Estadísticas de pases
│   ├── heatmap_generator.py        # Mapas de calor
│   └── coordination_index.py       # Índice de coordinación
│
└── util/
    ├── field_constants.py          # + constantes expandidas
    ├── geometry.py                 # ← NUEVO: geometría 2D
    ├── interpolation.py            # ← NUEVO: interpolación y smoothing
    └── profiling.py                # ← NUEVO: profiling de rendimiento
```

---

## 4. Algoritmos de Pathfinding

### Comparativa para RoboCup 2D

| Algoritmo | Ventajas | Desventajas | Uso en RoboCup |
|---|---|---|---|
| **A*** | Óptimo, completo, simple | No considera ángulos de giro,格子状 | ✅ Movimiento a posición táctica |
| **Theta*** | Ángulos naturales, any-angle paths | Más costoso que A* | ✅ Movimiento al balón |
| **Jump Point Search** | ~10x más rápido que A* en grids | Solo grids uniformes | ❌ Campo no es grid uniforme |
| **Dijkstra** | Completo, garantiza shortest path | Lento, sin heurística | ❌ Preferir A* |
| **Flow Fields** | Movimiento colectivo coordinado, evita colisiones | Cálculo por frame costoso | ✅ Movimiento de equipo completo |

### Arquitectura de Pathfinding Propuesta

```
┌─────────────────────────────────────────────────────┐
│                 PATH PLANNER                        │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────┐   ┌──────────────┐               │
│  │   A* Planner  │   │ Theta* Plan  │               │
│  │ (posiciones   │   │ (movimiento  │               │
│  │  tácticas)    │   │  al balón)   │               │
│  └──────┬───────┘   └──────┬───────┘               │
│         │                  │                         │
│         ▼                  ▼                         │
│  ┌──────────────────────────────────────┐           │
│  │       Flow Field Generator           │           │
│  │  (campo de potencial para equipo)    │           │
│  └──────────────┬───────────────────────┘           │
│                 │                                    │
│                 ▼                                    │
│  ┌──────────────────────────────────────┐           │
│  │      Collision Avoidance Module      │           │
│  │  (evita compañeros y rivales)        │           │
│  └──────────────┬───────────────────────┘           │
│                 │                                    │
│                 ▼                                    │
│  ┌──────────────────────────────────────┐           │
│  │        Smooth Motion Filter          │           │
│  │  (elimina zigzag, suaviza giros)     │           │
│  └──────────────────────────────────────┘           │
└─────────────────────────────────────────────────────┘
```

### Implementación recomendada

**A*** para navegación táctica → `planning/astar.py`:
- Grid de celdas de 1m x 1m (105 x 68 = 7,140 celdas)
- Heurística: distancia euclidiana
- Costo adicional: proximidad a rivales (+50% si hay rival cerca)
- Penalización: salir de zona estricta (+100%)

**Theta*** para ir al balón → `planning/theta_star.py`:
- Any-angle: permite diagonales sin grid
- Ideal para `MOVE_TO_BALL` — caminos más suaves
- 20-30% más lento que A* pero caminos 15% más cortos

**Flow Fields** para movimiento colectivo → `planning/flow_field.py`:
- Cálculo por capas: 1 flow field por situación táctica
- Cada jugador sigue el gradiente de su propio campo
- Integración directa con Voronoi para evitar colisiones
- Recalculado cada 5-10 ciclos (no cada frame)

---

## 5. Coordinación Multiagente

### Arquitectura Híbrida Propuesta

```
┌─────────────────────────────────────────────────────────────────────┐
│                   BLACKBOARD SYSTEM (Central)                      │
│                                                                     │
│  Almacenes compartidos:                                             │
│  ┌────────────┐  ┌───────────┐  ┌──────────┐  ┌────────────────┐ │
│  │ Ball Info  │  │ Intents   │  │ Zones    │  │ Tactical State │ │
│  │ Pos, vel,  │  │ "voy al   │  │ Coverage │  │ formation,     │ │
│  │ predicted  │  │  balón"   │  │ por agente│  │ phase, strategy│ │
│  └────────────┘  └───────────┘  └──────────┘  └────────────────┘ │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          │               │               │
          ▼               ▼               ▼
   ┌──────────┐   ┌──────────┐   ┌──────────┐
   │ Agent #1 │   │ Agent #2 │   │ Agent #11│
   │ ┌──────┐ │   │ ┌──────┐ │   │ ┌──────┐ │
   │ │HFSM+BT│ │   │ │HFSM+BT│ │   │ │HFSM+BT│ │
   │ └──────┘ │   │ └──────┘ │   │ └──────┘ │
   │ +PPO     │   │ +PPO     │   │ +PPO     │
   └──────────┘   └──────────┘   └──────────┘
```

### Behavior Tree + HFSM (Agente Individual)

Cada agente ejecuta un **árbol híbrido**:

```
Selector (Prioridad)
│
├── Sequence: EMERGENCY
│   ├── ¿Soy portero Y balón entrando?
│   └── Catch / Clear
│
├── Sequence: SET_PIECE (solo si play_mode != play_on)
│   ├── ¿Soy ejecutor?
│   │   ├── Sí → Ir al balón → Ejecutar
│   │   └── No → Ir a posición táctica set_piece
│   └── Esperar señal
│
├── Sequence: DEFENSE (si balón cerca de mi área)
│   ├── ¿Soy el más cercano al balón?
│   │   ├── Sí → Presionar (HFSM: PRESS_STATE)
│   │   └── No → Cubrir espacio / Cerrar líneas de pase
│   └── Basculación defensiva
│
├── Sequence: POSSESSION (si mi equipo tiene el balón)
│   ├── ¿Tengo el balón?
│   │   ├── Sí → Pass Evaluator → Mejor pase o driblar
│   │   └── No → ¿Soy apoyo?
│   │       ├── Sí → Ir a espacio libre (Voronoi)
│   │       └── No → Atraer rival / Crear espacios
│   └── Triangulación
│
└── Sequence: TRANSITION (ninguna anterior aplica)
    ├── PLAY_ON → HFSM normal
    │   ├── GO_TO_POSITION
    │   ├── SEARCH_BALL
    │   ├── MOVE_TO_BALL
    │   └── KICK_BALL
    └── Recuperar posición
```

### Blackboard System

```
blackboard.py:
- Es SINGLETON thread-safe
- Se actualiza CADA ciclo antes de decidir
- Contenido:
  {
    "ball": { "pos": (x,y), "vel": (vx,vy), "predicted_5": (x,y),
              "last_touch": agent_id, "last_touch_team": "left"|"right" },
    "intents": {
      2: { "action": "move_to_ball", "target": (x,y), "priority": 0.8 },
      7: { "action": "support", "target": (x,y), "priority": 0.5 },
    },
    "zones": {
      "voronoi": { # Asignación dinámica de zonas
        2: { "area": [(x1,y1), ...], "center": (cx,cy) },
        ...
      }
    },
    "tactical": {
      "formation": "4-3-3",
      "phase": "possession" | "pressing" | "defensive" | "transition",
      "pressing_active": bool,
      "strategy": "short_pass" | "counter" | "hold_ball"
    },
    "score": { "left": N, "right": N, "time": T }
  }
```

### Protocolo de Comunicación Vía Say/Hear

Aunque el ancho de banda es limitado, podemos enviar intenciones compactas:

```
Mensaje estructurado (3 casos):

1. "intent M" + id_acción (1-20) + target_x codificado + target_y codificado
   Ej: "i 3 142 0" → acción=3 (apoyo), target_x=14.2, target_y=0.0

2. "ball" + x + y + vx + vy → corrección de posición del balón
   Ej: "b 521 31 05 -02" → balón en (52.1, 3.1), vel (0.5, -0.2)

3. "role" + número → solicitar intercambio de rol
   Ej: "r 2" → "quiero tu rol" (negociación implícita)
```

---

## 6. Red Neuronal

### Arquitectura Actual (Problemas)

```python
# model.py — Actual
Dense(128 → 64 → 32) + softmax(5) + tanh(3)
# Problemas:
# - Sin recurrencia → ignora historia
# - Sin atención → ignora contexto
# - 58 features → insuficientes
# - Sin skip connections → vanishing gradient
```

### Nueva Arquitectura: Transformer-Tactical

```
Input: 128 features
    │
    ▼
┌─────────────────────────────┐
│   Embedding Táctico         │  32-dim, entrenable
│   + Positional Encoding     │  (por ciclo de simulación)
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Transformer Block × 2     │
│                             │
│   ┌───────────────────┐     │
│   │ Multi-Head Self-   │     │  4 cabezas, 32-dim c/u
│   │ Attention          │     │
│   └─────────┬─────────┘     │
│             │               │
│   ┌─────────▼─────────┐     │
│   │ FFN: 128 → 64 → 32 │     │  ReLU + Dropout 0.15
│   └─────────┬─────────┘     │
│             │               │
│   + Residual + LayerNorm    │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│   LSTM (opcional)           │  32 celdas — para secuencias
│   (solo si hay 5+ frames    │
│    en buffer local)         │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   Tactical Embedding        │
│   (Voronoi + Influence Map  │
│    encoded as vector)       │  16-dim
└──────────┬──────────────────┘
           │
           ▼
     ┌─────┴─────┐
     │           │
     ▼           ▼
┌────────┐ ┌──────────────┐
│ HEAD 1  │ │ HEAD 2       │
│ Classif │ │ Regression   │
│ 8 acc. │ │ 4 params     │
│ softmax │ │ tanh         │
│[turn_L, │ │[turn, dash,  │
│ turn_R, │ │ kick_power,  │
│ dash,   │ │ kick_dir]    │
│ kick,   │ │              │
│ pass_S, │ │              │
│ pass_L, │ │              │
│ dribble,│ │              │
│ stay]   │ │              │
└────────┘ └──────────────┘
```

### Acciones Expandidas (8 clases)

| # | Acción | Descripción |
|---|---|---|
| 0 | `TURN_LEFT` | Girar a la izquierda |
| 1 | `TURN_RIGHT` | Girar a la derecha |
| 2 | `DASH` | Correr |
| 3 | `KICK` | Patear (disparo) |
| 4 | `PASS_SHORT` | Pase corto (< 15m) |
| 5 | `PASS_LONG` | Pase largo (> 15m) |
| 6 | `DRIBBLE` | Conducir el balón (dash + kick suave) |
| 7 | `STAY` | Esperar / no hacer nada |

### Nuevo State Vector — 128 Features

| Rango | Feature | Descripción |
|---|---|---|
| 0-7 | **Balón** | distancia, ángulo, vel_dist, vel_ang, visible, kickable, predicción_5, predicción_10 |
| 8-15 | **Agente propio** | x, y, stamina, effort, speed, body_dir, head_angle, velocidad angular |
| 16-19 | **Rol** | one-hot (4) |
| 20-27 | **FSM State** | one-hot (6) + estado BT (2) |
| 28-36 | **Play Mode** | one-hot (9 grupos) |
| 37-48 | **Compañeros** | top 4 (dist, angle, vel_x, vel_y) = 16 / 2 |
| 49-56 | **Compañeros** | top 4 restantes |
| 57-68 | **Rivales** | top 4 (dist, angle, vel_x, vel_y) = 16 / 2 |
| 69-76 | **Rivales** | top 4 restantes |
| 77-84 | **Posición táctica** | target_x, target_y, dist_target, angle_target, en_zona, en_fuera_de_juego, near_boundary, in_penalty |
| 85-90 | **Voronoi** | área_controlada, agents_cerca, rivals_cerca, espacio_libre_dir, espacio_libre_dist |
| 91-96 | **Contexto partido** | time_norm, score_diff, players_active, posesión_ratio (estimado), fase (ataque/defensa/transición), estrategia_actual |
| 97-104 | **Predicciones** | ball_x_fut, ball_y_fut, rival_más_cercano_fut_dist, espacio_libre_fut_dir, espacio_libre_fut_dist |
| 105-112 | **Pases** | mejor_pase_dist, mejor_pase_angle, riesgo_pase, openings_count, passing_lanes_count |
| 113-120 | **Historial** | última acción (one-hot 8) |
| 121-127 | **Embedding táctico** | vector aprendido (8-dim) |

---

## 7. Sistema de Pases

### Pass Evaluation — Algoritmo de Scoring

```
PASS_SCORE = w_dist * DIST_SCORE + w_risk * RISK_SCORE
           + w_space * SPACE_SCORE + w_tactical * TACTICAL_SCORE
           + w_pressure * PRESSURE_SCORE

Donde:
  DIST_SCORE     = 1.0 - (pass_distance / max_pass_distance)  ← pases cortos preferidos
  RISK_SCORE     = 1.0 - (nearest_rival_dist / pass_distance) ← riesgo de intercepción
  SPACE_SCORE    = receiver_open_space / max_open_space       ← espacio del receptor
  TACTICAL_SCORE = 1.0 si receptor está en mejor posición     ← valor estratégico
  PRESSURE_SCORE = 1.0 - (pressure_on_passer / max_pressure)  ← press sobre el pasador
```

### Passing Network — Triangulación

```
Para cada ciclo:
  1. Identificar TOP 3 receptores
  2. Para cada receptor, calcular PASS_SCORE
  3. Si PASS_SCORE > THRESHOLD (0.6):
       → Seleccionar el de mayor score
       → Si hay triangulación (2 receptores forman triángulo):
           → Priorizar pase que mantenga el triángulo
  4. Si PASS_SCORE máximo < THRESHOLD:
       → Mantener posesión (driblar / girar)
       → Esperar mejor opción
  5. NUNCA despejar — solo pase seguro o driblar
```

### Tipos de Pase

| Tipo | Distancia | Riesgo | Uso |
|---|---|---|---|
| **Pase de seguridad** | 3-8m | Muy bajo | Mantener posesión, laterales/atrás |
| **Pase de progresión** | 8-15m | Medio | Avanzar al mediocampo rival |
| **Pase filtrado** | 10-20m | Alto | Romper líneas rivales (solo si alta prob.) |
| **Cambio de frente** | 20-35m | Medio-Alto | Cambiar orientación del juego |
| **Pase al espacio** | 15-30m | Alto | Balón a la espalda de la defensa |

---

## 8. Control de Espacios

### Voronoi Diagrams

```
voronoi_control.py:

Para cada ciclo:
  1. Obtener posiciones de TODOS los agentes (compañeros + rivales visibles)
  2. Calcular diagrama de Voronoi (algoritmo de Fortune o Bowyer-Watson)
  3. Para cada compañero:
       área_control = calcular área de celda Voronoi
       si área_control < threshold:
           → mover a celda más grande (intercambio de zona)
  4. Asignar zonas dinámicamente:
       - Cada agente cubre su celda Voronoi
       - Si dos agentes están muy cerca → uno se expande
       - Si hay hueco → agente más cercano lo cubre
```

### Influence Maps

```
influence_maps.py:

Dos capas:
  1. Allied Influence → positiva en posiciones amigas
  2. Enemy Influence → negativa en posiciones rivales

Para cada punto (x,y):
  influence(x,y) = Σ allied_influence_i(x,y) - Σ enemy_influence_j(x,y)

  influence_i(x,y) = strength_i / (1 + distance_i^2)

Donde strength depende del rol:
  goalkeeper: 3.0
  defender:   2.0
  midfielder: 1.5
  forward:    1.0

Uso:
  - Espacios con influence > 0 → seguros para moverse
  - Espacios con influence < 0 → evitar (presión rival)
  - Pases óptimos: receiver en zona influence > 0
```

### Ocupancy Grids

```
space_control.py:

Grid de 5m x 5m (21 x 14 = 294 celdas):

Estado de cada celda:
  CONTROLADA   = más compañeros que rivales (verde)
  DISPUTADA    = igual número (amarillo)
  RIVAL        = más rivales (rojo)
  VACÍA        = nadie

Objetivo: tener más celdas "CONTROLADA" que el rival.
```

---

## 9. Predicción

### Ball Predictor

```python
class BallPredictor:
    """
    Predice la posición del balón en N ciclos usando
    el modelo físico del servidor RoboCup.
    """
    # Constantes físicas del rcssserver:
    BALL_DECAY     = 0.94   # factor de amortiguamiento
    BALL_SPEED_MAX = 3.0    # m/s máximo
    PLAYER_DECAY   = 0.4

    def predict(self, pos, vel, n_cycles=5):
        x, y = pos
        vx, vy = vel
        trajectory = [(x, y)]
        for _ in range(n_cycles):
            vx *= self.BALL_DECAY
            vy *= self.BALL_DECAY
            x += vx
            y += vy
            # Rebote en bordes del campo
            if abs(x) > 52.5: vx *= -1; x = clamp(x)
            if abs(y) > 34.0: vy *= -1; y = clamp(y)
            trajectory.append((x, y))
        return trajectory
```

### Rival Predictor (Kalman Filter)

```python
class RivalTracker:
    """
    Filtro de Kalman para predecir posición futura de rivales.
    Modelo: velocidad constante con ruido.
    """
    def __init__(self):
        self.kalman_filters = {}  # unum → KalmanFilter

    def update(self, rival_id, pos, vel):
        if rival_id not in self.kalman_filters:
            self.kalman_filters[rival_id] = self._init_kf(pos, vel)
        else:
            self.kalman_filters[rival_id].predict()
            self.kalman_filters[rival_id].update(pos)

    def predict(self, rival_id, n_cycles=5):
        kf = self.kalman_filters.get(rival_id)
        if not kf:
            return None
        # Predecir n_cycles hacia adelante
        return kf.predict_n_steps(n_cycles)
```

### Pass Lane Evaluator

```python
class PassLaneEvaluator:
    """
    Evalúa si hay una línea de pase limpia entre dos puntos.
    """
    def evaluate(self, passer_pos, receiver_pos, rivals_positions):
        # 1. Línea recta entre pasador y receptor
        # 2. Para cada rival:
        #      distancia a la línea de pase
        #      si distancia < 2.0m → intercepción posible
        #      calcular intercept_time
        # 3. Si intercept_time < ball_travel_time → pase bloqueado
        # 4. Return: { "clean": bool, "interceptor": id, "risk": float }
```

---

## 10. Tácticas Colectivas

### Ataque Posicional (Posesión)

```
Fase de ataque — objetivos por rol:

Goalkeeper (1):
  - Iniciar juego corto (pase a defensas)
  - Nunca despejar largo

Defenders (2-5):
  - Formar línea de 4 comprimida (anchura 30m)
  - Pases horizontales y hacia el mediocampo
  - No superar la línea media

Midfielders (6-8):
  - Formar triángulo: 6-7-8 en rombo
  - Ofrecer líneas de pase CONSTANTES
  - Rotación: si uno sube, otro cubre
  - Control del centro del campo

Forwards (9-11):
  - Amplitud máxima (pegados a bandas 9 y 11)
  - Profundidad: 10 juega de "falso 9" (cae al mediocampo)
  - Arrastrar defensas rivales
```

### Triangulación Permanente

```
Regla de oro: EN TODO MOMENTO debe haber
al menos 2 opciones de pase para el poseedor.

Estructura:
  Poseedor ──── Compañero A (opción 1)
       │
       └──────── Compañero B (opción 2)

Los tres forman un triángulo de 5-12m de lado.

Si no hay triángulo:
  - El poseedor gira buscando espacio
  - Los compañeros se reubican automáticamente
```

### Presión Alta (Gegenpress)

```
Activación:
  - Pérdida de balón en campo rival (mitad ofensiva)
  - Inmediata: TODOS los jugadores ofensivos presionan

Roles en pressing:
  1. First Presser (más cercano al balón):
     - Sprint directo al poseedor
     - Objetivo: robar o forzar error

  2. Second Presser (segundo más cercano):
     - Cubrir línea de pase más cercana
     - Evitar pase de seguridad

  3. Cutters (resto):
     - Cerrar líneas de pase hacia adelante
     - Forzar juego lateral o hacia atrás
     - Mantener bloque compacto

  4. Cover (defensas + portero):
     - Subir línea defensiva (comprimir campo)
     - Evitar pase en profundidad

Duración: máx 10-15 ciclos. Si no se recupera:
  → Transición a bloque medio
```

### Bloque Medio / Bajo

```
Bloque Medio:
  - Defensas en línea a 30m de nuestro arco
  - Mediocampistas a 40m
  - Delanteros presionan en 50-52m
  - Espacios entre líneas: < 10m
  - Basculación lateral según posición del balón

Bloque Bajo:
  - Defensas en línea del área (16.5m)
  - Todos los jugadores en nuestro campo
  - Objetivo: proteger el área
  - Solo usado en los últimos minutos de partido
```

### Transiciones

```
Pérdida → Defensa (ataque → defensa):
  0-3 ciclos: Gegenpress activo
  4-10 ciclos: Repliegue a bloque medio
  11+ ciclos: Bloque bajo si es necesario
  Tiempo total de reacción: < 2 ciclos (200ms)

Recuperación → Ataque (defensa → ataque):
  0-2 ciclos: Pase de seguridad (no perder el balón)
  3-8 ciclos: Progresión controlada
  9+ ciclos: Ataque posicional
  Principio: mejor perder la jugada que el balón
```

---

## 11. Recuperación

### Sistema de Recuperación en 3 Fases

```
FASE 1: CHOQUE INMEDIATO (ciclos 0-3)
┌─────────────────────────────────────┐
│ • Identificar pérdida               │
│   (cambio de posesión detectado)    │
│ • First Presser: al poseedor        │
│ • Second Presser: cubre pase corto  │
│ • Resto: comprime espacio           │
└─────────────────────────────────────┘

FASE 2: PRESIÓN ORGANIZADA (ciclos 4-10)
┌─────────────────────────────────────┐
│ • Si no se recuperó en Fase 1       │
│ • Mantener bloque compacto          │
│ • Cerrar líneas de pase hacia ad.   │
│ • Forzar al rival a jugar lateral   │
└─────────────────────────────────────┘

FASE 3: REORDENAMIENTO (ciclos 11+)
┌─────────────────────────────────────┐
│ • Recuperar posiciones tácticas     │
│ • Bloque medio o bajo               │
│ • Preparar siguiente ataque         │
└─────────────────────────────────────┘
```

### Cobertura de Líneas de Pase

```python
def cover_pass_lines(ball_pos, rivals, teammates):
    """
    Para cada rival cerca del balón:
      - Identificar sus posibles receptores
      - Asignar compañero para cubrir cada línea
    """
    for rival in near_ball_rivals:
        # Posibles receptores (top 3)
        receivers = identify_receivers(rival, rivals)
        # Asignar cobertura
        for receiver in receivers:
            nearest_teammate = find_nearest(teammates, receiver)
            assign_cover(nearest_teammate, receiver)
```

---

## 12. Entrenamiento

### Estrategia de Entrenamiento en 4 Fases

```
FASE 1: Behavioral Cloning (Offline)
  Data: logs .rcg de partidos de alto nivel
  Objetivo: aprendizaje por imitación
  Técnica: Behavioral Cloning con augmentación
  Duración: 100 epochs por rol
  Resultado: baseline que sabe jugar

FASE 2: PPO Online (Auto-play)
  Data: partidos contra sí mismo
  Objetivo: fine-tuning con RL
  Algoritmo: PPO con clip ε=0.2
  Reward: ver abajo
  Duración: 10,000 episodios

FASE 3: Self-Play + Curriculum
  Data: partidos contra versiones anteriores
  Objetivo: mejora continua
  Técnica:
    - 50% contra versión actual
    - 30% contra versión N-1
    - 20% contra versión N-2
  Duración: continua

FASE 4: Sparse Reward + Hindsight
  Data: partidos reales
  Objetivo: aprendizaje de eventos raros (goles)
  Técnica: HER (Hindsight Experience Replay)
```

### Reward Shaping Avanzado

```python
class AdvancedReward:
    """
    Recompensa total = Σ pesos * componentes
    """
    WEIGHTS = {
        "possession":       1.0,   # mantener posesión
        "pass_success":     0.5,   # pase completado
        "ball_progression": 0.3,   # avanzar con el balón
        "space_control":    0.2,   # control del espacio
        "pressing_success": 1.0,   # recuperación
        "goal_scored":      5.0,   # gol
        "goal_conceded":    -5.0,  # gol recibido
        "zone_discipline":  0.1,   # mantener zona
        "support_position": 0.2,   # estar en posición de apoyo
        "interception":     0.5,   # interceptar pase
        "tackle_success":   0.3,   # entrada exitosa
        "useless_kick":     -0.5,  # despeje innecesario
        "out_of_position":  -0.3,  # fuera de posición
        "ball_loss":        -1.0,  # pérdida de balón
    }

    def calculate(self, state, prev_state):
        reward = 0.0
        # Posesión: ¿mi equipo tiene el balón?
        if state.ball_last_touch == "my_team":
            reward += self.WEIGHTS["possession"]
        # ... más componentes
        return reward
```

### Curriculum Learning

```
Nivel 1: Balón parado (solo pases)
  - Sin rivales
  - Solo practicar pases precisos
  - Objetivo: 90% precisión

Nivel 2: 1v1
  - Un atacante vs un defensor
  - Objetivo: mantener posesión

Nivel 3: 3v2
  - Tres atacantes vs dos defensores
  - Objetivo: triangulación

Nivel 4: 5v5
  - Medio campo
  - Objetivo: posesión 60%

Nivel 5: 7v7
  - Casi completo
  - Objetivo: integración

Nivel 6: 11v11
  - Partido completo
  - Objetivo: ganar
```

---

## 13. Métricas

### Sistema de Métricas en Vivo

```python
class GameMetrics:
    """
    Métricas calculadas en tiempo real durante el partido.
    """

    def __init__(self):
        self.metrics = {
            "possession":             0.0,  # % tiempo con balón
            "pass_completion":        0.0,  # % pases completados
            "pass_accuracy":          0.0,  # precisión de pase (metros de error)
            "recovery_time":          0.0,  # ciclos promedio para recuperar
            "pressing_success":       0.0,  # % presiones exitosas
            "ball_recoveries":        0,    # recuperaciones totales
            "distance_covered":       0.0,  # metros totales recorridos
            "space_control_ratio":    0.0,  # % campo controlado
            "coordination_index":     0.0,  # índice de coordinación
            "triangulation_count":    0,    # momentos con triangulación
            "intensity":              0.0,  # intensidad media (dashes/ciclo)
            "useless_kicks":          0,    # despejes innecesarios
            "positional_discipline":  0.0,  # % tiempo en zona
            "passing_lanes_created":  0,    # líneas de pase creadas
            "interceptions":          0,    # pases interceptados
            "tactical_efficiency":    0.0,  # eficiencia táctica
            "response_time":          0.0,  # tiempo de reacción promedio
        }

    def calculate_coordination_index(self, teammates):
        """
        Mide qué tan coordinado está el equipo:
        - Distancia promedio entre compañeros (ideal: 8-15m)
        - Desviación estándar de distancias
        - Número de triángulos formados
        - Superposición de zonas
        """
        distances = []
        for t1 in teammates:
            for t2 in teammates:
                if t1.unum < t2.unum:
                    d = distance(t1.pos, t2.pos)
                    distances.append(d)

        mean_dist = np.mean(distances)
        std_dist = np.std(distances)
        triangles = self._count_triangles(teammates)

        # Ideal: mean_dist ~ 10m, std_dist < 5m, triangles > 5
        score = 1.0 - abs(mean_dist - 10.0) / 20.0
        score *= 1.0 - min(1.0, std_dist / 10.0)
        score *= min(1.0, triangles / 8.0)

        return score
```

---

## 14. Plan de Implementación por Fases

### Fase 0 — Correcciones Críticas (Semana 1)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Implementar localización EKF desde flags | `perception/localizer.py` | 🔴 |
| Corregir posicionamiento inicial con `move()` | `decision.py` / `agent.py` | 🔴 |
| Implementar `actuators.move()` con sincronización | `modules/actuators.py` | 🔴 |
| Añadir predicción básica de balón | `prediction/ball_predictor.py` | 🔴 |
| Corregir `_goalkeeper_step` | `tactics/hybrid_fsm.py` | 🟡 |

### Fase 1 — Sistema de Pases y Posesión (Semana 2)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Pass Evaluation System | `tactics/pass_evaluation.py` | 🔴 |
| Passing Network + Triangulación | `strategy/possession.py` | 🔴 |
| Sistema de apoyo (support positions) | `tactics/space_control.py` | 🔴 |
| Eliminar despejes | Modificar `decision.py` | 🔴 |

### Fase 2 — Control de Espacios (Semana 3)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Voronoi Diagram | `tactics/voronoi_control.py` | 🟡 |
| Influence Maps | `tactics/influence_maps.py` | 🟡 |
| Ocupancy Grids | `tactics/space_control.py` | 🟡 |
| Integrar con movimiento | `planning/flow_field.py` | 🟡 |

### Fase 3 — Pathfinding (Semana 4)

| Tarea | Archivo | Prioridad |
|---|---|---|
| A* adaptado | `planning/astar.py` | 🟡 |
| Theta* para mov. al balón | `planning/theta_star.py` | 🟡 |
| Flow Fields para equipo | `planning/flow_field.py` | 🟡 |
| Collision Avoidance | `planning/collision_avoidance.py` | 🟡 |

### Fase 4 — Coordinación Multiagente (Semana 5)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Blackboard System | `coordination/blackboard.py` | 🔴 |
| Communication Protocol | `coordination/communication_protocol.py` | 🟡 |
| Role Manager dinámico | `coordination/role_manager.py` | 🟡 |
| Behavior Tree + HFSM | `tactics/hybrid_fsm.py` | 🔴 |

### Fase 5 — Pressing y Recuperación (Semana 6)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Gegenpress system | `strategy/pressing.py` | 🟡 |
| Counter-pressing | `strategy/pressing.py` | 🟡 |
| Coverage de líneas de pase | `coordination/coordinator.py` | 🟡 |
| Transiciones rápidas | `strategy/transition.py` | 🟡 |

### Fase 6 — Red Neuronal V2 (Semana 7-8)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Transformer-Tactical | `ml/model_v2.py` | 🔴 |
| State Vector 128 features | `modules/state_vector.py` | 🔴 |
| PPO Trainer | `ml/ppo_trainer.py` | 🔴 |
| Prioritized Replay | `ml/replay_buffer.py` | 🟡 |
| Reward Shaping avanzado | `ml/reward_shaping.py` | 🟡 |

### Fase 7 — Entrenamiento Avanzado (Semana 9-10)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Self-Play | `ml/self_play.py` | 🟡 |
| Curriculum Learning | `ml/curriculum.py` | 🟡 |
| Imitation Learning | `ml/imitation.py` | 🟡 |
| Behavioral Cloning pipeline | `ml/trainer.py` refactor | 🟡 |

### Fase 8 — Métricas y Optimización (Semana 11-12)

| Tarea | Archivo | Prioridad |
|---|---|---|
| Live metrics system | `metrics/game_analyzer.py` | 🟢 |
| Heatmaps y visualización | `metrics/heatmap_generator.py` | 🟢 |
| Profiling de rendimiento | `util/profiling.py` | 🟢 |
| Optimización final | Varios | 🟢 |

---

## 15. Impacto Esperado

| Métrica | Actual | Proyectado (Fase 8) |
|---|---|---|
| Posesión de balón | ~35% | **65-75%** |
| Pases completados | ~40% | **85-90%** |
| Goles por partido | ~1-2 | **3-5** |
| Goles recibidos | ~3-4 | **0-1** |
| Recuperaciones por partido | ~10 | **30-40** |
| Tiempo de reacción | ~500ms | **<200ms** |
| Coordinación | Baja | **Alta (índice >0.8)** |
| Movimientos inútiles | Altos | **Minimizados** |
| Triangulación | Nunca | **Permanente** |
| Contraataques recibidos | Frecuentes | **Raros** |

### Comparación con Equipos RoboCup Reales

| Aspecto | Equipo Base | Este Rediseño | Top RoboCup (HELIOS, etc.) |
|---|---|---|---|
| Posicionamiento | Básico | Avanzado (Voronoi + Influence) | Profesional |
| Pases | Aleatorios | Evaluación multi-factor | Óptimos |
| Coordinación | Inexistente | Blackboard + BT + HFSM | MADP + modelos |
| ML | MLP simple | Transformer + PPO | CNN + LSTM + PPO |
| Velocidad | Lenta | Optimizada | Máxima |
| Pressing | No | Gegenpress organizado | Adaptativo |

---
