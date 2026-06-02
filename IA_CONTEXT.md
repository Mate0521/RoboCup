# IA_CONTEXT — Sistema de Agentes Inteligentes para RoboCup 2D

**Versión**: 2.0  
**Fecha**: Junio 1, 2026  
**Propósito**: Documento central que define la filosofía, objetivos y reglas de razonamiento de los agentes

---

## 📋 ÍNDICE

1. [Objetivos del Sistema](#1-objetivos-del-sistema)
2. [Filosofía de Juego](#2-filosofía-de-juego)
3. [Arquitectura de Razonamiento](#3-arquitectura-de-razonamiento)
4. [Contextos de Información](#4-contextos-de-información)
5. [Sistema de Decisión](#5-sistema-de-decisión)
6. [Reglas de Comportamiento](#6-reglas-de-comportamiento)
7. [Coordinación Multiagente](#7-coordinación-multiagente)
8. [Función de Valor y Recompensas](#8-función-de-valor-y-recompensas)
9. [Estados Mentales del Agente](#9-estados-mentales-del-agente)
10. [Restricciones y Límites](#10-restricciones-y-límites)

---

## 1. OBJETIVOS DEL SISTEMA

### Objetivo Principal
**MAXIMIZAR LA POSESIÓN DE BALÓN Y MINIMIZAR EL RIESGO DE PÉRDIDA**

### Objetivos Secundarios (en orden de prioridad):

1. **Posesión Segura (70%+ del tiempo)**
   - Mantener el balón en el equipo
   - Nunca despejar sin intención táctica
   - Preferir pase corto seguro sobre pase largo arriesgado

2. **Progresión Territorial Controlada**
   - Avanzar hacia el arco rival cuando sea seguro
   - No forzar jugadas si no hay ventaja
   - Usar todo el ancho del campo

3. **Creación de Oportunidades de Gol**
   - Generar situaciones de superioridad numérica
   - Explotar espacios entre líneas rivales
   - Finalizar cuando la probabilidad sea >40%

4. **Defensa Organizada**
   - Recuperar balón en <5 ciclos (Gegenpress)
   - Cobertura zonal inteligente
   - Nunca dejar espacios críticos sin cubrir

5. **Adaptabilidad Táctica**
   - Ajustar estrategia según marcador
   - Identificar debilidades del rival
   - Cambiar formación según contexto

---

## 2. FILOSOFÍA DE JUEGO

### Principios Fundamentales

#### A. Posesión como Defensa
```
"Si tenemos el balón, el rival no puede atacar"
```
- Posesión >65% es la mejor defensa
- Cada pase exitoso reduce presión rival
- Paciencia > Urgencia

#### B. Triangulación Permanente
```
"El poseedor del balón SIEMPRE tiene 2+ opciones de pase"
```
- Formación de triángulos 5-15m de lado
- Movimiento sin balón constante
- Ocupación inteligente de espacios

#### C. Presión Inmediata tras Pérdida
```
"Recuperar en 3 ciclos o replegar en bloque"
```
- Gegenpress: choque inmediato (ciclos 0-3)
- Si falla, repliegue ordenado (ciclos 4-10)
- No perseguir sin coordinación

#### D. Inteligencia Colectiva > Individual
```
"El equipo piensa como uno solo"
```
- Blackboard compartido con información global
- Decisiones coordinadas vía intenciones
- No competir por el balón entre compañeros

---

## 3. ARQUITECTURA DE RAZONAMIENTO

### Capas de Procesamiento (8 niveles)

```
┌─────────────────────────────────────────────────────────┐
│ 8. ACTUACIÓN         │ Ejecución física de comandos    │
├─────────────────────────────────────────────────────────┤
│ 7. PLANIFICACIÓN     │ Pathfinding, evitación          │
├─────────────────────────────────────────────────────────┤
│ 6. APRENDIZAJE       │ Red neuronal (decisión ML)      │
├─────────────────────────────────────────────────────────┤
│ 5. COORDINACIÓN      │ Blackboard, intenciones         │
├─────────────────────────────────────────────────────────┤
│ 4. ESTRATEGIA        │ Plan de juego global            │
├─────────────────────────────────────────────────────────┤
│ 3. TÁCTICA           │ FSM/BT, decisión situacional    │
├─────────────────────────────────────────────────────────┤
│ 2. PREDICCIÓN        │ Balón, rivales, espacios        │
├─────────────────────────────────────────────────────────┤
│ 1. PERCEPCIÓN        │ Localización, visión            │
└─────────────────────────────────────────────────────────┘
```

### Ciclo de Decisión (cada 100-200ms)

```
1. PERCIBIR
   ↓ ¿Qué veo? (see, sense_body, hear)
   
2. LOCALIZAR
   ↓ ¿Dónde estoy? (EKF con flags)
   
3. PREDECIR
   ↓ ¿Qué pasará? (balón en 5-10 ciclos)
   
4. SINCRONIZAR
   ↓ ¿Qué hacen mis compañeros? (Blackboard)
   
5. EVALUAR CONTEXTO
   ↓ ¿En qué situación estoy? (contexto global + local)
   
6. DECIDIR
   ↓ ¿Qué hago? (FSM + ML + Reglas)
   
7. PLANIFICAR
   ↓ ¿Cómo lo hago? (pathfinding)
   
8. EJECUTAR
   ↓ Enviar comando al servidor
```

---

## 4. CONTEXTOS DE INFORMACIÓN

### 4.1 CONTEXTO GLOBAL (compartido en Blackboard)

#### A. Estado del Partido
```python
{
    "time": 0-6000,              # Ciclos transcurridos
    "score_left": 0-N,           # Goles equipo izquierdo
    "score_right": 0-N,          # Goles equipo derecho
    "play_mode": PlayMode,       # Modo de juego actual
    "phase": "possession" | "pressing" | "defensive" | "transition"
}
```

#### B. Estado del Balón
```python
{
    "ball_pos": (x, y),          # Posición absoluta
    "ball_vel": (vx, vy),        # Velocidad
    "ball_predicted_t5": (x, y), # Predicción 5 ciclos
    "ball_predicted_t10": (x, y),# Predicción 10 ciclos
    "ball_owner_team": "left" | "right" | None,
    "ball_owner_unum": 1-11 | None,
    "last_touch_cycle": N,       # Último ciclo con contacto
    "ball_zone": "defensive" | "midfield" | "offensive"  # Tercio del campo
}
```

#### C. Estado del Equipo (Compañeros)
```python
{
    "agents": {
        1: {  # Por cada jugador (unum: 1-11)
            "pos": (x, y),
            "vel": (vx, vy),
            "stamina": 0-8000,
            "role": "goalkeeper" | "defender" | "midfielder" | "forward",
            "state": "IDLE" | "CHASE" | "KICK" | "SUPPORT" | "PRESS",
            "intent": {
                "action": "move_to_ball" | "support" | "cover" | "press",
                "target": (x, y),
                "priority": 0.0-1.0,
                "duration": N_cycles
            },
            "zone_assignment": (xmin, xmax, ymin, ymax),
            "is_in_zone": bool,
            "visible_opponents": [unum_list],
            "last_update": cycle
        },
        # ... para los 11 jugadores
    },
    "formation": "4-3-3" | "4-4-2" | "3-5-2",
    "nearest_to_ball": unum,
    "second_nearest": unum,
    "players_in_offensive_third": count,
    "players_in_defensive_third": count
}
```

#### D. Estado del Rival (Oponentes)
```python
{
    "opponents": {
        0: {  # ID temporal (puede no ser unum real)
            "pos": (x, y),
            "vel_estimated": (vx, vy),
            "last_seen_cycle": N,
            "confidence": 0.0-1.0,
            "role_estimated": "defender" | "midfielder" | "forward",
            "marking_target": unum | None,  # ¿A quién marca?
            "threat_level": 0.0-1.0,
            "predicted_pos_t5": (x, y)
        },
        # ... oponentes visibles
    },
    "opponent_formation_estimated": "4-4-2" | "unknown",
    "opponent_pressure_index": 0.0-1.0,  # Intensidad de pressing rival
    "opponent_defensive_line": y_coordinate,
    "opponent_offensive_line": y_coordinate
}
```

#### E. Control Espacial
```python
{
    "voronoi_cells": {
        1: {  # Por jugador
            "area": float,  # m²
            "center": (x, y),
            "neighbors": [unum_list],
            "is_contested": bool
        }
    },
    "influence_map": np.array(21, 14),  # Grid 5m x 5m
    "free_spaces": [
        {
            "center": (x, y),
            "radius": float,
            "value": 0.0-1.0,  # Qué tan seguro
            "direction": angle
        }
    ],
    "dangerous_zones": [(x, y, radius)],  # Zonas con presión rival
    "controlled_area_ratio": 0.0-1.0  # % campo controlado
}
```

#### F. Evaluación de Pases
```python
{
    "pass_network": {
        "passer_unum": 7,
        "options": [
            {
                "receiver_unum": 9,
                "receiver_pos": (x, y),
                "distance": float,
                "score": 0.0-1.0,
                "risk": 0.0-1.0,
                "tactical_value": 0.0-1.0,
                "interceptor": opp_id | None,
                "estimated_time": cycles,
                "requires_movement": bool
            }
        ],
        "best_option": unum | None,
        "triangulation_available": bool,
        "support_count": int
    }
}
```

#### G. Métricas en Vivo
```python
{
    "possession_ratio": 0.0-1.0,
    "pass_completion_rate": 0.0-1.0,
    "avg_pass_distance": float,
    "pressing_success_rate": 0.0-1.0,
    "coordination_index": 0.0-1.0,  # Qué tan coordinados estamos
    "stamina_average": float,
    "distance_covered_team": float,
    "intensity": 0.0-1.0  # Dashes/ciclo promedio
}
```

---

### 4.2 CONTEXTO LOCAL (propio del agente)

#### A. Percepción Directa
```python
{
    "self_pos": (x, y) | (None, None),
    "self_vel": (vx, vy),
    "self_stamina": 0-8000,
    "self_effort": 0-1,
    "self_recovery": 0-1,
    "self_body_dir": 0-360,
    "self_head_angle": -90 a +90,
    "self_speed": 0-1.05,
    
    "can_see_ball": bool,
    "ball_distance": float | None,
    "ball_angle": float | None,
    "ball_dist_change": float,  # Velocidad relativa
    "ball_dir_change": float,
    "is_ball_kickable": bool,
    
    "view_quality": "high" | "low",
    "view_width": "narrow" | "normal" | "wide",
    
    "visible_teammates": [
        {
            "unum": int,
            "distance": float,
            "angle": float,
            "body_dir": float | None,
            "pos_estimated": (x, y)
        }
    ],
    
    "visible_opponents": [
        {
            "id": int,  # ID temporal
            "distance": float,
            "angle": float,
            "body_dir": float | None,
            "pos_estimated": (x, y)
        }
    ],
    
    "visible_flags": [
        ("flag_name", distance, angle)
    ],
    
    "collision_risk": {
        "imminent": bool,
        "agent_id": unum | None,
        "cycles_to_collision": int
    }
}
```

#### B. Estado Mental Propio
```python
{
    "role": "goalkeeper" | "defender" | "midfielder" | "forward",
    "fsm_state": State,
    "substate": str | None,
    
    "intent": {
        "action": str,
        "target": (x, y) | None,
        "priority": 0.0-1.0
    },
    
    "tactical_position": (x, y),  # Posición asignada
    "zone": (xmin, xmax, ymin, ymax),
    "is_in_zone": bool,
    "distance_to_zone": float,
    
    "responsibility": "ball_owner" | "support" | "cover" | "press" | "mark",
    
    "mental_state": {
        "confidence": 0.0-1.0,
        "fatigue": 0.0-1.0,  # basado en stamina
        "pressure": 0.0-1.0,  # rivales cerca
        "isolation": 0.0-1.0  # lejos de compañeros
    }
}
```

#### C. Evaluación Táctica Local
```python
{
    "am_i_nearest_to_ball": bool,
    "am_i_second_nearest": bool,
    "should_i_go_to_ball": bool,
    
    "am_i_marked": bool,
    "marker_distance": float | None,
    "marker_angle": float | None,
    
    "teammates_in_support_range": int,  # 5-20m
    "opponents_in_pressure_range": int,  # <5m
    
    "space_available": {
        "front": float,  # distancia libre adelante
        "back": float,
        "left": float,
        "right": float,
        "best_direction": angle
    },
    
    "passing_options_count": int,
    "dribble_feasibility": 0.0-1.0,
    "shoot_feasibility": 0.0-1.0,
    
    "is_offside": bool,
    "offside_line": float,
    
    "in_penalty_area": bool,
    "near_boundary": bool
}
```

#### D. Historial Reciente (últimos 5-10 ciclos)
```python
{
    "action_history": [
        ("dash", power, cycles_ago),
        ("turn", angle, cycles_ago),
        ("kick", power, cycles_ago)
    ],
    
    "position_history": [
        ((x, y), cycle)
    ],
    
    "ball_possession_history": [
        (had_ball: bool, cycle)
    ],
    
    "recent_events": [
        "lost_ball",
        "received_pass",
        "successful_pass",
        "interception",
        "collision"
    ]
}
```

---

## 5. SISTEMA DE DECISIÓN

### 5.1 Jerarquía de Decisión (Prioridades)

```
PRIORIDAD 1 — EMERGENCIAS (overrides todo)
├─ Portero: balón entrando al arco → catch
├─ Balón fuera de límites → posicionarse
└─ Tiempo agotado → detener

PRIORIDAD 2 — SET PIECES (play mode != play_on)
├─ Kick off → ejecutor o posicionarse
├─ Free kick → ejecutor o apoyo
├─ Corner kick → ejecutor o atacar área
├─ Goal kick → retroceder a posición
└─ Penalty → ejecutor o esperar

PRIORIDAD 3 — POSESIÓN (tengo el balón)
├─ Evaluar pases (PassEvaluator)
├─ Si hay pase bueno (score >0.6) → pasar
├─ Si no hay pase → driblar o girar
├─ Si estoy en zona de tiro → evaluar tiro
└─ NUNCA despejar sin razón

PRIORIDAD 4 — APOYO (compañero tiene balón)
├─ Moverme a espacio libre (Voronoi)
├─ Formar triángulo con poseedor
├─ Abrir línea de pase
└─ Anticipar recepción

PRIORIDAD 5 — PRESSING (rival tiene balón, cerca)
├─ Si soy nearest → presionar directo (PRESS)
├─ Si soy second → cubrir línea de pase (COVER_LANE)
├─ Si estoy lejos → cerrar espacios (POSITION)
└─ Duración máxima: 15 ciclos

PRIORIDAD 6 — DEFENSA (rival tiene balón, lejos)
├─ Replegar a zona táctica
├─ Basculación lateral según balón
├─ Mantener compacidad (<15m entre líneas)
└─ Cubrir rival más peligroso

PRIORIDAD 7 — TRANSICIÓN (balón en disputa)
├─ Si perdimos balón → Gegenpress (3 ciclos)
├─ Si recuperamos → pase seguro
├─ Si balón suelto → el más cercano va
└─ Otros anticipan jugada

PRIORIDAD 8 — REPOSICIONAMIENTO (nada urgente)
├─ Volver a posición táctica
├─ Ajustar formación
└─ Recuperar stamina
```

---

### 5.2 Integración FSM + Machine Learning

#### Modo Híbrido

```python
def decide_action(context_global, context_local):
    """
    Decisión híbrida: reglas deterministas + ML
    """
    
    # 1. Reglas deterministas (casos claros)
    if is_goalkeeper and ball_entering_goal():
        return "catch"
    
    if play_mode != PLAY_ON:
        return handle_set_piece()
    
    # 2. Situaciones tácticas definidas
    if context_local.responsibility == "ball_owner":
        if context_local.is_ball_kickable:
            # Aquí SÍ usamos ML para decidir pase vs dribble
            state_vector = build_state_vector(context_global, context_local)
            action, params = neural_network.predict(state_vector)
            
            # Validar con reglas de seguridad
            if is_action_safe(action, params):
                return action, params
            else:
                return safe_fallback()
    
    elif context_local.responsibility == "support":
        # ML decide mejor posición de apoyo
        state_vector = build_state_vector(context_global, context_local)
        target_position = neural_network.predict_position(state_vector)
        return move_to(target_position)
    
    elif context_local.responsibility == "press":
        # Regla determinista
        return press_ball_owner()
    
    # 3. Situación ambigua → ML
    state_vector = build_state_vector(context_global, context_local)
    return neural_network.predict(state_vector)
```

---

## 6. REGLAS DE COMPORTAMIENTO

### Reglas IMPERATIVAS (nunca violar)

#### R1. NO COLISIONAR
```
NUNCA ejecutar dash si hay colisión inminente (<0.5m, <2 ciclos)
```

#### R2. NO DESPEJAR SIN RAZÓN
```
SOLO despejar si:
  - Soy portero Y balón en área Y no puedo catch
  - Último defensa Y rival a <2m Y sin pase disponible
```

#### R3. NO SALIR DE LA ZONA (excepto emergencias)
```
IF role != "forward":
    mantener distancia a zona < 5m
```

#### R4. NO COMPETIR POR BALÓN CON COMPAÑERO
```
IF compañero más cercano al balón:
    responsibility = "support"
ELSE IF yo más cercano:
    responsibility = "ball_owner"
```

#### R5. PORTERO NUNCA SALE DEL ÁREA (excepto extremos)
```
IF role == "goalkeeper":
    x_limit = -52.5 + 16.5 = -36.0  (para lado izquierdo)
```

#### R6. NO PASAR SI RIESGO ALTO
```
IF pass_option.risk > 0.7:
    NO ejecutar pase
    Buscar alternativa o retener
```

#### R7. TRIANGULACIÓN OBLIGATORIA
```
IF tengo balón:
    DEBE haber ≥2 compañeros en rango [5-15m] formando triángulo
    IF NOT:
        Signal "need_support" en Blackboard
        Esperar 3-5 ciclos
```

#### R8. PRESSING COORDINADO
```
IF pérdida de balón en mitad rival:
    TODOS los jugadores en 20m del balón → pressing
    Duración máxima: 15 ciclos
    IF no recuperación:
        Replegar en bloque
```

---

### Reglas HEURÍSTICAS (preferencias)

#### H1. Preferir Pase Corto
```
IF dos pases con score similar (diff <0.1):
    elegir el más corto
```

#### H2. Preferir Avanzar
```
IF empate en opciones:
    preferir la que avanza territorio (x hacia arco rival)
```

#### H3. Mantener Amplitud
```
IF soy extremo (unum 7 u 11):
    mantener |y| > 15 cuando estamos en ataque
```

#### H4. Basculación Defensiva
```
IF rival tiene balón en lateral:
    TODO el equipo bascula 5-10m hacia ese lado
```

#### H5. Conservar Stamina
```
IF stamina <4000 Y no estoy en pressing:
    reducir dash_power en 30%
```

---

## 7. COORDINACIÓN MULTIAGENTE

### Protocolo de Intenciones (Blackboard)

#### Publicación de Intención
```python
def publish_intent(action, target, priority, duration):
    """
    Cada agente publica su intención antes de actuar
    """
    Blackboard().update_intent(
        self.unum,
        {
            "action": action,  # "move_to_ball", "support", "press", etc.
            "target": target,  # (x, y) o None
            "priority": priority,  # 0.0-1.0
            "duration": duration,  # cycles
            "timestamp": current_cycle
        }
    )
```

#### Resolución de Conflictos
```python
def resolve_conflicts():
    """
    Si 2+ agentes quieren ir al balón, solo va el de mayor prioridad
    """
    intents = Blackboard().get_all_intents()
    
    # Caso: múltiples agentes quieren el balón
    ball_seekers = [i for i in intents if i.action == "move_to_ball"]
    if len(ball_seekers) > 1:
        # Solo el más cercano va, otros a "support"
        nearest = min(ball_seekers, key=lambda i: distance_to_ball(i.unum))
        for seeker in ball_seekers:
            if seeker != nearest:
                seeker.action = "support"
                seeker.priority = 0.5
```

#### Roles Dinámicos
```python
def assign_responsibilities():
    """
    Asignar responsabilidades según contexto
    """
    ball_owner_team = Blackboard().ball["owner_team"]
    
    if ball_owner_team == "us":
        # Tenemos posesión
        nearest = Blackboard().get_nearest_to_ball()
        nearest.responsibility = "ball_owner"
        
        # Otros forman triángulo
        supporters = get_best_support_positions(nearest.pos, n=2)
        for s in supporters:
            s.responsibility = "support"
        
        # Resto mantiene posición
        for agent in others:
            agent.responsibility = "position"
    
    elif ball_owner_team == "them":
        # Rival tiene posesión
        if should_press():
            nearest = Blackboard().get_nearest_to_ball()
            nearest.responsibility = "press"
            second = Blackboard().get_second_nearest_to_ball()
            second.responsibility = "cover_lane"
            for agent in others:
                agent.responsibility = "defensive_position"
        else:
            # Repliegue
            for agent in all_agents:
                agent.responsibility = "defensive_position"
```

---

## 8. FUNCIÓN DE VALOR Y RECOMPENSAS

### Recompensa por Ciclo

```python
def calculate_reward(prev_state, current_state, action):
    """
    Recompensa densa para aprendizaje por refuerzo
    """
    reward = 0.0
    
    # A. POSESIÓN (más importante)
    if current_state.ball_owner_team == "us":
        reward += 1.0
        if prev_state.ball_owner_team != "us":
            reward += 5.0  # Bonus por recuperación
    
    # B. PÉRDIDA DE BALÓN (penalización fuerte)
    if prev_state.ball_owner_team == "us" and current_state.ball_owner_team == "them":
        reward -= 10.0  # Castigo severo
    
    # C. PASE EXITOSO
    if action == "pass" and ball_reached_teammate():
        reward += 2.0
        if pass_was_progressive():  # Avanzó territorio
            reward += 1.0
    
    # D. PASE FALLIDO
    if action == "pass" and not ball_reached_teammate():
        reward -= 5.0
    
    # E. PROGRESIÓN TERRITORIAL
    ball_x_advance = current_state.ball_x - prev_state.ball_x
    if current_state.ball_owner_team == "us":
        if my_side == "left":
            reward += ball_x_advance * 0.1  # Avanzar a la derecha
        else:
            reward -= ball_x_advance * 0.1  # Avanzar a la izquierda
    
    # F. CONTROL DE ESPACIOS
    voronoi_area_change = current_state.my_voronoi_area - prev_state.my_voronoi_area
    reward += voronoi_area_change * 0.05
    
    # G. DISCIPLINA POSICIONAL
    if current_state.is_in_zone:
        reward += 0.1
    else:
        reward -= 0.2
    
    # H. COORDINACIÓN (triangulación)
    if current_state.has_triangulation:
        reward += 0.5
    
    # I. PRESSING EXITOSO
    if action == "press" and recovered_ball_within_5_cycles():
        reward += 3.0
    
    # J. INTERCEPTACIÓN
    if action == "intercept" and intercepted_successfully():
        reward += 4.0
    
    # K. STAMINA (penalizar gasto excesivo)
    stamina_loss = prev_state.stamina - current_state.stamina
    if stamina_loss > 50:
        reward -= 0.3
    
    # L. GOLES (eventos raros)
    if goal_scored_by_us():
        reward += 100.0
    if goal_conceded():
        reward -= 100.0
    
    return reward
```

### Función de Valor (V(s))

```python
def estimate_value(state):
    """
    Valor estimado del estado = recompensa futura esperada
    
    Estado valioso:
      - Tenemos posesión
      - Balón en campo rival
      - Múltiples opciones de pase
      - Equipo compacto
      - Alta stamina
    """
    value = 0.0
    
    # Posesión
    if state.ball_owner_team == "us":
        value += 10.0
    
    # Posición del balón
    if my_side == "left":
        value += state.ball_x * 0.2  # Más a la derecha = mejor
    else:
        value -= state.ball_x * 0.2
    
    # Opciones de pase
    value += state.passing_options_count * 2.0
    
    # Compacidad
    if state.team_compactness < 20.0:  # <20m entre jugadores
        value += 5.0
    
    # Stamina promedio
    value += state.avg_stamina / 1000.0
    
    # Control de espacios
    value += state.controlled_area_ratio * 10.0
    
    return value
```

---

## 9. ESTADOS MENTALES DEL AGENTE

### Estados FSM (Finite State Machine)

```python
class State(Enum):
    # Estados básicos
    WAIT = 0              # Esperando inicio/set piece
    SEARCH_BALL = 1       # Buscando balón (no visible)
    MOVE_TO_BALL = 2      # Moviéndose hacia el balón
    KICK_BALL = 3         # Tiene el balón, va a patear
    GO_TO_POSITION = 4    # Moviéndose a posición táctica
    DEAD_BALL = 5         # Set piece (corner, free kick, etc.)
    
    # Estados avanzados
    SUPPORT = 6           # Posición de apoyo (ofrecerse para pase)
    PRESS = 7             # Presionando rival con balón
    DRIBBLE = 8           # Conduciendo el balón
    COVER_LANE = 9        # Cubriendo línea de pase rival
    MARK = 10             # Marcando rival específico
    INTERCEPT = 11        # Intentando interceptar pase
```

### Transiciones de Estado

```
WAIT
  → SEARCH_BALL (si no veo balón)
  → MOVE_TO_BALL (si veo balón y soy nearest)
  → GO_TO_POSITION (si play_mode cambia a play_on)

SEARCH_BALL
  → MOVE_TO_BALL (si encuentro balón)
  → GO_TO_POSITION (si timeout de búsqueda)

MOVE_TO_BALL
  → KICK_BALL (si balón kickable)
  → SUPPORT (si compañero más cercano)
  → GO_TO_POSITION (si balón lejos)

KICK_BALL
  → MOVE_TO_BALL (después de kick, si aún cerca)
  → SUPPORT (después de pase)
  → GO_TO_POSITION (después de clear)

SUPPORT
  → MOVE_TO_BALL (si recibo pase)
  → PRESS (si perdemos balón)
  → GO_TO_POSITION (si ya no hay posesión)

PRESS
  → MOVE_TO_BALL (si recuperamos)
  → COVER_LANE (si no soy nearest)
  → GO_TO_POSITION (si timeout pressing)

DRIBBLE
  → KICK_BALL (si hay pase disponible)
  → GO_TO_POSITION (si pierdo balón)
```

---

## 10. RESTRICCIONES Y LÍMITES

### Restricciones Físicas del Servidor

```python
# Velocidades máximas
MAX_PLAYER_SPEED = 1.05      # m/ciclo
MAX_BALL_SPEED = 3.0         # m/ciclo
MAX_DASH_POWER = 100.0
MAX_KICK_POWER = 100.0
MAX_TURN_ANGLE = 180.0       # grados

# Rangos de acción
KICKABLE_MARGIN = 0.7        # m
CATCHABLE_AREA = 2.0         # m (portero)
VISIBLE_DISTANCE = 3.0       # m (con view quality high)

# Stamina
INITIAL_STAMINA = 8000.0
STAMINA_MAX = 8000.0
RECOVERY_MAX = 1.0
EFFORT_MAX = 1.0

# Decay factors
BALL_DECAY = 0.94            # Por ciclo
PLAYER_DECAY = 0.4
INERTIA_MOMENT = 5.0

# Dimensiones del campo
FIELD_LENGTH = 105.0         # m
FIELD_WIDTH = 68.0           # m
PENALTY_AREA_LENGTH = 16.5   # m
PENALTY_AREA_WIDTH = 40.32   # m
GOAL_WIDTH = 14.02           # m
```

### Límites de Comunicación

```python
# Say message
MAX_SAY_LENGTH = 10          # caracteres
SAY_MSG_SIZE = 512           # bytes

# Hear
AUDIO_CUT_DIST = 50.0        # m

# Bandwidth
MAX_MESSAGES_PER_CYCLE = 1   # Solo 1 say por ciclo
```

### Restricciones Computacionales

```python
# Tiempo de decisión
MAX_DECISION_TIME = 100      # ms (antes del timeout)
TARGET_DECISION_TIME = 50    # ms (objetivo)

# Memoria
MAX_BLACKBOARD_SIZE = 10     # MB
MAX_REPLAY_BUFFER = 10000    # experiencias

# Predicción
MAX_PREDICTION_HORIZON = 10  # ciclos hacia futuro
```

---

## 📌 NOTAS FINALES

### Principios de Implementación

1. **Primero funcionamiento, luego optimización**
   - Sistema debe funcionar antes de optimizar
   - Bugs críticos tienen prioridad

2. **Datos > Intuición**
   - Todas las decisiones basadas en métricas
   - Logging extensivo para debugging

3. **Modularidad**
   - Cada componente independiente
   - Interfaces claras entre capas

4. **Testing continuo**
   - Partidos contra agentes baseline
   - Métricas automáticas (posesión, pases, goles)

5. **Iteración rápida**
   - Ciclos cortos de desarrollo
   - Feedback inmediato

---

**Este documento es la fuente de verdad del sistema. Todas las decisiones de diseño deben alinearse con estos principios.**

**Versión**: 2.0  
**Última actualización**: 2026-06-01
