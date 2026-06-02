# WORKFLOW DE DESARROLLO — RoboCup 2D Soccer Simulation

**Estado Actual**: 68% completado  
**Objetivo**: Sistema funcional y competitivo  
**Timeline**: 12 semanas (3 meses)

---

## 📊 RESUMEN EJECUTIVO

### Sprints Planificados

| Sprint | Duración | Objetivo | Estado |
|--------|----------|----------|--------|
| **Sprint 0** | 1 semana | Bugfixes críticos | 🔴 PENDIENTE |
| **Sprint 1** | 2 semanas | Integración ML-FSM + Pases | 🔴 PENDIENTE |
| **Sprint 2** | 2 semanas | Control espacial + Nodos relacionales | 🔴 PENDIENTE |
| **Sprint 3** | 2 semanas | Coordinación + Pressing | 🔴 PENDIENTE |
| **Sprint 4** | 3 semanas | Entrenamiento + Self-play | 🔴 PENDIENTE |
| **Sprint 5** | 2 semanas | Métricas + Optimización | 🔴 PENDIENTE |

---

## 🔥 SPRINT 0: BUGFIXES CRÍTICOS (Semana 1)

**Objetivo**: Eliminar bugs que impiden funcionamiento básico

### Tareas

#### 1. BUG #1: Sincronización Estados FSM 🔴 CRÍTICO
**Archivo**: `src/tactics/hybrid_fsm.py` + `src/modules/state_vector_v2.py`

**Problema**: 
- FSM define 5 estados
- State vector espera 10 estados
- Mismatch causa codificación incorrecta

**Solución**:
```python
# En hybrid_fsm.py
class State(Enum):
    WAIT = 0
    SEARCH_BALL = 1
    MOVE_TO_BALL = 2
    KICK_BALL = 3
    GO_TO_POSITION = 4
    DEAD_BALL = 5
    SUPPORT = 6
    PRESS = 7
    DRIBBLE = 8
    COVER_LANE = 9
```

**Pasos**:
1. [ ] Expandir enum `State` en `hybrid_fsm.py`
2. [ ] Implementar lógica para nuevos estados (SUPPORT, PRESS, DRIBBLE, COVER_LANE)
3. [ ] Agregar transiciones de estado
4. [ ] Verificar en `state_vector_v2.py` que mapping esté correcto
5. [ ] Testing: generar state vector y verificar encoding

**Tiempo estimado**: 8 horas

---

#### 2. BUG #2: PPO sin Red Crítica 🔴 CRÍTICO
**Archivo**: `src/ml/model_v2.py` + `src/ml/ppo_trainer.py`

**Problema**: 
- PPO usa `max(action_probs)` como valor del estado
- Incorrecto matemáticamente
- Entrenamiento no converge

**Solución**:
```python
# En model_v2.py
class TacticalBrain:
    def __init__(self):
        # ... existente ...
        
        # AGREGAR: Value Head
        self.value_head = keras.Sequential([
            layers.Dense(64, activation='relu'),
            layers.Dense(32, activation='relu'),
            layers.Dense(1, activation='linear', name='value')
        ])
    
    def call(self, inputs):
        x = self.embedding(inputs)
        x = self.transformer_block_1(x)
        x = self.transformer_block_2(x)
        
        # Policy
        action_probs = self.action_head(x)
        action_params = self.param_head(x)
        
        # Value (NUEVO)
        value = self.value_head(x)
        
        return action_probs, action_params, value
```

**Pasos**:
1. [ ] Agregar `value_head` a `TacticalBrain`
2. [ ] Modificar `call()` para retornar 3 outputs
3. [ ] Actualizar `ppo_trainer.py` para usar `value` real
4. [ ] Implementar cálculo de ventaja correcto: `A(s,a) = Q(s,a) - V(s)`
5. [ ] Agregar loss de valor: `value_loss = MSE(V(s), returns)`
6. [ ] Testing: verificar que gradientes fluyan correctamente

**Tiempo estimado**: 12 horas

---

#### 3. BUG #3: Renombrar/Implementar EKF Real 🟡 ALTO
**Archivo**: `src/perception/localizer.py`

**Problema**: 
- Se llama "EKFLocalizer" pero no es EKF
- Solo hace triangulación simple

**Solución (opción rápida)**:
```python
# Renombrar clase
class TriangulationLocalizer:  # antes: EKFLocalizer
    """
    Localizador basado en triangulación de flags.
    Usa promedio ponderado de múltiples observaciones.
    """
    # ... código existente ...
```

**Pasos**:
1. [ ] Renombrar clase a `TriangulationLocalizer`
2. [ ] Actualizar imports en `agent.py`
3. [ ] Actualizar docstrings para reflejar algoritmo real
4. [ ] (Opcional) Implementar EKF real si hay tiempo

**Tiempo estimado**: 2 horas (renombrar) o 16 horas (implementar EKF real)

---

#### 4. BUG #4: Flags Duplicados 🟡 MEDIO
**Archivo**: `src/perception/localizer.py`

**Problema**: 
- `"fct"` aparece dos veces en diccionario
- Una entrada sobrescribe la otra

**Solución**:
```python
# Revisar y eliminar duplicados
FLAGS = {
    # ... revisar líneas 13-35 ...
}
```

**Pasos**:
1. [ ] Identificar entradas duplicadas
2. [ ] Eliminar duplicados
3. [ ] Verificar coordenadas correctas de flags

**Tiempo estimado**: 1 hora

---

#### 5. BUG #5: Offside Hardcodeado 🟡 MEDIO
**Archivo**: `src/modules/state_vector_v2.py:84`

**Problema**: 
```python
is_offside = 0.0  # TODO: calcular offside real
```

**Solución**:
```python
def calculate_offside(self_x, self_y, side, opponents, ball_x):
    """
    Offside: estar más cerca del arco rival que el penúltimo defensor
    cuando el balón está en campo rival
    """
    if side == "l":
        if self_x < ball_x:  # Atrás del balón
            return False
        
        # Obtener posición del penúltimo defensor rival
        opponent_xs = sorted([opp['x'] for opp in opponents])
        if len(opponent_xs) >= 2:
            second_last_defender = opponent_xs[-2]
            return self_x > second_last_defender
    else:  # side == "r"
        if self_x > ball_x:
            return False
        opponent_xs = sorted([opp['x'] for opp in opponents], reverse=True)
        if len(opponent_xs) >= 2:
            second_last_defender = opponent_xs[-2]
            return self_x < second_last_defender
    
    return False
```

**Pasos**:
1. [ ] Implementar función `calculate_offside()`
2. [ ] Integrar en state_vector_v2.py
3. [ ] Testing con casos conocidos

**Tiempo estimado**: 4 horas

---

### Criterios de Éxito Sprint 0

- ✅ Todos los bugs críticos (#1, #2) resueltos
- ✅ State vector codifica correctamente estados FSM
- ✅ PPO tiene red de valor funcional
- ✅ Sistema compila sin errores
- ✅ Agentes pueden jugar un partido completo sin crashes

---

## 🔧 SPRINT 1: INTEGRACIÓN ML-FSM + SISTEMA DE PASES (Semanas 2-3)

**Objetivo**: Conectar ML con FSM y sistema de pases funcional

### Tareas

#### 1.1 Integrar PassEvaluator con FSM 🔴 CRÍTICO
**Archivos**: `src/tactics/hybrid_fsm.py`, `src/tactics/pass_evaluation.py`

**Cambios**:
```python
# En hybrid_fsm.py, estado KICK_BALL
def _kick_ball_step(self):
    if not self.perception.is_ball_kickable():
        return self._transition_to(State.MOVE_TO_BALL)
    
    # NUEVO: Usar PassEvaluator
    from tactics.pass_evaluation import PassEvaluator
    from coordination.blackboard import Blackboard
    
    bb = Blackboard()
    teammates = bb.get_all_agents_positions()
    opponents = bb.get_all_opponents()
    
    passer_pos = (self.perception.state.self_x, self.perception.state.self_y)
    
    evaluator = PassEvaluator(ball_predictor=self.ball_predictor)
    best_pass = evaluator.evaluate(passer_pos, self._side, teammates, opponents)
    
    if best_pass and best_pass.score > 0.6:
        # Ejecutar pase
        angle = self._calculate_pass_angle(best_pass.x, best_pass.y)
        power = self._calculate_pass_power(best_pass.distance)
        return actuators.kick(power, angle)
    else:
        # No hay buen pase, driblar o girar
        return self._dribble_or_turn()
```

**Pasos**:
1. [ ] Modificar `_kick_ball_step()` para usar PassEvaluator
2. [ ] Implementar `_dribble_or_turn()` como fallback
3. [ ] Agregar logging de decisiones de pase
4. [ ] Testing: verificar que se prefieran pases seguros

**Tiempo estimado**: 10 horas

---

#### 1.2 Crear Hybrid Controller (FSM + ML) 🔴 CRÍTICO
**Archivo**: `src/tactics/hybrid_controller.py` (NUEVO)

**Diseño**:
```python
class HybridController:
    """
    Controlador que decide cuándo usar FSM y cuándo usar ML.
    
    FSM (reglas):
      - Portero
      - Set pieces
      - Emergencias
    
    ML (aprendido):
      - Decisión de pases
      - Posicionamiento de apoyo
      - Situaciones ambiguas
    """
    
    def __init__(self, fsm, neural_net):
        self.fsm = fsm
        self.nn = neural_net
        self.use_ml_for_states = {
            State.KICK_BALL,    # ML ayuda a decidir pase vs dribble
            State.SUPPORT,      # ML encuentra mejor posición
            State.GO_TO_POSITION  # ML optimiza ruta
        }
    
    def decide(self, context_global, context_local):
        current_state = self.fsm.current_state
        
        # Casos deterministas (FSM)
        if self._is_deterministic_situation(context_local):
            return self.fsm.step()
        
        # Casos donde ML ayuda
        if current_state in self.use_ml_for_states:
            state_vector = build_state_vector(context_global, context_local)
            action_probs, params, value = self.nn.predict(state_vector)
            
            # Validar seguridad
            if self._is_action_safe(action_probs, params, context_local):
                return self._execute_ml_action(action_probs, params)
            else:
                # Fallback a FSM
                return self.fsm.step()
        
        # Default: FSM
        return self.fsm.step()
```

**Pasos**:
1. [ ] Crear archivo `hybrid_controller.py`
2. [ ] Implementar lógica de decisión FSM vs ML
3. [ ] Integrar con `agent.py`
4. [ ] Testing: verificar que ML se use cuando corresponde

**Tiempo estimado**: 16 horas

---

#### 1.3 Implementar Estado SUPPORT 🟡 ALTO
**Archivo**: `src/tactics/hybrid_fsm.py`

**Objetivo**: Agentes sin balón se mueven a posiciones de apoyo

**Lógica**:
```python
def _support_step(self):
    """
    Moverse a posición de apoyo para recibir pase.
    Formar triángulo con poseedor del balón.
    """
    bb = Blackboard()
    ball_owner_pos = bb.get_ball_owner_position()
    
    if not ball_owner_pos:
        return self._transition_to(State.GO_TO_POSITION)
    
    # Encontrar mejor posición de apoyo
    support_pos = self._calculate_support_position(ball_owner_pos)
    
    # Moverse allí
    return self._move_to_target(support_pos)

def _calculate_support_position(self, ball_owner_pos):
    """
    Posición de apoyo:
      - 5-15m del poseedor
      - En espacio libre (Voronoi)
      - Línea de pase limpia
    """
    # Usar Voronoi para encontrar espacios libres
    from tactics.voronoi_control import find_free_spaces
    free_spaces = find_free_spaces(self.perception.state.self_x, 
                                     self.perception.state.self_y)
    
    # Filtrar espacios en rango 5-15m
    valid_spaces = [s for s in free_spaces 
                    if 5 < distance(s, ball_owner_pos) < 15]
    
    if valid_spaces:
        # Elegir el que maximiza ángulo de pase
        return max(valid_spaces, key=lambda s: pass_angle_quality(s, ball_owner_pos))
    else:
        # Default: moverse perpendicular al poseedor
        return ball_owner_pos + perpendicular_vector(10.0)
```

**Pasos**:
1. [ ] Implementar `_support_step()`
2. [ ] Implementar `_calculate_support_position()`
3. [ ] Agregar transición: `KICK_BALL` → `SUPPORT` para receptores
4. [ ] Testing: verificar formación de triángulos

**Tiempo estimado**: 8 horas

---

#### 1.4 Sistema de Triangulación Automática 🟡 ALTO
**Archivo**: `src/coordination/triangulation.py` (NUEVO)

**Objetivo**: Mantener 2+ opciones de pase siempre

**Diseño**:
```python
class TriangulationManager:
    """
    Gestiona formación de triángulos de pase.
    """
    
    def assign_support_roles(self, ball_owner_unum):
        """
        Asigna 2-3 agentes como apoyo del poseedor.
        """
        bb = Blackboard()
        ball_pos = bb.ball["pos"]
        
        # Encontrar agentes más cercanos (excluir poseedor)
        nearby = bb.get_agents_in_range(ball_pos, max_dist=20.0)
        nearby = [a for a in nearby if a.unum != ball_owner_unum]
        nearby = sorted(nearby, key=lambda a: distance(a.pos, ball_pos))
        
        # Asignar roles de apoyo
        for i, agent in enumerate(nearby[:3]):
            if i == 0:
                # Primer apoyo: posición ofensiva
                agent.intent = "support_offensive"
            elif i == 1:
                # Segundo apoyo: posición lateral
                agent.intent = "support_lateral"
            elif i == 2:
                # Tercer apoyo: posición defensiva (seguridad)
                agent.intent = "support_defensive"
    
    def validate_triangulation(self, ball_owner_pos):
        """
        Verifica que haya ≥2 opciones de pase.
        """
        bb = Blackboard()
        support_agents = bb.get_agents_with_intent("support_*")
        
        valid_supports = []
        for agent in support_agents:
            if self._has_clean_pass_line(ball_owner_pos, agent.pos):
                valid_supports.append(agent)
        
        return len(valid_supports) >= 2
```

**Pasos**:
1. [ ] Crear `triangulation.py`
2. [ ] Implementar `TriangulationManager`
3. [ ] Integrar con `agent.py` (llamar cada ciclo)
4. [ ] Testing: contar triángulos formados por partido

**Tiempo estimado**: 10 horas

---

### Criterios de Éxito Sprint 1

- ✅ PassEvaluator integrado con FSM
- ✅ Agentes usan pases evaluados (no aleatorios)
- ✅ Estado SUPPORT implementado
- ✅ Triangulación funciona (≥2 opciones de pase)
- ✅ Hybrid Controller decide cuándo usar ML
- ✅ Tasa de pases completados >70%

---

## 🌐 SPRINT 2: NODOS RELACIONALES + CONTROL ESPACIAL (Semanas 4-5)

**Objetivo**: Implementar representación completa de contexto global/local

### Tareas

#### 2.1 Expandir State Vector con Nodos Relacionales 🔴 CRÍTICO
**Archivo**: `src/modules/state_vector_v3.py` (NUEVO)

**Diseño**: Pasar de 128 → 200 dimensiones

**Nuevos features**:
```python
# [128-137] LÍNEAS DE PASE (10 features)
- num_passing_lanes: int          # Cantidad de pases disponibles
- best_pass_angle: float          # Ángulo del mejor pase
- second_best_pass_score: float   # Segundo mejor pase
- pass_triangle_quality: float    # ¿Hay triangulación?
- support_positions_count: int    # Compañeros en apoyo
- avg_pass_distance: float        # Distancia promedio de pases
- risky_passes_count: int         # Pases con riesgo >0.7
- safe_passes_count: int          # Pases con riesgo <0.3
- forward_passes_available: int   # Pases hacia adelante
- backward_passes_available: int  # Pases hacia atrás

# [138-147] ESPACIOS LIBRES (10 features)
- largest_free_space_dir: float   # Dirección del espacio más grande
- largest_free_space_dist: float  # Distancia al espacio
- voronoi_cell_area: float        # Área de Voronoi del agente
- pressure_index: float           # Presión rival cercana (0-1)
- isolation_index: float          # Lejos de compañeros (0-1)
- free_space_front: float         # Espacio libre adelante
- free_space_back: float
- free_space_left: float
- free_space_right: float
- optimal_dribble_direction: float

# [148-157] RELACIONES DE MARCAJE (10 features)
- am_i_marked: bool               # ¿Estoy marcado?
- closest_marker_dist: float      # Distancia al marcador
- marker_angle: float             # Ángulo del marcador
- teammates_marked_count: int     # Compañeros marcados
- rivals_unmarked_count: int      # Rivales sin marca
- my_marking_target: int          # ¿A quién marco? (unum o 0)
- marking_effectiveness: float    # Qué tan bien marco
- nearest_rival_to_ball: float    # Distancia rival-balón
- am_i_nearest_defender: bool
- defensive_line_position: float  # Posición en línea defensiva

# [158-167] COORDINACIÓN DE EQUIPO (10 features)
- team_compactness: float         # Distancia promedio entre compañeros
- team_width: float               # Amplitud del equipo
- team_depth: float               # Profundidad del equipo
- formation_integrity: float      # ¿Mantenemos formación?
- num_agents_attacking: int
- num_agents_defending: int
- num_agents_pressing: int
- blackboard_sync_lag: int        # Ciclos desde última actualización
- intent_conflicts: int           # Conflictos de intención
- coordination_quality: float     # Índice de coordinación

# [168-177] CONTEXTO RIVAL (10 features)
- opponent_formation: one-hot(3)  # 4-4-2, 4-3-3, unknown
- opponent_pressing: bool
- opponent_possession_time: float # % posesión rival
- opponent_avg_pass_distance: float
- opponent_in_penalty_area: int   # Rivales en nuestra área
- opponent_defensive_intensity: float
- opponent_offensive_threat: float
- opponent_stamina_estimated: float
- opponent_compactness: float
- opponent_exploitable_space: float

# [178-187] PREDICCIONES AVANZADAS (10 features)
- ball_intercept_feasible: bool   # ¿Puedo interceptar?
- ball_intercept_cycles: int      # Ciclos para interceptar
- rival_intercept_risk: float     # Riesgo de que rival intercepte
- next_ball_owner_predicted: int  # unum predicho
- goal_probability_us: float      # P(gol) si disparamos
- goal_probability_them: float    # P(gol) rival
- counterattack_risk: float       # Riesgo de contraataque
- possession_loss_risk: float     # Riesgo de perder balón
- optimal_action_value: float     # Valor Q máximo
- state_value_estimate: float     # V(s) de red neuronal

# [188-199] RESERVADO (12 features para expansión futura)
```

**Pasos**:
1. [ ] Crear `state_vector_v3.py`
2. [ ] Implementar cálculo de cada feature
3. [ ] Integrar con Blackboard (contexto global)
4. [ ] Actualizar `model_v2.py` para aceptar 200 dims
5. [ ] Testing: verificar normalización de features

**Tiempo estimado**: 20 horas

---

#### 2.2 Completar Voronoi Control 🟡 ALTO
**Archivo**: `src/tactics/voronoi_control.py`

**Objetivo**: Control dinámico de espacios

**Implementación**:
```python
from scipy.spatial import Voronoi
import numpy as np

class VoronoiController:
    def compute_voronoi_cells(self, team_positions, opponent_positions):
        """
        Calcula diagrama de Voronoi del campo.
        """
        all_positions = team_positions + opponent_positions
        points = np.array(all_positions)
        
        vor = Voronoi(points)
        
        cells = {}
        for i, pos in enumerate(team_positions):
            region_index = vor.point_region[i]
            region = vor.regions[region_index]
            
            if -1 not in region and len(region) > 0:
                polygon = [vor.vertices[j] for j in region]
                area = self._polygon_area(polygon)
                cells[i] = {
                    "area": area,
                    "vertices": polygon,
                    "center": pos
                }
        
        return cells
    
    def find_free_spaces(self, voronoi_cells, my_unum):
        """
        Identifica espacios libres grandes (oportunidades).
        """
        my_cell = voronoi_cells.get(my_unum)
        if not my_cell:
            return []
        
        # Espacios libres = celdas grandes sin rivales cerca
        free_spaces = []
        for unum, cell in voronoi_cells.items():
            if cell["area"] > 50:  # >50 m²
                # Verificar que no haya rivales cerca
                if self._is_space_safe(cell["center"]):
                    free_spaces.append(cell)
        
        return free_spaces
```

**Pasos**:
1. [ ] Instalar scipy: `pip install scipy`
2. [ ] Implementar `VoronoiController`
3. [ ] Integrar con Blackboard (actualizar cada 5 ciclos)
4. [ ] Usar en state_vector_v3 (features 138-147)
5. [ ] Testing: visualizar diagramas de Voronoi

**Tiempo estimado**: 12 horas

---

#### 2.3 Implementar Influence Maps 🟢 MEDIO
**Archivo**: `src/tactics/influence_maps.py`

**Objetivo**: Mapas de influencia para evaluar zonas

**Pasos**:
1. [ ] Crear grid 21x14 (5m x 5m)
2. [ ] Calcular influencia aliada y rival
3. [ ] Integrar con state_vector_v3
4. [ ] Testing: visualizar mapas de calor

**Tiempo estimado**: 10 horas

---

### Criterios de Éxito Sprint 2

- ✅ State vector expandido a 200 dimensiones
- ✅ Voronoi cells calculadas correctamente
- ✅ Features relacionales poblados
- ✅ Agentes usan información de espacios libres
- ✅ Sistema identifica oportunidades tácticas

---

## 🤝 SPRINT 3: COORDINACIÓN + PRESSING (Semanas 6-7)

**Objetivo**: Coordinación multiagente y recuperación de balón

### Tareas

#### 3.1 Implementar Gegenpress 🔴 CRÍTICO
**Archivo**: `src/strategy/pressing.py` (NUEVO)

**Diseño** (según IA_CONTEXT.md):
```python
class PressingSystem:
    def activate_pressing(self, ball_lost_pos, cycle):
        """
        Activa pressing tras pérdida de balón.
        """
        bb = Blackboard()
        
        # Solo si perdimos en campo rival
        if ball_lost_pos[0] > 0:  # mitad ofensiva
            # Fase 1: Choque inmediato (ciclos 0-3)
            if cycle - self.loss_cycle <= 3:
                self._assign_immediate_press()
            
            # Fase 2: Presión organizada (ciclos 4-10)
            elif cycle - self.loss_cycle <= 10:
                self._assign_organized_press()
            
            # Fase 3: Repliegue (ciclos 11+)
            else:
                self._deactivate_pressing()
    
    def _assign_immediate_press(self):
        bb = Blackboard()
        ball_pos = bb.ball["pos"]
        
        # First presser: más cercano
        nearest = bb.get_nearest_to_ball()
        nearest.intent = {"action": "press", "priority": 1.0}
        
        # Second presser: segundo más cercano
        second = bb.get_second_nearest()
        second.intent = {"action": "cover_lane", "priority": 0.9}
        
        # Resto: comprimir espacio
        for agent in bb.get_agents_in_range(ball_pos, 20):
            if agent.unum not in [nearest.unum, second.unum]:
                agent.intent = {"action": "compress", "priority": 0.7}
```

**Pasos**:
1. [ ] Crear `pressing.py`
2. [ ] Implementar sistema de 3 fases
3. [ ] Integrar con `strategic_planner.py`
4. [ ] Implementar estado `PRESS` en FSM
5. [ ] Testing: medir tasa de recuperación

**Tiempo estimado**: 14 horas

---

#### 3.2 Sistema de Roles Dinámicos 🟡 ALTO
**Archivo**: `src/coordination/role_manager.py` (NUEVO)

**Objetivo**: Roles se asignan dinámicamente según contexto

**Pasos**:
1. [ ] Crear `RoleManager`
2. [ ] Asignar responsabilidades (ball_owner, support, press, etc.)
3. [ ] Resolver conflictos de roles
4. [ ] Testing: verificar que solo 1 agente vaya al balón

**Tiempo estimado**: 10 horas

---

#### 3.3 Protocolo de Comunicación Say/Hear 🟢 MEDIO
**Archivo**: `src/coordination/communication_protocol.py` (NUEVO)

**Objetivo**: Comunicación estructurada entre agentes

**Mensajes**:
```python
# Formato compacto (max 10 chars)
"i5"     # intent: "voy al balón" (action_id=5)
"p142"   # pase a posición x=14.2
"m3"     # marco rival #3
"h"      # "ayuda" / "necesito apoyo"
```

**Pasos**:
1. [ ] Definir protocolo de mensajes
2. [ ] Implementar encoding/decoding
3. [ ] Integrar con Blackboard
4. [ ] Testing: verificar que mensajes se reciban

**Tiempo estimado**: 8 horas

---

### Criterios de Éxito Sprint 3

- ✅ Gegenpress funciona (recuperación <5 ciclos)
- ✅ Roles dinámicos asignados correctamente
- ✅ No hay conflictos (2+ agentes al balón)
- ✅ Comunicación entre agentes funcional
- ✅ Tasa de recuperación >60%

---

## 🧠 SPRINT 4: ENTRENAMIENTO + SELF-PLAY (Semanas 8-10)

**Objetivo**: Entrenar agentes con RL avanzado

### Tareas

#### 4.1 Arreglar PPO Trainer (ya hecho en Sprint 0)
- ✅ Red de valor implementada
- ✅ Ventaja calculada correctamente
- ✅ Loss de valor agregado

#### 4.2 Implementar Self-Play System 🔴 CRÍTICO
**Archivo**: `src/ml/self_play.py`

**Diseño**:
```python
class SelfPlayLeague:
    """
    Sistema de auto-juego con pool de versiones.
    """
    
    def __init__(self, pool_size=10):
        self.pool = []  # Lista de checkpoints
        self.current_version = 0
        self.elo_ratings = {}
    
    def add_checkpoint(self, model_path, version):
        """Agrega nueva versión al pool."""
        self.pool.append({
            "path": model_path,
            "version": version,
            "elo": 1500  # ELO inicial
        })
        if len(self.pool) > self.pool_size:
            self.pool.pop(0)  # Eliminar versión más vieja
    
    def select_opponent(self):
        """
        Selecciona oponente según distribución:
          - 50% versión actual
          - 30% versión N-1
          - 20% versión N-2
        """
        if len(self.pool) == 0:
            return None
        
        rand = random.random()
        if rand < 0.5 and len(self.pool) >= 1:
            return self.pool[-1]  # Versión actual
        elif rand < 0.8 and len(self.pool) >= 2:
            return self.pool[-2]  # N-1
        elif len(self.pool) >= 3:
            return self.pool[-3]  # N-2
        else:
            return random.choice(self.pool)
    
    def update_elo(self, winner_version, loser_version, score_diff):
        """Actualiza ratings ELO tras partido."""
        K = 32  # Factor K
        expected = 1 / (1 + 10 ** ((loser_elo - winner_elo) / 400))
        winner_elo += K * (1 - expected)
        loser_elo -= K * (1 - expected)
```

**Pasos**:
1. [ ] Crear `self_play.py`
2. [ ] Implementar pool de versiones
3. [ ] Sistema ELO para ranking
4. [ ] Script para correr partidos automáticos
5. [ ] Testing: verificar que ELO converge

**Tiempo estimado**: 16 horas

---

#### 4.3 Curriculum Learning 🟡 ALTO
**Archivo**: `src/ml/curriculum.py` (NUEVO)

**Niveles**:
```python
CURRICULUM = [
    {
        "level": 1,
        "name": "Passing Drills",
        "num_agents": 3,
        "opponents": 0,
        "duration": 1000,
        "objective": "90% pass completion"
    },
    {
        "level": 2,
        "name": "1v1",
        "num_agents": 1,
        "opponents": 1,
        "duration": 500,
        "objective": "Maintain possession"
    },
    {
        "level": 3,
        "name": "3v2",
        "num_agents": 3,
        "opponents": 2,
        "duration": 1000,
        "objective": "Triangulation"
    },
    # ... hasta 11v11
]
```

**Pasos**:
1. [ ] Definir 6 niveles de curriculum
2. [ ] Scripts para lanzar cada nivel
3. [ ] Métricas de progreso
4. [ ] Transfer learning entre niveles

**Tiempo estimado**: 12 horas

---

#### 4.4 Reward Shaping Avanzado (ya existe)
**Archivo**: `src/ml/reward_shaping.py`

**Mejoras**:
1. [ ] Ajustar pesos según IA_CONTEXT.md
2. [ ] Agregar recompensa por triangulación
3. [ ] Penalizar despejes innecesarios
4. [ ] Testing: verificar que recompensas tengan sentido

**Tiempo estimado**: 6 horas

---

### Criterios de Éxito Sprint 4

- ✅ Self-play funcional con pool de versiones
- ✅ Curriculum de 6 niveles implementado
- ✅ Entrenamiento con recompensas alineadas a IA_CONTEXT
- ✅ Modelo mejora consistentemente (ELO sube)
- ✅ Checkpoint cada 1000 partidos

---

## 📊 SPRINT 5: MÉTRICAS + OPTIMIZACIÓN (Semanas 11-12)

**Objetivo**: Métricas en vivo y optimización final

### Tareas

#### 5.1 Completar Game Analyzer 🟢 MEDIO
**Archivo**: `src/metrics/game_analyzer.py`

**Métricas a calcular**:
- Posesión de balón (%)
- Tasa de pases completados
- Distancia promedio de pases
- Presiones exitosas
- Coordinación (índice)
- Stamina promedio
- Zonas controladas

**Pasos**:
1. [ ] Implementar tracking de todas las métricas
2. [ ] Logging a archivo CSV
3. [ ] Visualización en tiempo real (opcional)
4. [ ] Testing: validar métricas con partidos conocidos

**Tiempo estimado**: 10 horas

---

#### 5.2 Heatmaps y Visualización 🟢 BAJO
**Archivo**: `src/metrics/heatmap_generator.py` (NUEVO)

**Pasos**:
1. [ ] Tracking de posiciones por ciclo
2. [ ] Generación de heatmaps con matplotlib
3. [ ] Exportar imágenes

**Tiempo estimado**: 8 horas

---

#### 5.3 Profiling y Optimización 🟡 ALTO
**Objetivo**: Reducir tiempo de decisión a <50ms

**Pasos**:
1. [ ] Profiling con cProfile
2. [ ] Identificar cuellos de botella
3. [ ] Optimizar loops críticos
4. [ ] Cache de cálculos repetidos (Voronoi, etc.)
5. [ ] Testing: medir latencia promedio

**Tiempo estimado**: 12 horas

---

### Criterios de Éxito Sprint 5

- ✅ Métricas en vivo funcionales
- ✅ Heatmaps generados automáticamente
- ✅ Tiempo de decisión <50ms (avg)
- ✅ Sistema estable en partidos largos
- ✅ Documentación completa

---

## 📈 MÉTRICAS DE PROGRESO

### KPIs por Sprint

| Sprint | KPI | Objetivo | Medición |
|--------|-----|----------|----------|
| 0 | Bugs críticos resueltos | 5/5 | Manual |
| 1 | Tasa pases completados | >70% | game_analyzer |
| 2 | Features estado completos | 200/200 | Code review |
| 3 | Tasa recuperación | >60% | game_analyzer |
| 4 | ELO self-play | >1600 | self_play.py |
| 5 | Latencia decisión | <50ms | profiling |

---

## 🎯 DEFINICIÓN DE "HECHO" (DoD)

Una tarea está completa cuando:

1. ✅ Código implementado y committed
2. ✅ Sin errores de sintaxis
3. ✅ Pruebas básicas pasadas
4. ✅ Integrado con sistema existente
5. ✅ Documentado (docstrings mínimos)
6. ✅ Revisado por al menos 1 compañero

---

## 📝 TRACKING DE PROGRESO

### Herramientas

- **GitHub Issues**: 1 issue por tarea
- **GitHub Projects**: Board Kanban
- **Git Branches**: 1 branch por sprint
- **Pull Requests**: Revisión de código

### Reuniones

- **Daily standup** (5 min): ¿Qué hice? ¿Qué haré? ¿Blockers?
- **Sprint review** (1h): Demo de trabajo completado
- **Sprint retro** (30min): ¿Qué mejorar?

---

## 🚀 SIGUIENTE PASO INMEDIATO

**ACCIÓN**: Iniciar Sprint 0 - Bugfix #1 (sincronización estados FSM)

**Comando**:
```bash
git checkout -b sprint-0-bugfixes
```

**Archivo a editar**: `src/tactics/hybrid_fsm.py`

---

**Este workflow es el plan de trabajo oficial del proyecto. Actualizar según progreso real.**
