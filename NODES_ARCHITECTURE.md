# ARQUITECTURA DE NODOS — Contexto Global y Local

**Propósito**: Definir todos los nodos de información (fijos y relacionales) para toma de decisiones  
**Fecha**: Junio 1, 2026

---

## 📋 PROBLEMA IDENTIFICADO

### Situación Actual
El sistema solo ve **4 compañeros** y **4 rivales** más cercanos, perdiendo información crítica:
- Ignora hasta 6 compañeros y 7 rivales
- No modela relaciones (líneas de pase, marcajes, espacios)
- Decisiones miopes (solo proximidad, no valor táctico)

### Objetivo
Representar **TODOS** los datos relevantes en contextos estructurados:
- **Contexto Global**: Información compartida (Blackboard)
- **Contexto Local**: Información del agente individual

---

## 🌍 CONTEXTO GLOBAL (Blackboard Compartido)

### Estructura de Datos
```python
class GlobalContext:
    """
    Información compartida entre todos los agentes.
    Actualizada cada ciclo por todos.
    """
    
    def __init__(self):
        self.match_context = MatchContext()
        self.ball = BallContext()
        self.team = TeamContext()
        self.opponents = OpponentContext()
        self.spatial = SpatialContext()
        self.tactical = TacticalContext()
```

---

### 1. MATCH CONTEXT (Contexto del Partido)

**Nodos Fijos**:
```python
{
    "time": int,                    # Ciclo actual (0-6000)
    "time_remaining": int,          # Ciclos restantes
    "half": 1 | 2,                  # Primera o segunda parte
    
    "score_left": int,              # Goles equipo izquierdo
    "score_right": int,             # Goles equipo derecho
    "score_diff": int,              # Diferencia (nuestra perspectiva)
    
    "play_mode": PlayMode,          # kick_off, free_kick, etc.
    "last_play_mode": PlayMode,     # Modo anterior
    "play_mode_changed_cycle": int, # Cuándo cambió
    
    "goals_scored_us": int,         # Total goles nuestros
    "goals_conceded": int,          # Total goles recibidos
    
    "game_phase": str,              # "opening", "mid_game", "closing"
    "tactical_situation": str       # "winning", "losing", "tied"
}
```

**Derivados** (calculados):
```python
{
    "time_pressure": float,         # 0-1 (qué tan urgente)
    "need_to_score": bool,          # Vamos perdiendo cerca del final
    "need_to_defend": bool,         # Vamos ganando cerca del final
    "is_critical_moment": bool      # Últimos 500 ciclos
}
```

---

### 2. BALL CONTEXT (Contexto del Balón)

**Nodos Fijos**:
```python
{
    "pos": (x, y),                  # Posición absoluta
    "vel": (vx, vy),                # Velocidad
    "speed": float,                 # |vel|
    
    "visible_by": [unum_list],      # Quién lo ve
    "visible_count": int,           # Cuántos lo ven
    
    "owner_team": "left" | "right" | None,
    "owner_unum": int | None,       # Quién lo tiene
    "owner_pos": (x, y) | None,     # Posición del dueño
    
    "last_touch_cycle": int,        # Último ciclo con contacto
    "last_touch_team": str,
    "last_touch_unum": int,
    
    "is_kickable_by": [unum_list],  # Quién puede patearlo
    "is_in_play": bool,             # En juego o detenido
}
```

**Derivados** (calculados):
```python
{
    "zone": str,                    # "defensive", "midfield", "offensive"
    "third": int,                   # 1, 2, o 3 (tercio del campo)
    
    "predicted_pos_t5": (x, y),     # Predicción 5 ciclos
    "predicted_pos_t10": (x, y),    # Predicción 10 ciclos
    
    "will_go_out": bool,            # Va a salir del campo
    "will_go_to_goal": bool,        # Va directo al arco
    "goal_side": "left" | "right",  # A qué arco
    
    "nearest_agent_dist": float,    # Distancia al agente más cercano
    "nearest_agent_unum": int,
    "nearest_opponent_dist": float,
    "nearest_opponent_id": int,
    
    "in_contested_area": bool,      # Disputa entre varios
    "time_until_out": int | None,   # Ciclos hasta salir
    
    "possession_duration": int      # Ciclos que el equipo actual lo tiene
}
```

---

### 3. TEAM CONTEXT (Contexto del Equipo Propio)

**Estructura**:
```python
{
    "agents": {
        1: AgentNode,  # Portero
        2: AgentNode,  # Defensor derecho
        # ... 11 agentes
    },
    
    "formation": {
        "name": "4-3-3" | "4-4-2" | etc.,
        "defensive_line": [2, 3, 4, 5],
        "midfield_line": [6, 7, 8],
        "offensive_line": [9, 10, 11],
        "compactness": float,       # Distancia promedio entre jugadores
        "width": float,             # Amplitud del equipo
        "depth": float              # Profundidad
    },
    
    "roles": {
        "ball_owner": unum | None,
        "supporters": [unum_list],  # 2-3 jugadores en apoyo
        "pressers": [unum_list],    # Jugadores presionando
        "defenders": [unum_list],   # Jugadores defensivos
        "markers": {                # Quién marca a quién
            unum: opponent_id
        }
    }
}
```

**AgentNode** (cada jugador):
```python
{
    "unum": int,
    "pos": (x, y),
    "vel": (vx, vy),
    "speed": float,
    
    "stamina": float,
    "effort": float,
    "recovery": float,
    "fatigue_level": float,         # 0-1 (derivado de stamina)
    
    "body_dir": float,
    "head_angle": float,
    "view_width": str,
    "view_quality": str,
    
    "role": str,                    # "goalkeeper", "defender", etc.
    "state": State,                 # Estado FSM
    "responsibility": str,          # "ball_owner", "support", "press"
    
    "intent": {
        "action": str,              # "move_to_ball", "support", etc.
        "target": (x, y) | None,
        "priority": float,
        "duration": int
    },
    
    "zone_assignment": (xmin, xmax, ymin, ymax),
    "is_in_zone": bool,
    "dist_to_zone_center": float,
    
    "last_seen_cycle": int,
    "last_update_cycle": int,
    "data_freshness": float,        # 0-1 (qué tan reciente)
    
    # Relaciones
    "nearest_teammate": unum | None,
    "nearest_teammate_dist": float,
    "nearest_opponent": int | None,
    "nearest_opponent_dist": float,
    
    "is_marked": bool,
    "marker_id": int | None,
    "is_marking": bool,
    "marking_target": int | None,
    
    "has_ball": bool,
    "can_receive_pass": bool,
    "in_passing_lane": bool
}
```

**Métricas Agregadas**:
```python
{
    "num_agents_active": int,
    "num_agents_in_offensive_third": int,
    "num_agents_in_defensive_third": int,
    "num_agents_in_midfield": int,
    
    "avg_stamina": float,
    "min_stamina": float,
    "max_stamina": float,
    
    "avg_distance_to_ball": float,
    "centroid": (x, y),             # Centro geométrico del equipo
    
    "nearest_to_ball": unum,
    "second_nearest_to_ball": unum,
    "farthest_from_ball": unum,
    
    "formation_integrity": float,    # 0-1 (qué tan bien mantenemos formación)
    "coordination_quality": float    # 0-1 (índice de coordinación)
}
```

---

### 4. OPPONENT CONTEXT (Contexto de Rivales)

**Estructura**:
```python
{
    "opponents": {
        0: OpponentNode,  # IDs temporales (no necesariamente unum)
        1: OpponentNode,
        # ... hasta 11
    },
    
    "estimated_formation": str,      # "4-4-2", "unknown"
    "defensive_line_y": float,       # Línea defensiva estimada
    "offensive_line_y": float,       # Línea ofensiva estimada
    
    "pressure_index": float,         # 0-1 (intensidad de pressing)
    "compactness": float,            # Qué tan juntos están
    
    "possession_time_ratio": float,  # % tiempo que tienen el balón
    "avg_pass_distance": float,      # Distancia promedio de pases
    
    "in_our_penalty_area": int,      # Cuántos en nuestra área
    "in_their_penalty_area": int     # Cuántos de ellos en su área
}
```

**OpponentNode**:
```python
{
    "id": int,                      # ID temporal
    "pos": (x, y),
    "vel_estimated": (vx, vy),      # Estimado con Kalman
    
    "last_seen_cycle": int,
    "seen_by": [unum_list],         # Quién lo ve
    "confidence": float,            # 0-1 (confianza en datos)
    
    "role_estimated": str,          # "defender", "forward", etc.
    "threat_level": float,          # 0-1 (qué tan peligroso)
    
    "predicted_pos_t5": (x, y),     # Predicción futura
    "predicted_pos_t10": (x, y),
    
    # Relaciones
    "nearest_to_ball": bool,
    "dist_to_ball": float,
    "has_ball": bool,
    
    "marking_agent": unum | None,   # Quién de nosotros lo marca
    "is_marked": bool,
    "marked_by": unum | None,
    
    "is_dangerous": bool,           # En posición peligrosa
    "in_shooting_position": bool,
    "in_passing_position": bool
}
```

---

### 5. SPATIAL CONTEXT (Control Espacial)

**Voronoi Cells**:
```python
{
    "voronoi_cells": {
        unum: {
            "area": float,          # m²
            "center": (x, y),
            "vertices": [(x, y), ...],
            "neighbors": [unum_list],
            "is_contested": bool,   # Si hay rival cerca
            "control_quality": float # 0-1
        }
    },
    
    "total_controlled_area": float,  # Suma de áreas de agentes
    "control_ratio": float,          # vs área total del campo
    "largest_cell_unum": int,
    "smallest_cell_unum": int
}
```

**Free Spaces** (espacios libres):
```python
{
    "free_spaces": [
        {
            "id": int,
            "center": (x, y),
            "radius": float,
            "area": float,
            "value": float,         # 0-1 (qué tan valioso)
            "direction": float,     # Ángulo desde balón
            "distance_from_ball": float,
            "is_safe": bool,        # Sin rivales cerca
            "exploitable": bool     # Se puede aprovechar
        }
    ],
    
    "largest_free_space": int,      # ID del espacio más grande
    "nearest_free_space_to_ball": int
}
```

**Influence Map**:
```python
{
    "influence_grid": np.array(21, 14),  # Grid 5m x 5m
    "allied_influence": np.array(21, 14),
    "enemy_influence": np.array(21, 14),
    
    "controlled_cells": int,        # Celdas con influence >0
    "contested_cells": int,         # Celdas balance cercano a 0
    "enemy_controlled_cells": int,
    
    "dangerous_zones": [            # Zonas con alta presión rival
        {
            "center": (x, y),
            "radius": float,
            "threat_level": float
        }
    ]
}
```

---

### 6. TACTICAL CONTEXT (Contexto Táctico)

**Fase Estratégica**:
```python
{
    "phase": str,                   # "possession", "pressing", "defensive", "transition"
    "phase_duration": int,          # Ciclos en esta fase
    "last_phase": str,
    "phase_changes_count": int,     # Veces que cambió en partido
    
    "strategy": str,                # "short_pass", "counter", "hold_ball", "long_ball"
    "strategy_effectiveness": float, # 0-1 (qué tan bien funciona)
    
    "pressing_active": bool,
    "pressing_trigger_cycle": int,  # Cuándo activamos pressing
    "pressing_target": (x, y),      # Dónde presionamos
    "pressing_success_rate": float  # % veces que recuperamos
}
```

**Pass Network** (red de pases):
```python
{
    "current_passer": unum | None,
    "pass_options": [
        {
            "receiver_unum": int,
            "receiver_pos": (x, y),
            "distance": float,
            "angle": float,
            
            "score": float,         # 0-1 (calidad del pase)
            "risk": float,          # 0-1 (riesgo de intercepción)
            "tactical_value": float,# 0-1 (valor estratégico)
            
            "interceptor": int | None,
            "interception_point": (x, y) | None,
            "time_to_reach": int,   # Ciclos
            
            "requires_receiver_movement": bool,
            "receiver_must_move_to": (x, y) | None,
            
            "is_progressive": bool, # Avanza territorio
            "is_safe": bool,        # Riesgo <0.3
            "is_backward": bool,    # Pase hacia atrás
            "is_lateral": bool      # Pase lateral
        }
    ],
    
    "best_option": unum | None,
    "second_best": unum | None,
    
    "triangulation_available": bool,
    "triangle_nodes": [unum_list],  # 3 jugadores formando triángulo
    "triangle_quality": float,      # 0-1
    
    "support_positions": [          # Posiciones de apoyo ideales
        {
            "target": (x, y),
            "assigned_to": unum | None,
            "value": float
        }
    ],
    
    "passing_lanes_count": int,     # Total de líneas de pase limpias
    "blocked_lanes_count": int      # Bloqueadas por rivales
}
```

**Defensive Structure**:
```python
{
    "defensive_line": {
        "agents": [unum_list],
        "avg_y": float,             # Posición promedio Y
        "width": float,             # Amplitud
        "compactness": float,       # Qué tan juntos
        "has_gaps": bool,           # ¿Hay huecos?
        "gap_positions": [(x, y)]   # Ubicación de huecos
    },
    
    "midfield_line": { ... },       # Similar a defensive_line
    "offensive_line": { ... },
    
    "lines_distance": {
        "defense_to_midfield": float,
    "midfield_to_offense": float,
        "is_compact": bool          # <15m entre líneas
    },
    
    "marking_assignments": {
        unum: opponent_id
    },
    
    "unmarked_opponents": [opponent_ids],
    "coverage_quality": float       # 0-1
}
```

---

## 🎯 CONTEXTO LOCAL (Agente Individual)

### Estructura
```python
class LocalContext:
    """
    Información específica del agente.
    """
    
    def __init__(self):
        self.perception = PerceptionData()
        self.mental_state = MentalState()
        self.tactical_assessment = TacticalAssessment()
        self.history = HistoryBuffer()
```

---

### 1. PERCEPTION DATA (Percepción Directa)

**Self State**:
```python
{
    "pos": (x, y) | (None, None),
    "pos_confidence": float,        # 0-1
    "vel": (vx, vy),
    "speed": float,
    
    "stamina": float,
    "effort": float,
    "recovery": float,
    "capacity": float,
    "fatigue": float,               # Derivado: 1 - (stamina/max)
    
    "body_dir": float,
    "head_angle": float,
    "neck_angle": float,
    
    "view_quality": str,
    "view_width": str,
    "view_angle_min": float,
    "view_angle_max": float
}
```

**Ball Perception**:
```python
{
    "can_see": bool,
    "distance": float | None,
    "angle": float | None,
    "dist_change": float,           # Velocidad relativa
    "dir_change": float,
    
    "is_kickable": bool,
    "is_catchable": bool,           # Solo portero
    
    "estimated_pos": (x, y) | None,
    "estimated_vel": (vx, vy) | None,
    
    "time_since_seen": int,         # Ciclos desde última visión
    "last_seen_pos": (x, y)
}
```

**Visible Objects**:
```python
{
    "teammates": [
        {
            "unum": int,
            "distance": float,
            "angle": float,
            "body_dir": float | None,
            "estimated_pos": (x, y),
            "is_behind_me": bool,
            "in_my_view": bool
        }
    ],
    
    "opponents": [
        {
            "id": int,
            "distance": float,
            "angle": float,
            "body_dir": float | None,
            "estimated_pos": (x, y),
            "is_threat": bool,
            "is_marking_me": bool
        }
    ],
    
    "flags": [
        ("flag_name", distance, angle)
    ],
    
    "lines": [
        ("line_name", distance, angle)
    ]
}
```

**Collision Detection**:
```python
{
    "collision_risk": {
        "imminent": bool,           # <0.5m y <2 ciclos
        "agent_type": "teammate" | "opponent",
        "agent_id": int,
        "distance": float,
        "relative_velocity": (vx, vy),
        "cycles_to_collision": int,
        "collision_point": (x, y)
    }
}
```

---

### 2. MENTAL STATE (Estado Mental)

**Identity**:
```python
{
    "unum": int,
    "side": "left" | "right",
    "role": str,                    # "goalkeeper", "defender", etc.
    "role_confidence": float,       # Qué tan bien cumplo rol
    
    "fsm_state": State,
    "state_duration": int,          # Ciclos en este estado
    "last_state": State,
    "state_changes_count": int
}
```

**Responsibility**:
```python
{
    "current": str,                 # "ball_owner", "support", "press", etc.
    "priority": float,              # 0-1
    
    "should_go_to_ball": bool,
    "am_i_nearest": bool,
    "am_i_second_nearest": bool,
    
    "assigned_zone": (xmin, xmax, ymin, ymax),
    "is_in_zone": bool,
    "distance_to_zone": float,
    "should_return_to_zone": bool
}
```

**Intent** (intención publicada):
```python
{
    "action": str,
    "target": (x, y) | None,
    "priority": float,
    "duration": int,
    "published_cycle": int
}
```

**Emotional State** (para debugging/análisis):
```python
{
    "confidence": float,            # 0-1 (éxito reciente)
    "pressure": float,              # 0-1 (rivales cerca)
    "isolation": float,             # 0-1 (lejos de compañeros)
    "urgency": float,               # 0-1 (necesidad de actuar rápido)
    "frustration": float            # 0-1 (acciones fallidas recientes)
}
```

---

### 3. TACTICAL ASSESSMENT (Evaluación Táctica Local)

**Ball Relation**:
```python
{
    "my_dist_to_ball": float,
    "my_angle_to_ball": float,
    "ball_in_my_zone": bool,
    
    "i_am_nearest": bool,
    "i_am_second_nearest": bool,
    "my_rank_to_ball": int,         # 1º, 2º, 3º... más cercano
    
    "can_reach_ball_in": int | None, # Ciclos para alcanzar
    "should_intercept": bool,
    "intercept_point": (x, y) | None
}
```

**Marking & Coverage**:
```python
{
    "am_i_marked": bool,
    "marker_dist": float | None,
    "marker_angle": float | None,
    "marker_id": int | None,
    
    "am_i_marking": bool,
    "marking_target": int | None,
    "marking_effectiveness": float,  # 0-1
    
    "nearest_opponent_dist": float,
    "nearest_opponent_angle": float,
    "nearest_opponent_threat": float # 0-1
}
```

**Space Assessment**:
```python
{
    "free_space": {
        "front": float,             # Distancia libre adelante
        "back": float,
        "left": float,
        "right": float,
        "best_direction": float,    # Ángulo
        "largest": float
    },
    
    "my_voronoi_area": float,
    "in_contested_area": bool,
    
    "teammates_in_support_range": int,  # 5-20m
    "opponents_in_pressure_range": int, # <5m
    
    "pressure_level": float,        # 0-1 (derivado)
    "has_time": bool                # Puede tomar decisión tranquila
}
```

**Action Feasibility**:
```python
{
    "passing": {
        "options_count": int,
        "best_pass_score": float,
        "has_safe_pass": bool,      # Score >0.6, risk <0.3
        "can_pass_forward": bool,
        "can_pass_backward": bool
    },
    
    "dribbling": {
        "feasible": bool,
        "space_available": float,
        "risk": float,
        "optimal_direction": float
    },
    
    "shooting": {
        "feasible": bool,
        "goal_angle": float,        # Ángulo de tiro disponible
        "distance_to_goal": float,
        "probability": float,        # 0-1 (P de gol)
        "should_shoot": bool         # Probabilidad >0.4
    },
    
    "defending": {
        "should_press": bool,
        "should_cover": bool,
        "should_mark": bool,
        "optimal_defensive_position": (x, y)
    }
}
```

**Positioning**:
```python
{
    "tactical_position": (x, y),    # Posición asignada
    "current_deviation": float,     # Distancia a posición táctica
    
    "is_offside": bool,
    "offside_line": float,
    "distance_to_offside": float,
    
    "in_penalty_area": bool,
    "near_boundary": bool,
    "near_corner": bool,
    
    "optimal_support_position": (x, y) | None,
    "should_move_to_support": bool
}
```

---

### 4. HISTORY BUFFER (Historial Reciente)

**Actions** (últimas 10 acciones):
```python
{
    "action_history": [
        {
            "action": str,          # "dash", "turn", "kick"
            "params": [float],
            "cycle": int,
            "success": bool,
            "result": str
        }
    ]
}
```

**Positions** (últimas 20 posiciones):
```python
{
    "position_history": [
        ((x, y), cycle)
    ],
    
    "trajectory_direction": float,  # Hacia dónde me muevo
    "trajectory_speed": float,      # Qué tan rápido
    "is_stationary": bool          # Velocidad <0.1
}
```

**Events** (últimos eventos relevantes):
```python
{
    "recent_events": [
        {
            "event": str,           # "lost_ball", "received_pass", etc.
            "cycle": int,
            "cycles_ago": int
        }
    ],
    
    "last_ball_possession_cycle": int,
    "last_successful_pass_cycle": int,
    "last_failed_pass_cycle": int,
    "last_collision_cycle": int,
    "last_recovery_cycle": int
}
```

**Performance Metrics** (ventana de 100 ciclos):
```python
{
    "passes_attempted": int,
    "passes_completed": int,
    "pass_completion_rate": float,
    
    "balls_received": int,
    "balls_lost": int,
    "possession_time": int,
    
    "distance_covered": float,
    "avg_speed": float,
    "sprints": int,
    
    "stamina_efficiency": float     # Distancia / stamina gastado
}
```

---

## 🧮 CÁLCULOS DERIVADOS

### Índices Compuestos

**Coordination Index** (coordinación del equipo):
```python
def calculate_coordination_index():
    """
    Mide qué tan coordinado está el equipo (0-1).
    """
    # Factores:
    # 1. Distancia promedio entre jugadores (ideal: 8-12m)
    avg_dist = mean([distance(a1, a2) for a1, a2 in all_pairs])
    dist_score = 1.0 - abs(avg_dist - 10) / 20
    
    # 2. Varianza de distancias (ideal: baja)
    std_dist = std([distance(a1, a2) for a1, a2 in all_pairs])
    var_score = 1.0 - min(1.0, std_dist / 10)
    
    # 3. Triángulos formados
    triangles = count_triangles(team_positions)
    tri_score = min(1.0, triangles / 8)
    
    # 4. Conflictos de intención (ideal: 0)
    conflicts = count_intent_conflicts()
    conflict_score = max(0, 1.0 - conflicts / 3)
    
    return 0.3*dist_score + 0.2*var_score + 0.3*tri_score + 0.2*conflict_score
```

**Threat Level** (nivel de amenaza de rival):
```python
def calculate_threat_level(opponent):
    """
    Qué tan peligroso es un rival (0-1).
    """
    threat = 0.0
    
    # 1. Distancia al balón
    if opponent.dist_to_ball < 5:
        threat += 0.3
    
    # 2. Posición en campo
    if opponent.pos[0] > 30:  # Campo ofensivo
        threat += 0.2
    
    # 3. Sin marca
    if not opponent.is_marked:
        threat += 0.3
    
    # 4. En posición de tiro
    if opponent.can_shoot:
        threat += 0.2
    
    return min(1.0, threat)
```

---

## 🔄 FLUJO DE ACTUALIZACIÓN

### Cada Ciclo (100ms)

```
1. RECIBIR MENSAJES
   ↓
2. ACTUALIZAR PERCEPCIÓN LOCAL
   - Parsear see, sense_body, hear
   - Localización propia
   - Detección de objetos
   ↓
3. ACTUALIZAR BLACKBOARD (contexto global)
   - Mi posición → TeamContext
   - Balón visible → BallContext
   - Rivales vistos → OpponentContext
   ↓
4. LEER BLACKBOARD
   - Estado del equipo
   - Intenciones de compañeros
   - Fase táctica
   ↓
5. CALCULAR DERIVADOS
   - Voronoi (cada 5 ciclos)
   - Pass options (si tengo balón)
   - Threat levels
   ↓
6. CONSTRUIR CONTEXTOS
   - GlobalContext completo
   - LocalContext propio
   ↓
7. DECIDIR ACCIÓN
   - Hybrid Controller (FSM + ML)
   ↓
8. PUBLICAR INTENCIÓN
   - Actualizar Blackboard con mi intent
   ↓
9. EJECUTAR COMANDO
   - Enviar a servidor
```

---

## 📐 DIMENSIONES FINALES

### State Vector V3: 200 dimensiones

| Rango | Categoría | Dims | Descripción |
|-------|-----------|------|-------------|
| 0-7 | Ball | 8 | Balón (fijo + predicción) |
| 8-15 | Self | 8 | Estado propio |
| 16-19 | Role | 4 | One-hot rol |
| 20-29 | FSM | 10 | One-hot estado |
| 30-38 | PlayMode | 9 | One-hot modo |
| 39-54 | Teammates Top4 | 16 | 4 compañeros cercanos |
| 55-70 | Opponents Top4 | 16 | 4 rivales cercanos |
| 71-80 | Tactical Pos | 10 | Posición táctica |
| 81-90 | Match Context | 10 | Tiempo, score, fase |
| 91-100 | Predictions | 10 | Predicciones futuras |
| 101-110 | Passes | 10 | Evaluación de pases |
| 111-120 | History | 10 | Historial acciones |
| 121-127 | Embedding | 7 | Embedding táctico |
| **128-137** | **Pass Network** | **10** | **Líneas de pase disponibles** |
| **138-147** | **Free Spaces** | **10** | **Espacios libres (Voronoi)** |
| **148-157** | **Marking** | **10** | **Relaciones de marcaje** |
| **158-167** | **Coordination** | **10** | **Coordinación de equipo** |
| **168-177** | **Opponent Context** | **10** | **Contexto rival** |
| **178-187** | **Advanced Predictions** | **10** | **Predicciones avanzadas** |
| **188-199** | **Reserved** | **12** | **Reservado para expansión** |

**Total**: 200 dimensiones

---

## ✅ NEXT STEPS

1. **Sprint 2**: Implementar state_vector_v3.py con 200 dims
2. **Sprint 2**: Completar VoronoiController
3. **Sprint 2**: Implementar InfluenceMaps
4. **Sprint 3**: Actualizar Blackboard con todos los contextos
5. **Sprint 3**: Integrar nodos relacionales en decisiones

---

**Este documento define la arquitectura completa de información del sistema.**
