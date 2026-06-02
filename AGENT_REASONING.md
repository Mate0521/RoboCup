# RAZONAMIENTO DE AGENTES — Cómo Piensa Cada Jugador

**Propósito**: Definir el proceso de razonamiento cognitivo de cada agente  
**Fecha**: Junio 1, 2026

---

## 📋 ÍNDICE

1. [Razonamiento General (Todos los Agentes)](#1-razonamiento-general)
2. [Razonamiento por Rol](#2-razonamiento-por-rol)
3. [Casos de Uso Específicos](#3-casos-de-uso-específicos)
4. [Flujo de Pensamiento Completo](#4-flujo-de-pensamiento-completo)

---

## 1. RAZONAMIENTO GENERAL (Todos los Agentes)

### 1.1 Preguntas Fundamentales (Cada Ciclo)

Todo agente se hace estas 6 preguntas en orden:

```
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 1: ¿DÓNDE ESTOY?                                   │
├─────────────────────────────────────────────────────────────┤
│ • Localización: (x, y) absoluta                             │
│ • Orientación: body_dir, head_angle                         │
│ • Estado físico: stamina, fatigue                           │
│ • Zona asignada: ¿Estoy dentro de mi zona?                  │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 2: ¿DÓNDE ESTÁ EL BALÓN?                           │
├─────────────────────────────────────────────────────────────┤
│ • Posición actual del balón                                 │
│ • Velocidad del balón                                       │
│ • ¿Lo puedo patear? (kickable)                              │
│ • Predicción: ¿Dónde estará en 5-10 ciclos?                │
│ • ¿Quién lo tiene? (nosotros/ellos/nadie)                   │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 3: ¿QUIÉN SOY YO EN ESTE MOMENTO?                  │
├─────────────────────────────────────────────────────────────┤
│ • Rol fijo: goalkeeper/defender/midfielder/forward          │
│ • Responsabilidad dinámica:                                 │
│   - "ball_owner" (tengo el balón)                           │
│   - "support" (apoyo al poseedor)                           │
│   - "press" (presiono rival)                                │
│   - "cover" (cubro espacio/jugador)                         │
│   - "position" (mantengo posición táctica)                  │
│ • Prioridad: 0.0-1.0                                        │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 4: ¿QUÉ ESTÁ PASANDO? (Contexto)                   │
├─────────────────────────────────────────────────────────────┤
│ • Fase del partido: apertura/medio/cierre                   │
│ • Marcador: ¿Ganando/perdiendo/empate?                      │
│ • Fase táctica: posesión/pressing/defensa/transición        │
│ • Play mode: play_on/free_kick/corner/etc.                  │
│ • Urgencia: ¿Necesitamos anotar/defender?                   │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 5: ¿QUÉ DEBO HACER? (Decisión)                     │
├─────────────────────────────────────────────────────────────┤
│ A. ¿Es una emergencia? → Acción determinista (FSM)          │
│ B. ¿Es situación táctica clara? → Reglas (FSM)              │
│ C. ¿Es situación ambigua? → Red neuronal (ML)               │
│                                                              │
│ Decisión final: acción + parámetros                         │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│ PREGUNTA 6: ¿CÓMO LO HAGO? (Ejecución)                      │
├─────────────────────────────────────────────────────────────┤
│ • Pathfinding: ¿Cómo llego a target?                        │
│ • Evitación: ¿Hay colisiones?                               │
│ • Parámetros: power, angle, direction                       │
│ • Publicar intención en Blackboard                          │
│ • Ejecutar comando                                          │
└─────────────────────────────────────────────────────────────┘
```

---

### 1.2 Modelo Mental del Agente

Cada agente mantiene un **modelo mental** del mundo:

```python
class AgentMind:
    """
    Modelo mental del agente.
    """
    
    def __init__(self):
        # IDENTIDAD
        self.unum = None
        self.side = None
        self.role = None  # "goalkeeper", "defender", etc.
        
        # CREENCIAS SOBRE EL MUNDO
        self.beliefs = {
            "my_position": (x, y),
            "my_velocity": (vx, vy),
            "my_orientation": degrees,
            
            "ball_position": (x, y),
            "ball_velocity": (vx, vy),
            "ball_owner": "us" | "them" | None,
            
            "teammates": {unum: AgentBelief},
            "opponents": {id: AgentBelief},
            
            "game_phase": "opening" | "mid_game" | "closing",
            "tactical_phase": "possession" | "pressing" | "defensive",
            "score_diff": int,
            "time_remaining": int
        }
        
        # DESEOS (OBJETIVOS)
        self.desires = {
            "primary": "maximize_possession",
            "secondary": [
                "advance_territory",
                "create_goal_opportunity",
                "maintain_formation",
                "conserve_stamina"
            ]
        }
        
        # INTENCIONES (PLAN ACTUAL)
        self.intentions = {
            "current_action": "move_to_ball",
            "target": (x, y),
            "duration": cycles,
            "priority": 0.8,
            "backup_plan": "go_to_position"
        }
        
        # EMOCIONES (para debugging)
        self.emotions = {
            "confidence": 0.0-1.0,
            "pressure": 0.0-1.0,
            "frustration": 0.0-1.0,
            "urgency": 0.0-1.0
        }
```

---

### 1.3 Proceso de Razonamiento (BDI Architecture)

Usamos arquitectura **BDI (Beliefs-Desires-Intentions)**:

```
┌─────────────────────────────────────────────────────────────┐
│                    BELIEFS (Creencias)                      │
│  "El balón está en (10, 5), moviéndose a (0.5, 0.2)"       │
│  "El compañero #7 está en (15, 8), sin marca"              │
│  "Hay 3 rivales en radio de 10m"                           │
│  "Vamos ganando 2-1, quedan 1500 ciclos"                   │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│                    DESIRES (Deseos)                         │
│  1. Mantener posesión (prioridad: 1.0)                     │
│  2. Avanzar hacia arco rival (prioridad: 0.7)              │
│  3. Conservar stamina (prioridad: 0.5)                     │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│             DELIBERATION (Deliberación)                     │
│  ¿Cuál deseo puedo cumplir mejor?                          │
│  → Mantener posesión: tengo balón kickable                 │
│  → Evaluar opciones: ¿pasar a #7 o driblar?                │
│  → Pase a #7: score=0.85, risk=0.2                         │
│  → Decisión: PASAR a #7                                    │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│                 INTENTIONS (Intenciones)                    │
│  Acción: "pass"                                             │
│  Target: jugador #7 en (15, 8)                              │
│  Parámetros: power=60, angle=35°                            │
│  Prioridad: 0.9                                             │
│  Backup: si falla, "dribble"                                │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│                  MEANS-END REASONING                        │
│  ¿Cómo ejecuto el pase?                                     │
│  1. Orientarme hacia #7 (turn si es necesario)             │
│  2. Kick con power=60, angle=35°                            │
│  3. Publicar intent: "passing to 7"                         │
│  4. Transicionar a estado SUPPORT                           │
└─────────────────────────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────────────────────────┐
│                     ACTION (Acción)                         │
│  Comando: (kick 60 35)                                      │
│  Enviar a servidor                                          │
└─────────────────────────────────────────────────────────────┘
```

---

### 1.4 Jerarquía de Prioridades (Universal)

**Todos los agentes siguen esta jerarquía**:

```
PRIORIDAD 0 (EMERGENCIA) — Override TODO
├─ Portero: balón entrando al arco → catch
├─ Fuera de límites → reposicionarse
└─ Colisión inminente → evasión

PRIORIDAD 1 (SET PIECES) — Situaciones especiales
├─ Kick off → ejecutor o posición inicial
├─ Free kick → ejecutor o barrera/apoyo
├─ Corner → atacar o defender área
└─ Goal kick → repliegue

PRIORIDAD 2 (POSESIÓN PROPIA) — Tengo el balón
├─ Evaluar pases (PassEvaluator)
├─ Si hay pase seguro (score>0.6) → pasar
├─ Si hay tiro claro (P(gol)>0.4) → disparar
├─ Si no → driblar/girar
└─ NUNCA despejar sin razón

PRIORIDAD 3 (APOYO) — Compañero tiene balón
├─ Ir a espacio libre (Voronoi)
├─ Formar triángulo con poseedor
├─ Abrir línea de pase
└─ Anticipar recepción

PRIORIDAD 4 (PRESSING) — Rival tiene balón (cerca)
├─ Si soy nearest → presionar directo
├─ Si soy second → cubrir línea de pase
├─ Duración máx: 15 ciclos
└─ Si no recupero → repliegue

PRIORIDAD 5 (DEFENSA) — Rival tiene balón (lejos)
├─ Replegar a zona táctica
├─ Basculación lateral
├─ Marcar rival asignado
└─ Mantener bloque compacto

PRIORIDAD 6 (TRANSICIÓN) — Balón en disputa
├─ Si perdimos → Gegenpress (3 ciclos)
├─ Si recuperamos → pase seguro
└─ Si balón suelto → nearest va

PRIORIDAD 7 (REPOSICIONAMIENTO) — Nada urgente
├─ Volver a posición táctica
├─ Ajustar formación
└─ Recuperar stamina
```

---

## 2. RAZONAMIENTO POR ROL

### 2.1 PORTERO (Goalkeeper)

**Rol**: Último defensor + Iniciador de jugadas

#### Razonamiento Específico

```python
class GoalkeeperReasoning:
    """
    El portero razona diferente a los demás.
    """
    
    def think(self, context_global, context_local):
        """
        Proceso de pensamiento del portero.
        """
        
        # PREGUNTA ESPECIAL: ¿El balón viene hacia mi arco?
        if self.is_ball_dangerous():
            # SUB-PREGUNTA: ¿Puedo atraparlo (catch)?
            if context_local.ball.distance < 2.0 and self.can_catch():
                return Action.CATCH
            
            # SUB-PREGUNTA: ¿Puedo despejarlo?
            elif context_local.ball.is_kickable:
                # Despeje dirigido (NO aleatorio)
                safe_direction = self.find_safe_clear_direction()
                return Action.KICK(power=100, angle=safe_direction)
            
            # SUB-PREGUNTA: ¿Debo salir del arco?
            elif self.should_leave_goal():
                return self.move_to_intercept_ball()
            
            else:
                # Posicionarme entre balón y arco
                return self.position_between_ball_and_goal()
        
        # PREGUNTA: ¿Tengo el balón? → Iniciar jugada
        elif context_local.ball.is_kickable:
            # Buscar pase corto a defensor
            best_pass = self.find_short_pass_to_defender()
            
            if best_pass and best_pass.score > 0.7:
                return Action.PASS(best_pass)
            else:
                # Esperar mejor opción (girar buscando)
                return Action.TURN(30)
        
        # PREGUNTA: ¿Estoy fuera de posición?
        elif context_local.distance_to_zone > 5.0:
            # Volver al área
            return self.move_to_goal_center()
        
        # Default: mantener posición óptima
        else:
            optimal_pos = self.calculate_optimal_goalkeeper_position()
            return Action.MOVE_TO(optimal_pos)
    
    def is_ball_dangerous(self):
        """
        ¿El balón es una amenaza?
        """
        ball = self.context.ball
        
        # 1. Balón entrando al arco
        if self.ball_predictor.will_enter_goal(cycles=10):
            return True
        
        # 2. Rival con balón en área
        if ball.owner_team == "them" and ball.pos in self.penalty_area:
            return True
        
        # 3. Balón suelto en área pequeña
        if ball.owner_team is None and distance(ball.pos, self.goal) < 10:
            return True
        
        return False
    
    def should_leave_goal(self):
        """
        ¿Debo salir del arco?
        """
        # Solo si:
        # 1. Balón suelto en área
        # 2. Soy el más cercano
        # 3. Puedo llegar antes que rival
        
        if not self.blackboard.ball["owner"]:
            my_time = self.cycles_to_reach_ball()
            rival_time = self.blackboard.get_nearest_opponent_to_ball_time()
            
            if my_time < rival_time - 3:  # Margen de seguridad
                return True
        
        return False
```

#### Casos Específicos del Portero

**Caso 1: Balón Entrando al Arco**
```
PERCEPCIÓN:
  - Balón a 5m del arco
  - Velocidad: (-1.5, 0.2) m/ciclo
  - Predicción: entrará en 3 ciclos

RAZONAMIENTO:
  1. ¿Puedo catch? → Distancia > 2m → NO
  2. ¿Puedo bloquearlo? → Moverme a trayectoria → SÍ
  3. Calcular punto de intercepción
  4. Sprint hacia punto

DECISIÓN:
  dash(power=100) hacia punto de intercepción

INTENCIÓN PUBLICADA:
  "saving_goal" (prioridad: 1.0)
```

**Caso 2: Iniciar Jugada con Balón**
```
PERCEPCIÓN:
  - Tengo balón kickable
  - Veo 2 defensores: #2 (dcha) y #3 (izq)
  - #2 sin marca, #3 marcado

RAZONAMIENTO:
  1. Evaluar pases a defensores
     - Pase a #2: score=0.85, risk=0.1
     - Pase a #3: score=0.40, risk=0.6 (marcado)
  2. #2 es mejor opción
  3. Verificar ángulo (necesito girar 15°)
  4. Decidir: turn + kick

DECISIÓN:
  turn(15) este ciclo
  kick(power=40, angle=0) siguiente ciclo

INTENCIÓN PUBLICADA:
  "passing_to_2" (prioridad: 0.8)
```

---

### 2.2 DEFENSOR (Defender)

**Rol**: Proteger área + Iniciar construcción

#### Razonamiento Específico

```python
class DefenderReasoning:
    """
    El defensor equilibra defensa y construcción.
    """
    
    def think(self, context_global, context_local):
        """
        Proceso de pensamiento del defensor.
        """
        
        # PREGUNTA PRINCIPAL: ¿Dónde está el peligro?
        threat_level = self.assess_threat_level()
        
        if threat_level > 0.7:  # ALTO PELIGRO
            return self.defensive_mode()
        elif context_global.ball.owner_team == "us":
            return self.construction_mode()
        else:
            return self.transition_mode()
    
    def defensive_mode(self):
        """
        Modo defensivo: proteger el arco.
        """
        ball = self.context.ball
        
        # SUB-PREGUNTA: ¿Debo marcar rival específico?
        dangerous_opponent = self.identify_dangerous_opponent()
        
        if dangerous_opponent and dangerous_opponent.in_my_zone:
            # Marcaje individual
            return self.mark_opponent(dangerous_opponent)
        
        # SUB-PREGUNTA: ¿Debo ir al balón?
        elif self.am_i_nearest_defender_to_ball():
            # Presionar poseedor rival
            return self.press_ball_owner()
        
        # SUB-PREGUNTA: ¿Debo cubrir espacio?
        else:
            # Posicionamiento zonal
            optimal_pos = self.calculate_defensive_position()
            return Action.MOVE_TO(optimal_pos)
    
    def construction_mode(self):
        """
        Modo construcción: ayudar a avanzar.
        """
        # SUB-PREGUNTA: ¿Tengo el balón?
        if self.context_local.ball.is_kickable:
            # Buscar pase progresivo
            best_pass = self.find_progressive_pass()
            
            if best_pass and best_pass.score > 0.6:
                return Action.PASS(best_pass)
            else:
                # Pase seguro a mediocampista
                return self.find_safe_pass_to_midfielder()
        
        # SUB-PREGUNTA: ¿Debo ofrecer apoyo?
        elif self.should_support():
            support_pos = self.calculate_support_position()
            return Action.MOVE_TO(support_pos)
        
        # Default: mantener posición
        else:
            return self.hold_position()
    
    def assess_threat_level(self):
        """
        Evaluar nivel de amenaza (0-1).
        """
        threat = 0.0
        ball = self.context.ball
        
        # Factor 1: Proximidad del balón a mi arco
        ball_distance_to_goal = distance(ball.pos, self.my_goal)
        threat += (1.0 - ball_distance_to_goal / 105.0) * 0.4
        
        # Factor 2: Balón en posesión rival
        if ball.owner_team == "them":
            threat += 0.3
        
        # Factor 3: Rivales en mi área
        opponents_in_area = self.count_opponents_in_penalty_area()
        threat += min(0.3, opponents_in_area * 0.1)
        
        return min(1.0, threat)
```

#### Casos Específicos del Defensor

**Caso 1: Marcaje Hombre a Hombre**
```
PERCEPCIÓN:
  - Rival #9 en mi zona (30, 5)
  - Balón en posesión rival en (40, -10)
  - #9 es delantero peligroso

RAZONAMIENTO:
  1. #9 está en posición de recibir pase
  2. Línea de pase desde balón a #9 está limpia
  3. Debo cerrar esa línea
  4. Posicionarme entre balón y #9

DECISIÓN:
  Moverse a (35, 0) [entre balón y #9]
  Mantener distancia 2-3m de #9

INTENCIÓN PUBLICADA:
  "marking_9" (prioridad: 0.9)
```

**Caso 2: Inicio de Construcción**
```
PERCEPCIÓN:
  - Tengo balón kickable en (−30, 5)
  - Mediocampista #7 en (−10, 8) libre
  - Mediocampista #6 en (−15, −5) marcado

RAZONAMIENTO:
  1. Evaluar pases:
     - A #7: score=0.8, avanza 20m, sin riesgo
     - A #6: score=0.3, marcado
  2. #7 es mejor opción
  3. Pase progresivo seguro
  4. Después del pase, mantener posición

DECISIÓN:
  kick(power=50, angle=hacia_#7)

INTENCIÓN PUBLICADA:
  "passing_to_7" (prioridad: 0.8)
```

---

### 2.3 MEDIOCAMPISTA (Midfielder)

**Rol**: Conectar defensa-ataque + Control de juego

#### Razonamiento Específico

```python
class MidfielderReasoning:
    """
    El mediocampista es el cerebro del equipo.
    """
    
    def think(self, context_global, context_local):
        """
        Proceso de pensamiento del mediocampista.
        """
        
        # PREGUNTA PRINCIPAL: ¿Qué fase estamos jugando?
        phase = context_global.tactical_phase
        
        if phase == "possession":
            return self.possession_mode()
        elif phase == "pressing":
            return self.pressing_mode()
        elif phase == "defensive":
            return self.defensive_support_mode()
        else:  # transition
            return self.transition_mode()
    
    def possession_mode(self):
        """
        Modo posesión: mantener y circular balón.
        """
        # SUB-PREGUNTA: ¿Tengo el balón?
        if self.context_local.ball.is_kickable:
            # Rol: distribuidor
            
            # Opción 1: Pase filtrado a delantero
            forward_pass = self.find_pass_to_forward()
            if forward_pass and forward_pass.score > 0.7:
                return Action.PASS(forward_pass)
            
            # Opción 2: Pase lateral a otro mediocampista
            lateral_pass = self.find_lateral_pass()
            if lateral_pass and lateral_pass.score > 0.6:
                return Action.PASS(lateral_pass)
            
            # Opción 3: Pase de seguridad atrás
            back_pass = self.find_safe_backward_pass()
            if back_pass:
                return Action.PASS(back_pass)
            
            # Opción 4: Driblar para crear espacio
            else:
                return self.dribble_to_create_space()
        
        # SUB-PREGUNTA: ¿Debo ofrecer apoyo?
        elif self.should_support():
            # Triangulación
            support_pos = self.calculate_triangulation_position()
            return Action.MOVE_TO(support_pos)
        
        # Default: mantener posición de circulación
        else:
            return self.maintain_circulation_position()
    
    def pressing_mode(self):
        """
        Modo pressing: recuperación rápida.
        """
        # SUB-PREGUNTA: ¿Soy el presser?
        if self.am_i_assigned_presser():
            return self.press_ball_owner()
        
        # SUB-PREGUNTA: ¿Debo cubrir línea de pase?
        elif self.am_i_second_presser():
            return self.cover_most_dangerous_pass_lane()
        
        # Default: comprimir espacio
        else:
            return self.compress_space()
    
    def find_pass_to_forward(self):
        """
        Buscar pase que rompa líneas rivales.
        """
        forwards = self.blackboard.get_agents_by_role("forward")
        
        best_pass = None
        best_score = 0.0
        
        for forward in forwards:
            # Verificar si está en buena posición
            if self.is_forward_in_good_position(forward):
                # Evaluar pase
                pass_option = self.pass_evaluator.evaluate_single(
                    self.my_pos,
                    forward.pos,
                    self.blackboard.opponents
                )
                
                # Bonus por romper líneas
                if self.breaks_defensive_line(pass_option):
                    pass_option.score += 0.2
                
                if pass_option.score > best_score:
                    best_pass = pass_option
                    best_score = pass_option.score
        
        return best_pass if best_score > 0.7 else None
```

#### Casos Específicos del Mediocampista

**Caso 1: Distribución con Triangulación**
```
PERCEPCIÓN:
  - Tengo balón en (0, 0) [centro del campo]
  - Mediocampista #6 en (−10, −10) libre
  - Delantero #9 en (20, 5) marcado
  - Delantero #11 en (15, 15) libre

RAZONAMIENTO:
  1. Evaluar opciones:
     - Pase a #11: rompe líneas, score=0.75
     - Pase a #9: marcado, score=0.40
     - Pase a #6: seguro pero retrocede, score=0.65
  
  2. #11 es mejor opción (rompe líneas)
  3. Verificar que #6 esté en apoyo (triangulación)
  4. #6 forma triángulo: yo-(0,0), #11-(15,15), #6-(−10,−10)
  
  5. Ejecutar pase a #11

DECISIÓN:
  kick(power=55, angle=45°)

INTENCIÓN PUBLICADA:
  "passing_to_11" (prioridad: 0.8)

COMUNICACIÓN (say):
  "p11" [pase a 11]
```

**Caso 2: Pressing en Mediocampo**
```
PERCEPCIÓN:
  - Rival tiene balón en (5, 0)
  - Soy el más cercano (distancia: 8m)
  - Rival #7 tiene línea de pase abierta

RAZONAMIENTO:
  1. Fase: pressing activado (perdimos hace 2 ciclos)
  2. Soy first presser
  3. Objetivo: forzar error o pase hacia atrás
  4. Ángulo de aproximación: cerrar pase a #7
  5. Sprint hacia rival

DECISIÓN:
  dash(power=100) hacia balón
  Ángulo de aproximación: cerrar línea a #7

INTENCIÓN PUBLICADA:
  "pressing_ball" (prioridad: 1.0)

COORDINACIÓN:
  - Compañero #8 cubre pase a #7
  - Compañero #10 cubre pase atrás
```

---

### 2.4 DELANTERO (Forward)

**Rol**: Finalización + Crear espacios

#### Razonamiento Específico

```python
class ForwardReasoning:
    """
    El delantero busca anotar + crear espacios.
    """
    
    def think(self, context_global, context_local):
        """
        Proceso de pensamiento del delantero.
        """
        
        # PREGUNTA PRINCIPAL: ¿Puedo anotar?
        if self.can_shoot():
            return self.evaluate_shooting()
        
        # PREGUNTA: ¿Tengo el balón?
        elif self.context_local.ball.is_kickable:
            return self.with_ball_in_attack()
        
        # PREGUNTA: ¿Debo moverme al espacio?
        elif self.should_move_to_space():
            return self.attack_space()
        
        # Default: ofrecer opción de pase
        else:
            return self.offer_passing_option()
    
    def can_shoot(self):
        """
        ¿Puedo disparar al arco?
        """
        if not self.context_local.ball.is_kickable:
            return False
        
        # Calcular probabilidad de gol
        goal_prob = self.calculate_goal_probability()
        
        # Disparar si P(gol) > 0.4
        return goal_prob > 0.4
    
    def calculate_goal_probability(self):
        """
        Calcular P(gol) basado en:
        - Distancia al arco
        - Ángulo de tiro
        - Presencia de portero
        - Defensores en línea
        """
        distance_to_goal = self.distance_to_opponent_goal()
        goal_angle = self.calculate_goal_angle()
        
        # Probabilidad base por distancia
        if distance_to_goal < 10:
            base_prob = 0.7
        elif distance_to_goal < 20:
            base_prob = 0.4
        elif distance_to_goal < 30:
            base_prob = 0.2
        else:
            base_prob = 0.05
        
        # Ajuste por ángulo
        angle_factor = goal_angle / 30.0  # Normalizar (30° es bueno)
        
        # Ajuste por obstáculos
        if self.goalkeeper_in_sight():
            goalkeeper_penalty = 0.3
        else:
            goalkeeper_penalty = 0.0
        
        defenders_in_line = self.count_defenders_in_shooting_line()
        defender_penalty = defenders_in_line * 0.15
        
        prob = base_prob * angle_factor - goalkeeper_penalty - defender_penalty
        
        return max(0.0, min(1.0, prob))
    
    def with_ball_in_attack(self):
        """
        Tengo balón en ataque, ¿qué hago?
        """
        # Opción 1: Disparar
        if self.can_shoot():
            return Action.SHOOT()
        
        # Opción 2: Asistir a compañero mejor posicionado
        better_positioned_teammate = self.find_teammate_in_better_position()
        if better_positioned_teammate:
            return Action.PASS(better_positioned_teammate)
        
        # Opción 3: Driblar hacia arco
        if self.can_dribble_forward():
            return self.dribble_towards_goal()
        
        # Opción 4: Retener y esperar apoyo
        else:
            return self.retain_ball_and_wait()
    
    def attack_space(self):
        """
        Moverse a la espalda de la defensa.
        """
        # Identificar espacio libre más peligroso
        dangerous_space = self.find_most_dangerous_free_space()
        
        # Verificar offside
        if self.would_be_offside(dangerous_space):
            # Quedarse justo en línea de offside
            return self.move_to_offside_line()
        else:
            # Atacar espacio
            return Action.MOVE_TO(dangerous_space)
```

#### Casos Específicos del Delantero

**Caso 1: Situación de Gol**
```
PERCEPCIÓN:
  - Tengo balón en (45, 5)
  - Distancia al arco: 12m
  - Ángulo de tiro: 25°
  - Portero en línea
  - 1 defensor cerca (3m)

RAZONAMIENTO:
  1. Calcular P(gol):
     - Distancia 12m → base_prob = 0.6
     - Ángulo 25° → angle_factor = 0.83
     - Portero visible → penalty = 0.3
     - 1 defensor → penalty = 0.15
     - P(gol) = 0.6 * 0.83 - 0.3 - 0.15 = 0.05
  
  2. P(gol) = 0.05 < 0.4 → NO disparar
  
  3. Buscar mejor opción:
     - Compañero #9 en (50, 0) sin marca
     - Distancia a arco: 7m
     - Su P(gol) sería ~0.6
  
  4. Decisión: pasar a #9

DECISIÓN:
  kick(power=40, angle=-10°) [hacia #9]

INTENCIÓN PUBLICADA:
  "assisting_9" (prioridad: 0.9)
```

**Caso 2: Desmarque a la Espalda**
```
PERCEPCIÓN:
  - Compañero #7 tiene balón en (10, -5)
  - Estoy en (25, 10)
  - Defensor rival me marca a 2m
  - Espacio libre en (35, 5)

RAZONAMIENTO:
  1. #7 tiene balón → debo ofrecer opción
  2. Estoy marcado → difícil recibir aquí
  3. Espacio libre detectado en (35, 5)
  4. Verificar offside: línea en x=30 → OK
  5. Sprint al espacio

DECISIÓN:
  dash(power=100) hacia (35, 5)
  
  Movimiento: diagonal para perder marca

INTENCIÓN PUBLICADA:
  "attacking_space" (prioridad: 0.8)

COMUNICACIÓN (say):
  "h" [help/ayuda, necesito pase]
```

---

## 3. CASOS DE USO ESPECÍFICOS

### 3.1 Triangulación Automática

**Situación**: Mediocampista #7 tiene balón

```
AGENTE #7 (con balón):
  PENSAMIENTO:
    1. Tengo balón en (0, 0)
    2. Evaluar opciones de pase
    3. ¿Hay triangulación? → Verificar

  COORDINACIÓN (Blackboard):
    - Leo intenciones de compañeros
    - #6 en (−10, −8) → "support_defensive"
    - #8 en (10, 8) → "support_offensive"
    - Triángulo formado: 7-6-8
  
  DECISIÓN:
    - Tengo 2 opciones seguras
    - Elegir pase progresivo a #8

AGENTE #6 (sin balón):
  PENSAMIENTO:
    1. #7 tiene balón
    2. Mi responsabilidad: "support"
    3. Calcular mejor posición de apoyo
    4. Posición defensiva (pase de seguridad)
  
  COORDINACIÓN:
    - Publicar intent: "support_defensive"
    - Target: (−10, −8)
  
  DECISIÓN:
    - Moverme a (−10, −8)
    - Mantener línea de pase limpia

AGENTE #8 (sin balón):
  PENSAMIENTO:
    1. #7 tiene balón
    2. Mi responsabilidad: "support"
    3. Calcular mejor posición de apoyo
    4. Posición ofensiva (pase progresivo)
  
  COORDINACIÓN:
    - Publicar intent: "support_offensive"
    - Target: (10, 8)
  
  DECISIÓN:
    - Moverme a (10, 8)
    - Anticipar recepción
```

**Resultado**: Sistema de pases con 2+ opciones siempre

---

### 3.2 Gegenpress (Recuperación Inmediata)

**Situación**: Perdemos balón en (30, 0) [campo rival]

```
CICLO 0 (pérdida detectada):

AGENTE #7 (perdió balón):
  PENSAMIENTO:
    1. ¡Perdí balón!
    2. Blackboard: publicar "ball_lost" en (30, 0)
    3. Activar gegenpress
  
  DECISIÓN:
    - Presionar inmediatamente al nuevo poseedor
    - Intent: "pressing_ball" (prioridad: 1.0)

AGENTE #8 (nearest):
  PENSAMIENTO:
    1. Blackboard: "ball_lost" detectado
    2. Estoy a 8m del balón
    3. Soy segundo más cercano
  
  DECISIÓN:
    - Cubrir línea de pase más peligrosa
    - Intent: "cover_lane" (prioridad: 0.9)

AGENTE #9 (delantero):
  PENSAMIENTO:
    1. Blackboard: "ball_lost" detectado
    2. Estoy a 15m
    3. No soy presser directo
  
  DECISIÓN:
    - Cerrar espacio hacia mediocampo
    - Intent: "compress_space" (prioridad: 0.7)

CICLOS 1-3 (choque inmediato):
  - #7 presiona directo
  - #8 cubre pase a mediocampista rival
  - #9 cierra retroceso
  - Si recuperan → éxito
  - Si no → fase 2

CICLOS 4-10 (presión organizada):
  - Mantener presión coordinada
  - Forzar pase hacia atrás o lateral
  - Si rival sale de presión → fase 3

CICLOS 11+ (repliegue):
  - Desactivar pressing
  - Replegar a bloque medio
  - Reposicionamiento táctico
```

---

### 3.3 Pase con Movimiento del Receptor

**Situación**: Pase que requiere movimiento

```
AGENTE #7 (pasador):
  PENSAMIENTO:
    1. Tengo balón
    2. #9 en (40, 10) marcado
    3. Espacio libre en (45, 5)
    4. ¿Puede #9 moverse al espacio?
  
  EVALUACIÓN:
    - Pase a posición actual de #9: score=0.3 (marcado)
    - Pase al espacio (45, 5): score=0.8 SI #9 se mueve
  
  COORDINACIÓN:
    - say "p459" [pase a espacio x=45, y=5]
    - Blackboard: intent "passing_to_space" target=(45, 5)
  
  DECISIÓN:
    - Kick hacia (45, 5) con timing
    - Power calculado para que llegue en 8 ciclos

AGENTE #9 (receptor):
  PENSAMIENTO:
    1. hear: "p459" de #7
    2. Decodificar: pase a espacio (45, 5)
    3. Calcular: puedo llegar en 7 ciclos
    4. Timing correcto
  
  DECISIÓN:
    - Sprint hacia (45, 5)
    - Intent: "receiving_pass"
    - Anticipar recepción
  
RESULTADO:
  - Pase exitoso al espacio
  - #9 llega justo a tiempo
  - Se mantiene posesión
```

---

## 4. FLUJO DE PENSAMIENTO COMPLETO

### 4.1 Diagrama de Flujo Unificado

```
┌─────────────────────────────────────────────────────────────┐
│                    INICIO DEL CICLO                         │
│               (Recepción de see, sense_body)                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│             CAPA 1: PERCEPCIÓN                              │
│  • Parsear mensajes                                         │
│  • Localización propia (EKF)                                │
│  • Detección de objetos (balón, jugadores, flags)           │
│  • Predicción básica (balón en 5-10 ciclos)                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         CAPA 2: ACTUALIZACIÓN DE CREENCIAS                  │
│  • Actualizar belief state                                  │
│  • Publicar en Blackboard:                                  │
│    - Mi posición                                            │
│    - Balón si visible                                       │
│    - Rivales vistos                                         │
│  • Leer Blackboard:                                         │
│    - Posiciones de compañeros                               │
│    - Intenciones de otros                                   │
│    - Fase táctica global                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│        CAPA 3: IDENTIFICACIÓN DE RESPONSABILIDAD            │
│  Pregunta: ¿Quién soy en este momento?                      │
│                                                              │
│  IF soy goalkeeper:                                          │
│    → responsibility = "goalkeeper_duty"                      │
│  ELIF tengo balón kickable:                                  │
│    → responsibility = "ball_owner"                           │
│  ELIF compañero tiene balón:                                 │
│    → responsibility = "support"                              │
│  ELIF rival tiene balón Y estoy cerca:                       │
│    → responsibility = "press" | "cover"                      │
│  ELIF rival tiene balón Y estoy lejos:                       │
│    → responsibility = "defensive_position"                   │
│  ELSE:                                                       │
│    → responsibility = "position"                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│           CAPA 4: EVALUACIÓN DE CONTEXTO                    │
│  • Contexto Global:                                          │
│    - Fase del partido (apertura/medio/cierre)               │
│    - Marcador (ganando/perdiendo/empate)                    │
│    - Fase táctica (posesión/pressing/defensa)               │
│  • Contexto Local:                                           │
│    - Presión rival cercana                                  │
│    - Opciones de pase disponibles                           │
│    - Espacios libres                                        │
│    - Fatiga                                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CAPA 5: DELIBERACIÓN                           │
│  Pregunta: ¿Qué debo hacer?                                 │
│                                                              │
│  BRANCH 1: ¿Es emergencia? (portero catch, colisión, etc.)  │
│    → Acción determinista (FSM puro)                         │
│                                                              │
│  BRANCH 2: ¿Es set piece? (free kick, corner, etc.)         │
│    → Acción según play mode (FSM)                           │
│                                                              │
│  BRANCH 3: ¿Es situación táctica clara?                     │
│    (ej: tengo balón, hay pase obvio con score>0.8)          │
│    → Acción según reglas (FSM)                              │
│                                                              │
│  BRANCH 4: ¿Es situación ambigua?                           │
│    (ej: múltiples opciones de pase, dribble vs pass)        │
│    → Consultar red neuronal (ML)                            │
│      • Construir state vector (200 dims)                    │
│      • Predecir: action_probs, params, value                │
│      • Validar seguridad                                    │
│      • Si seguro → ejecutar                                 │
│      • Si no → fallback a FSM                               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│         CAPA 6: PLANIFICACIÓN DE MEDIOS                     │
│  Pregunta: ¿Cómo ejecuto la acción?                         │
│                                                              │
│  IF acción = "move_to":                                      │
│    • Pathfinding (A* o directo)                             │
│    • Evitación de colisiones                                │
│    • Calcular dash power y ángulo                           │
│                                                              │
│  IF acción = "pass":                                         │
│    • Calcular ángulo hacia receptor                         │
│    • Calcular power según distancia                         │
│    • Turn si es necesario                                   │
│    • Kick con parámetros calculados                         │
│                                                              │
│  IF acción = "shoot":                                        │
│    • Calcular ángulo óptimo (esquina del arco)              │
│    • Power máximo o ajustado                                │
│    • Kick                                                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│        CAPA 7: PUBLICACIÓN DE INTENCIÓN                     │
│  • Publicar en Blackboard:                                   │
│    intent = {                                                │
│      "action": "passing_to_7",                               │
│      "target": (x, y),                                       │
│      "priority": 0.8,                                        │
│      "duration": 5                                           │
│    }                                                         │
│  • Comunicar via say (si es relevante):                      │
│    say "p7" [pasando a 7]                                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              CAPA 8: EJECUCIÓN                              │
│  • Generar comando:                                          │
│    (kick 60 35)                                              │
│  • Enviar a servidor                                         │
│  • Actualizar historial:                                     │
│    - Última acción ejecutada                                │
│    - Timestamp                                              │
│  • Transicionar estado FSM:                                  │
│    KICK_BALL → SUPPORT                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 RESUMEN

### Razonamiento General
**Todos los agentes usan el mismo framework**:
1. Percibir → Actualizar creencias
2. Identificar responsabilidad
3. Evaluar contexto (global + local)
4. Deliberar (FSM vs ML)
5. Planificar ejecución
6. Publicar intención
7. Ejecutar

### Razonamiento Particular
**Cada rol tiene prioridades diferentes**:
- **Portero**: Proteger arco > Iniciar jugada
- **Defensor**: Proteger > Construir
- **Mediocampista**: Distribuir > Recuperar
- **Delantero**: Finalizar > Crear espacios

### Coordinación
**Blackboard + Intenciones**:
- Todos publican qué van a hacer
- Todos leen qué hacen los demás
- Conflictos se resuelven por prioridad
- Triangulación emerge naturalmente

---

**Este documento define cómo piensa cada agente. Es la base para implementar el Hybrid Controller.**
