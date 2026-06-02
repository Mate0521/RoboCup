# BUGFIXES — Listado de Bugs Detectados y Soluciones

**Fecha**: Junio 1, 2026  
**Total de Bugs**: 9 (3 críticos, 4 altos, 2 medios)

---

## 🔴 BUGS CRÍTICOS (Prioridad Máxima)

### BUG #1: Desincronización de Estados FSM
**Severidad**: 🔴 CRÍTICO  
**Impacto**: Sistema ML recibe información incorrecta, no puede aprender

#### Ubicación
- `src/tactics/hybrid_fsm.py:8-13`
- `src/modules/state_vector_v2.py:33-40`

#### Descripción
El FSM define solo 5 estados:
```python
class State(Enum):
    SEARCH = 0
    CHASE = 1
    KICK = 2
    POSITION = 3
    DEAD = 4
```

Pero `state_vector_v2.py` espera 10 estados:
```python
mapping = {
    State.WAIT: 0, State.SEARCH_BALL: 1, State.MOVE_TO_BALL: 2,
    State.KICK_BALL: 3, State.GO_TO_POS: 4, State.DEAD_BALL: 5,
    State.SUPPORT: 6, State.PRESS: 7, State.DRIBBLE: 8, State.COVER_LANE: 9,
}
```

#### Causa Raíz
Desarrollo incremental: `state_vector_v2.py` fue diseñado para arquitectura futura que nunca se implementó en `hybrid_fsm.py`.

#### Solución

**Opción A** (Recomendada): Expandir FSM
```python
# En src/tactics/hybrid_fsm.py
class State(Enum):
    WAIT = 0              # Esperando (antes de kick-off)
    SEARCH_BALL = 1       # Buscando balón (no visible)
    MOVE_TO_BALL = 2      # Moviéndose hacia balón
    KICK_BALL = 3         # Va a patear
    GO_TO_POSITION = 4    # Reposicionamiento táctico
    DEAD_BALL = 5         # Set piece
    SUPPORT = 6           # Posición de apoyo
    PRESS = 7             # Presionando rival
    DRIBBLE = 8           # Conduciendo balón
    COVER_LANE = 9        # Cubriendo línea de pase
```

**Pasos de implementación**:
1. Expandir enum `State`
2. Implementar métodos `_support_step()`, `_press_step()`, `_dribble_step()`, `_cover_lane_step()`
3. Agregar transiciones de estado
4. Testing: generar state vector y verificar que índice sea correcto

**Opción B**: Reducir state_vector_v2 a 5 estados (no recomendado)

#### Testing
```python
# Test unitario
def test_state_encoding():
    fsm = HybridFSM(...)
    fsm.current_state = State.SUPPORT
    
    state_vec = StateVectorV2(...)
    vec = state_vec.build()
    
    # Verificar que bit correcto esté en 1
    assert vec[20 + 6] == 1.0  # SUPPORT = index 6
```

#### Tiempo estimado: 8 horas

---

### BUG #2: PPO sin Red Crítica (Value Network)
**Severidad**: 🔴 CRÍTICO  
**Impacto**: Entrenamiento PPO no converge, modelo no aprende

#### Ubicación
- `src/ml/ppo_trainer.py:79-83`
- `src/ml/model_v2.py` (falta cabeza de valor)

#### Descripción
PPO requiere dos redes:
- **Policy Network**: π(a|s) → probabilidad de acciones
- **Value Network**: V(s) → valor del estado

Actualmente solo existe policy, y se usa una aproximación incorrecta:
```python
# INCORRECTO
value_est = tf.reduce_max(all_probs, axis=-1)  # Usa max(probabilidades)
```

Esto NO es el valor del estado. El valor debe predecir la recompensa futura acumulada.

#### Causa Raíz
Simplificación errónea del algoritmo PPO. Se intentó evitar tener dos redes.

#### Matemática Correcta
```
Advantage: A(s,a) = Q(s,a) - V(s)
PPO Loss: L = E[min(r(θ)A, clip(r(θ), 1-ε, 1+ε)A)]
Value Loss: L_V = E[(V(s) - R_target)²]

donde:
  r(θ) = π_new(a|s) / π_old(a|s)  (ratio de políticas)
  R_target = recompensa acumulada (return)
```

#### Solución

**Paso 1**: Agregar Value Head a `model_v2.py`
```python
class TacticalBrain(keras.Model):
    def __init__(self, state_size=128, num_actions=8, params_size=4):
        super().__init__()
        
        # ... código existente ...
        
        # NUEVO: Value Head
        self.value_dense_1 = layers.Dense(64, activation='relu', name='value_dense_1')
        self.value_dense_2 = layers.Dense(32, activation='relu', name='value_dense_2')
        self.value_output = layers.Dense(1, activation='linear', name='value')
    
    def call(self, inputs, training=False):
        # ... código existente hasta x ...
        
        # Policy heads (existente)
        action_probs = self.action_head(x)
        action_params = self.param_head(x)
        
        # NUEVO: Value head
        value = self.value_dense_1(x)
        if training:
            value = layers.Dropout(0.1)(value)
        value = self.value_dense_2(value)
        value = self.value_output(value)
        
        return action_probs, action_params, value
    
    def predict_value(self, state):
        """Predice solo el valor (para evaluación)."""
        _, _, value = self(state)
        return value
```

**Paso 2**: Actualizar `ppo_trainer.py`
```python
def _train(self):
    batch = random.sample(self.buffer, BATCH_SIZE)
    
    states = np.array([e.state for e in batch])
    actions = np.array([e.action for e in batch])
    rewards = np.array([e.reward for e in batch])
    next_states = np.array([e.next_state for e in batch])
    dones = np.array([e.done for e in batch])
    
    # Calcular returns (Monte Carlo)
    returns = self._calculate_returns(rewards, dones)
    
    # Predecir valores
    _, _, values = self.brain.model(states)
    _, _, next_values = self.brain.model(next_states)
    
    # Calcular ventaja
    advantages = returns - values.numpy().flatten()
    advantages = (advantages - np.mean(advantages)) / (np.std(advantages) + 1e-8)
    
    # Entrenar
    with tf.GradientTape() as tape:
        action_probs, _, new_values = self.brain.model(states, training=True)
        
        # Policy loss (PPO)
        selected_probs = tf.reduce_sum(
            action_probs * tf.one_hot(actions, NUM_ACTIONS),
            axis=1
        )
        old_probs = selected_probs  # Simplificación: usar misma política
        ratio = selected_probs / (old_probs + 1e-8)
        
        clipped_ratio = tf.clip_by_value(ratio, 1 - EPSILON, 1 + EPSILON)
        policy_loss = -tf.reduce_mean(
            tf.minimum(ratio * advantages, clipped_ratio * advantages)
        )
        
        # Value loss (NUEVO)
        value_loss = tf.reduce_mean(tf.square(new_values - returns))
        
        # Total loss
        total_loss = policy_loss + 0.5 * value_loss
    
    # Backprop
    grads = tape.gradient(total_loss, self.brain.model.trainable_variables)
    self.brain.optimizer.apply_gradients(
        zip(grads, self.brain.model.trainable_variables)
    )
    
    return policy_loss.numpy(), value_loss.numpy()

def _calculate_returns(self, rewards, dones, gamma=0.99):
    """Calcula returns usando descuento."""
    returns = np.zeros_like(rewards)
    running_return = 0
    for t in reversed(range(len(rewards))):
        if dones[t]:
            running_return = 0
        running_return = rewards[t] + gamma * running_return
        returns[t] = running_return
    return returns
```

**Paso 3**: Actualizar loading/saving
```python
def save_weights(self):
    self.model.save_weights(f"weights/brain_v2_{self.save_count}.h5")
    # Ahora incluye value head automáticamente
```

#### Testing
```python
def test_value_prediction():
    brain = TacticalBrain()
    state = np.random.random((1, 128))
    
    action_probs, params, value = brain(state)
    
    assert action_probs.shape == (1, 8)
    assert params.shape == (1, 4)
    assert value.shape == (1, 1)  # NUEVO: verificar shape de valor
    assert -100 < value[0, 0] < 100  # Rango razonable
```

#### Tiempo estimado: 12 horas

---

### BUG #3: FSM No Integrado con ML
**Severidad**: 🔴 CRÍTICO  
**Impacto**: Modelo ML entrenado nunca se usa en producción

#### Ubicación
- `src/tactics/hybrid_fsm.py` (nunca llama a red neuronal)
- `src/agent.py:191` (solo usa FSM)

#### Descripción
El sistema tiene dos pipelines paralelos que nunca se comunican:
1. **FSM (reglas)**: Usado en producción
2. **ML (aprendizaje)**: Entrenado pero nunca ejecutado

```python
# En agent.py
cmd = self._fsm.step(pressing=pressing)  # Solo FSM, ML ignorado
```

#### Causa Raíz
Arquitectura evolutiva: ML se agregó después sin integrar con FSM existente.

#### Solución

Crear **Hybrid Controller** que decide cuándo usar FSM vs ML.

**Archivo nuevo**: `src/tactics/hybrid_controller.py`
```python
class HybridController:
    """
    Controlador híbrido que decide entre FSM (reglas) y ML (aprendizaje).
    
    FSM se usa para:
      - Situaciones deterministas (portero, set pieces)
      - Emergencias
      - Fallback de seguridad
    
    ML se usa para:
      - Decisión de pases
      - Posicionamiento de apoyo
      - Situaciones ambiguas
    """
    
    def __init__(self, fsm, brain, perception, role, unum, side):
        self.fsm = fsm
        self.brain = brain
        self.perception = perception
        self.role = role
        self.unum = unum
        self.side = side
        
        # Estados donde ML es útil
        self.ml_states = {
            State.KICK_BALL,      # Decidir pase vs dribble vs tiro
            State.SUPPORT,        # Mejor posición de apoyo
            State.GO_TO_POSITION  # Ruta óptima
        }
    
    def decide(self):
        """Decisión principal."""
        current_state = self.fsm.current_state
        
        # 1. Casos deterministas (FSM puro)
        if self._is_deterministic():
            return self.fsm.step()
        
        # 2. Casos donde ML ayuda
        if current_state in self.ml_states and self.brain.is_loaded():
            try:
                return self._decide_with_ml()
            except Exception as e:
                logger.warning(f"ML falló: {e}, fallback a FSM")
                return self.fsm.step()
        
        # 3. Default: FSM
        return self.fsm.step()
    
    def _is_deterministic(self):
        """Situaciones donde FSM es mejor."""
        state = self.perception.state
        
        # Portero siempre usa FSM
        if self.role == "goalkeeper":
            return True
        
        # Set pieces usan FSM
        if state.play_mode != PlayMode.PLAY_ON:
            return True
        
        # Emergencias
        if self._is_emergency():
            return True
        
        return False
    
    def _decide_with_ml(self):
        """Decisión usando red neuronal."""
        from modules.state_vector_v2 import StateVectorV2
        from coordination.blackboard import Blackboard
        
        # Construir state vector
        bb = Blackboard()
        state_vec_builder = StateVectorV2(
            perception=self.perception,
            role=self.role,
            fsm_state=self.fsm.current_state,
            # ... otros parámetros ...
        )
        state_vec = state_vec_builder.build()
        
        # Predecir acción
        action_idx, params, value = self.brain.predict(state_vec)
        
        # Validar seguridad
        if self._is_action_safe(action_idx, params):
            return self._execute_ml_action(action_idx, params)
        else:
            # Fallback a FSM
            logger.warning(f"Acción ML no segura: {action_idx}, usando FSM")
            return self.fsm.step()
    
    def _is_action_safe(self, action_idx, params):
        """Verifica que acción ML sea segura."""
        # Ejemplo: no patear si balón no kickable
        if action_idx in [3, 4, 5]:  # KICK, PASS_SHORT, PASS_LONG
            if not self.perception.is_ball_kickable():
                return False
        
        # No colisionar
        if action_idx == 2:  # DASH
            if self._would_collide(params):
                return False
        
        return True
    
    def _execute_ml_action(self, action_idx, params):
        """Convierte predicción ML a comando."""
        ACTION_MAP = {
            0: "TURN_LEFT",
            1: "TURN_RIGHT",
            2: "DASH",
            3: "KICK",
            4: "PASS_SHORT",
            5: "PASS_LONG",
            6: "DRIBBLE",
            7: "STAY"
        }
        
        action_name = ACTION_MAP.get(action_idx, "STAY")
        
        if action_name == "TURN_LEFT":
            return actuators.turn(-abs(params[0]) * 180)
        elif action_name == "TURN_RIGHT":
            return actuators.turn(abs(params[0]) * 180)
        elif action_name == "DASH":
            return actuators.dash(params[1] * 100)
        elif action_name == "KICK":
            return actuators.kick(params[2] * 100, params[3] * 180)
        elif action_name in ["PASS_SHORT", "PASS_LONG"]:
            # Usar PassEvaluator para encontrar mejor pase
            from tactics.pass_evaluation import PassEvaluator
            # ... lógica de pase ...
        elif action_name == "DRIBBLE":
            # Dash suave + kick ligero
            return actuators.dash(50)
        else:
            return None
```

**Integración en `agent.py`**:
```python
# En Agent.__init__
self._hybrid_controller = None

# En Agent._decide
def _decide(self):
    # ... código existente ...
    
    if self._hybrid_controller is None:
        from tactics.hybrid_controller import HybridController
        self._hybrid_controller = HybridController(
            fsm=self._fsm,
            brain=self.brain,  # Necesitamos agregar esto a Agent
            perception=self.perception,
            role=self._role,
            unum=self.unum,
            side=self._side
        )
    
    # CAMBIO PRINCIPAL: usar hybrid controller
    cmd = self._hybrid_controller.decide()
    
    # ... resto del código ...
```

#### Tiempo estimado: 16 horas

---

## 🟡 BUGS ALTOS (Prioridad Alta)

### BUG #4: Localización EKF Falsa
**Severidad**: 🟡 ALTO  
**Impacto**: Localización funcional pero imprecisa, nombre engañoso

#### Ubicación
- `src/perception/localizer.py:6`

#### Descripción
La clase se llama `EKFLocalizer` pero NO implementa Extended Kalman Filter. Solo hace triangulación simple.

Un EKF real requiere:
- Matriz de covarianza `P` (incertidumbre del estado)
- Matriz de ruido del proceso `Q`
- Matriz de ruido de medición `R`
- Ganancia de Kalman `K = P*H'/(H*P*H' + R)`
- Predicción + Corrección

Actualmente solo hace:
```python
# Triangulación simple
pos_estimated = average([pos1_from_flag1, pos2_from_flag2])
```

#### Solución Rápida
Renombrar la clase:
```python
class TriangulationLocalizer:
    """
    Localizador basado en triangulación de flags estáticos.
    Usa promedio ponderado de múltiples observaciones.
    
    NO es un Extended Kalman Filter. Es una aproximación simple.
    """
    # ... código sin cambios ...
```

Actualizar imports:
```python
# En agent.py
from perception.localizer import TriangulationLocalizer
self.localizer = TriangulationLocalizer()
```

#### Solución Completa (si hay tiempo)
Implementar EKF real usando `filterpy`:
```python
from filterpy.kalman import ExtendedKalmanFilter
import numpy as np

class RealEKFLocalizer:
    def __init__(self):
        self.ekf = ExtendedKalmanFilter(dim_x=4, dim_z=2)
        # Estado: [x, y, vx, vy]
        self.ekf.x = np.array([0., 0., 0., 0.])
        self.ekf.P *= 10.  # Incertidumbre inicial
        self.ekf.R = np.array([[0.5, 0], [0, 0.5]])  # Ruido de medición
        self.ekf.Q = np.eye(4) * 0.01  # Ruido del proceso
    
    def update(self, flag_observations, body_dir, head_angle):
        # 1. Predicción (modelo de movimiento constante)
        self.ekf.predict()
        
        # 2. Corrección (con observaciones de flags)
        for flag_name, distance, angle in flag_observations:
            if flag_name in FLAGS:
                flag_pos = FLAGS[flag_name]
                # ... cálculo de z_expected ...
                self.ekf.update(z, HJacobian, Hx)
        
        return (self.ekf.x[0], self.ekf.x[1])
```

#### Tiempo estimado: 2 horas (renombrar) o 16 horas (EKF real)

---

### BUG #5: Flags Duplicados
**Severidad**: 🟡 MEDIO  
**Impacto**: Landmark perdido, localización menos precisa

#### Ubicación
- `src/perception/localizer.py:13-35`

#### Descripción
El diccionario `FLAGS` tiene entradas duplicadas:
```python
FLAGS = {
    # ...
    "fct": (-52.5, 34.0),   # Línea 21
    # ...
    "fct": (-52.5, 34.0),   # Línea 26 (DUPLICADO)
}
```

En Python, la segunda entrada sobrescribe la primera silenciosamente.

#### Solución
1. Revisar manualmente el diccionario
2. Eliminar duplicados
3. Verificar coordenadas contra especificación oficial de RoboCup

```python
# Verificación automatizada
def check_duplicates():
    seen = set()
    for key in FLAGS:
        if key in seen:
            print(f"DUPLICADO: {key}")
        seen.add(key)
```

#### Tiempo estimado: 1 hora

---

### BUG #6: Pases sin Predicción de Balón
**Severidad**: 🟡 MEDIO  
**Impacto**: Pases no consideran timing real del balón

#### Ubicación
- `src/tactics/pass_evaluation.py:15`

#### Descripción
```python
class PassEvaluator:
    def __init__(self, ball_predictor=None):
        self.ball_predictor = ball_predictor  # Se guarda pero NUNCA se usa
```

El evaluador de pases debería:
1. Predecir trayectoria del balón
2. Calcular cuándo llegará al receptor
3. Verificar si rival puede interceptar

Actualmente solo usa posiciones estáticas.

#### Solución
```python
def _calculate_risk(self, passer_pos, receiver_pos, opponents):
    px1, py1 = passer_pos
    px2, py2 = receiver_pos
    
    # NUEVO: Usar predictor
    if self.ball_predictor:
        ball_trajectory = self.ball_predictor.predict(
            pos=(px1, py1),
            vel=self._estimate_pass_velocity(px1, py1, px2, py2),
            n_cycles=20
        )
        
        # Verificar intercepciones en cada punto de la trayectoria
        for t, (bx, by) in enumerate(ball_trajectory):
            for opp in opponents:
                opp_dist_to_ball = distance((bx, by), (opp['x'], opp['y']))
                # Si rival puede alcanzar el balón antes que receptor
                if opp_dist_to_ball < t * 0.5:  # Velocidad rival ~0.5 m/ciclo
                    return (1.0, opp['unum'])  # Riesgo máximo
    
    # Fallback: método actual (estático)
    # ... código existente ...
```

#### Tiempo estimado: 6 horas

---

### BUG #7: Offside Hardcodeado
**Severidad**: 🟡 MEDIO  
**Impacto**: Agentes no saben si están en fuera de juego

#### Ubicación
- `src/modules/state_vector_v2.py:84`

#### Descripción
```python
is_offside = 0.0  # TODO: calcular offside real
```

#### Solución
Ver sección detallada en Sprint 0, tarea #5.

#### Tiempo estimado: 4 horas

---

### BUG #8: Historia y Embedding Vacíos
**Severidad**: 🟡 MEDIO  
**Impacto**: 15 dimensiones del state vector desperdiciadas

#### Ubicación
- `src/modules/state_vector_v2.py:111-127`

#### Descripción
```python
# [111-120] Historial (10) — reservado
i += 10  # Saltar sin llenar

# [121-127] Embedding táctico (7) — reservado
i += 7  # Saltar sin llenar
```

#### Solución
**Historial (últimos 5 ciclos)**:
```python
# [111-120] Historial
if hasattr(self, 'action_history'):
    for past_action in self.action_history[-5:]:
        v[i] = past_action / 7.0  # Normalizar (8 acciones posibles)
        i += 1
    # Pad si hay menos de 5
    i += (5 - len(self.action_history[-5:]))
else:
    i += 5

# Stamina history
if hasattr(self, 'stamina_history'):
    for past_stamina in self.stamina_history[-5:]:
        v[i] = past_stamina / 8000.0
        i += 1
    i += (5 - len(self.stamina_history[-5:]))
else:
    i += 5
```

**Embedding táctico**:
```python
# [121-127] Embedding táctico (aprendido)
# Estos serán aprendidos por la red, iniciar en 0 está bien
i += 7
```

#### Tiempo estimado: 4 horas

---

## 🟢 BUGS MEDIOS/BAJOS

### BUG #9: Planificador Estratégico Simplista
**Severidad**: 🟢 BAJO  
**Impacto**: Estrategia poco adaptativa

#### Ubicación
- `src/strategy/strategic_planner.py`

#### Descripción
Solo cambia fases por posesión. Ignora:
- Marcador
- Tiempo restante
- Zona del campo

#### Solución
Ver Sprint 3 para mejoras.

#### Tiempo estimado: 8 horas

---

## 📊 RESUMEN DE PRIORIDADES

| Prioridad | Cantidad | Tiempo Total |
|-----------|----------|--------------|
| 🔴 Crítica | 3 | 36 horas |
| 🟡 Alta | 4 | 28 horas |
| 🟢 Media/Baja | 2 | 12 horas |
| **TOTAL** | **9** | **76 horas (~2 semanas)** |

---

## ✅ CHECKLIST DE VERIFICACIÓN

Antes de cerrar cada bug:

- [ ] Código implementado
- [ ] Sin errores de compilación
- [ ] Test unitario creado
- [ ] Test pasado
- [ ] Integrado con sistema
- [ ] Documentado
- [ ] Revisado por peer
- [ ] Commiteado a git

---

**Este documento debe actualizarse conforme se resuelven bugs.**
