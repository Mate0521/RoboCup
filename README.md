# RoboCup 2D Soccer Simulation Team

**Estado del Proyecto**: 68% completado  
**Última actualización**: Junio 1, 2026

## 📚 Documentación Principal

Este proyecto está completamente documentado. **Lee estos documentos en orden**:

### 1. **[IA_CONTEXT.md](./IA_CONTEXT.md)** ⭐ EMPEZAR AQUÍ
   - Objetivos del sistema
   - Filosofía de juego (posesión, triangulación, pressing)
   - Cómo razonan los agentes
   - Reglas de comportamiento
   - Función de valor y recompensas
   - **Este es el documento más importante del proyecto**

### 2. **[NODES_ARCHITECTURE.md](./NODES_ARCHITECTURE.md)**
   - Arquitectura de nodos de información
   - Contexto Global vs Local
   - Nodos fijos vs relacionales
   - State Vector V3 (200 dimensiones)
   - Responde: "¿Qué datos tenemos disponibles?"

### 3. **[ARCHITECTURE_REDESIGN.md](./ARCHITECTURE_REDESIGN.md)**
   - Arquitectura en 8 capas
   - Diseño técnico detallado
   - Algoritmos propuestos (Voronoi, A*, Transformers)
   - Métricas avanzadas

### 4. **[WORKFLOW.md](./WORKFLOW.md)**
   - Plan de desarrollo completo (12 semanas)
   - 6 Sprints detallados
   - Tareas específicas con tiempo estimado
   - Criterios de éxito por sprint
   - **Úsalo como roadmap de desarrollo**

### 5. **[BUGFIXES.md](./BUGFIXES.md)**
   - 9 bugs detectados (3 críticos, 4 altos, 2 medios)
   - Soluciones detalladas con código
   - Priorización clara
   - Tiempo estimado: 76 horas

---

## 🚀 Quick Start

### Comandos Docker

**Iniciar servidor + equipos + monitor**:
```bash
cd docker
docker compose up --build
```

**Recargar solo equipo izquierdo** (tras cambios de código):
```bash
docker compose down team_left
docker compose build team_left
docker compose up --build
```

**Conectar al monitor visual**:
- Usar TigerVNC Viewer
- Servidor: `localhost:5900`

---

## 📊 Estado Actual

### ✅ Componentes Implementados (68%)

- [x] FSM básico con 5 estados
- [x] Localización por triangulación
- [x] Predicción de balón (física simple)
- [x] Blackboard para coordinación
- [x] PassEvaluator con scoring multi-factor
- [x] Red neuronal Transformer (policy + params)
- [x] State vector de 128 dims
- [x] PPO trainer (con bugs)
- [x] Entrenamiento offline (behavioral cloning)
- [x] Docker compose completo

### ❌ Faltante (32%)

- [ ] Integración FSM ↔ ML (híbrido)
- [ ] Red de valor (value network) para PPO
- [ ] Voronoi completo
- [ ] Influence maps
- [ ] Pathfinding (A*, Theta*)
- [ ] Gegenpress
- [ ] Self-play
- [ ] State vector expandido (200 dims)
- [ ] Métricas en vivo

### 🔴 Bugs Críticos

1. **Desincronización estados FSM**: 5 estados vs 10 esperados
2. **PPO sin red crítica**: Usa max(probs) en vez de V(s)
3. **FSM no usa ML**: Modelo entrenado nunca se ejecuta

**Ver [BUGFIXES.md](./BUGFIXES.md) para detalles completos**

---

## 🎯 Próximos Pasos (Sprint 0)

**ACCIÓN INMEDIATA**: Arreglar bugs críticos

```bash
# 1. Crear branch
git checkout -b sprint-0-bugfixes

# 2. Arreglar Bug #1 (sincronización estados)
# Editar: src/tactics/hybrid_fsm.py
# Tiempo: 8 horas

# 3. Arreglar Bug #2 (PPO value network)
# Editar: src/ml/model_v2.py, src/ml/ppo_trainer.py
# Tiempo: 12 horas

# 4. Testing
python -m pytest tests/

# 5. Commit y PR
git add .
git commit -m "fix: sincronización estados FSM + value network PPO"
git push origin sprint-0-bugfixes
```

**Ver [WORKFLOW.md](./WORKFLOW.md) para plan completo de 12 semanas**

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│ 8. ACTUACIÓN      │ Comandos al servidor               │
├─────────────────────────────────────────────────────────┤
│ 7. PLANIFICACIÓN  │ Pathfinding, evitación             │
├─────────────────────────────────────────────────────────┤
│ 6. APRENDIZAJE    │ Red neuronal Transformer + PPO     │
├─────────────────────────────────────────────────────────┤
│ 5. COORDINACIÓN   │ Blackboard, intenciones            │
├─────────────────────────────────────────────────────────┤
│ 4. ESTRATEGIA     │ Plan de juego, formación 4-3-3     │
├─────────────────────────────────────────────────────────┤
│ 3. TÁCTICA        │ FSM + Behavior Tree                │
├─────────────────────────────────────────────────────────┤
│ 2. PREDICCIÓN     │ Balón, rivales, espacios           │
├─────────────────────────────────────────────────────────┤
│ 1. PERCEPCIÓN     │ Localización, visión               │
└─────────────────────────────────────────────────────────┘
```

**Ver diagrama completo en [ARCHITECTURE_REDESIGN.md](./ARCHITECTURE_REDESIGN.md)**

---

## 🧪 Testing

```bash
# Correr un partido de prueba
cd docker
docker compose up

# Logs de un agente específico
docker logs team_left | grep "\[7\]"  # Logs del jugador #7

# Métricas (cuando esté implementado)
python src/metrics/game_analyzer.py --game_log logs/game_001.rcg
```

---

## 📦 Estructura del Proyecto

```
RoboCup/
├── IA_CONTEXT.md                    ⭐ Especificación central
├── NODES_ARCHITECTURE.md            📐 Arquitectura de datos
├── WORKFLOW.md                      📅 Plan de desarrollo
├── BUGFIXES.md                      🐛 Bugs y soluciones
├── ARCHITECTURE_REDESIGN.md         🏗️ Diseño técnico
├── README.md                        📖 Este archivo
│
├── src/
│   ├── agent.py                     # Agente principal
│   ├── main.py                      # Entry point
│   │
│   ├── comunication/                # Cliente UDP + parser
│   ├── perception/                  # Localización
│   ├── prediction/                  # Predicciones
│   ├── coordination/                # Blackboard
│   ├── strategy/                    # Planificación estratégica
│   ├── tactics/                     # FSM + pases
│   ├── planning/                    # Pathfinding
│   ├── ml/                          # Redes neuronales + entrenamiento
│   ├── metrics/                     # Análisis de partidos
│   ├── modules/                     # State vector, actuators
│   └── util/                        # Utilidades
│
├── docker/
│   ├── docker-compose.yml           # Orquestación
│   ├── server/                      # Servidor RoboCup
│   ├── agents/                      # Dockerfile agentes
│   └── monitor/                     # Monitor visual
│
├── config/
│   └── requirements.txt             # Dependencias Python
│
└── tests/                           # Tests unitarios
```

---

## 🤝 Contribuir

1. Lee [IA_CONTEXT.md](./IA_CONTEXT.md) para entender la filosofía
2. Revisa [WORKFLOW.md](./WORKFLOW.md) para ver tareas disponibles
3. Toma una tarea de Sprint 0 o Sprint 1
4. Crea un branch: `git checkout -b feature/nombre-feature`
5. Implementa siguiendo los principios del IA_CONTEXT
6. Haz PR y pide revisión

### Reglas de Código

- **Primero funcionamiento, luego optimización**
- Todas las decisiones basadas en datos
- Testing continuo
- Documentar con docstrings
- Commits descriptivos

---

## 📈 Objetivos del Proyecto

### Objetivo Principal
**Maximizar posesión de balón (>65%) y minimizar pérdidas**

### Métricas de Éxito

| Métrica | Actual | Objetivo |
|---------|--------|----------|
| Posesión | ~35% | **65-75%** |
| Pases completados | ~40% | **85-90%** |
| Goles por partido | ~1-2 | **3-5** |
| Goles recibidos | ~3-4 | **0-1** |
| Tiempo de reacción | ~500ms | **<200ms** |
| Coordinación | Baja | **Alta (>0.8)** |

---

## 🎓 Recursos

- [RoboCup Official](https://www.robocup.org/)
- [Soccer Server Manual](https://github.com/rcsoccersim/rcssserver/wiki)
- [HELIOS Base](https://github.com/helios-base/helios-base) - Equipo top
- [PPO Paper](https://arxiv.org/abs/1707.06347)
- [Multi-Agent RL](https://arxiv.org/abs/1911.10635)

---

## 📞 Contacto

**Equipo**: [Tu equipo]  
**Universidad**: [Tu universidad]  
**Año**: 2026

---

**Este proyecto es académico para competencia RoboCup 2D Soccer Simulation League**