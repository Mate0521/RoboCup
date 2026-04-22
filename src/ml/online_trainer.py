"""
Entrenador online — fine-tuning durante la simulación.

Usa Experience Replay:
  1. Cada ciclo guarda (state, action, reward, next_state) en un buffer
  2. Cada N ciclos entrena un mini-batch aleatorio del buffer
  3. Guarda los pesos cada M ciclos

El fine-tuning online usa Q-learning simplificado (no actor-critic completo)
para mantener la complejidad manejable y el tiempo de entrenamiento bajo.
"""

import numpy as np
import random
import logging
from collections import deque

from ml.model import AgentBrain
from ml.reward import RewardCalculator

logger = logging.getLogger(__name__)

BUFFER_SIZE     = 10_000   # experiencias máximas en el buffer
BATCH_SIZE      = 64       # tamaño del mini-batch
TRAIN_EVERY     = 10       # entrenar cada N ciclos
SAVE_EVERY      = 500      # guardar pesos cada N ciclos
GAMMA           = 0.95     # factor de descuento


class Experience:
    __slots__ = ("state", "action", "params", "reward", "next_state", "done")

    def __init__(self, state, action, params, reward, next_state, done):
        self.state      = state
        self.action     = action
        self.params     = params
        self.reward     = reward
        self.next_state = next_state
        self.done       = done


class OnlineTrainer:
    def __init__(self, brain: AgentBrain, reward_calc: RewardCalculator):
        self.brain       = brain
        self.reward_calc = reward_calc
        self.buffer      = deque(maxlen=BUFFER_SIZE)
        self._cycle      = 0
        self._prev_state = None
        self._prev_action = None
        self._prev_params = None

    def step(self, state_vec: np.ndarray, score_diff: float) -> tuple[int, np.ndarray]:
        """
        Llamar cada ciclo sense_body:
          1. Calcula la recompensa del ciclo anterior
          2. Guarda la experiencia en el buffer
          3. Obtiene la nueva acción de la red
          4. Entrena si toca

        Retorna (action_idx, params).
        """
        reward = self.reward_calc.calculate(score_diff)

        # Guardar experiencia anterior
        if self._prev_state is not None:
            exp = Experience(
                state      = self._prev_state,
                action     = self._prev_action,
                params     = self._prev_params,
                reward     = reward,
                next_state = state_vec.copy(),
                done       = False,
            )
            self.buffer.append(exp)

        # Obtener nueva acción
        action_idx, params = self.brain.predict(state_vec)

        # Guardar para el siguiente ciclo
        self._prev_state  = state_vec.copy()
        self._prev_action = action_idx
        self._prev_params = params.copy()

        self._cycle += 1

        # Entrenar
        if self._cycle % TRAIN_EVERY == 0 and len(self.buffer) >= BATCH_SIZE:
            self._train()
            self.brain.decay_epsilon()

        # Guardar pesos
        if self._cycle % SAVE_EVERY == 0:
            self.brain.save_weights()
            logger.info(f"[OnlineTrainer] Pesos guardados — ciclo {self._cycle}")

        return action_idx, params

    def _train(self):
        batch = random.sample(self.buffer, BATCH_SIZE)

        states      = np.stack([e.state      for e in batch])
        actions     = np.array([e.action     for e in batch], dtype=np.int32)
        params_arr  = np.stack([e.params     for e in batch])
        rewards     = np.array([e.reward     for e in batch], dtype=np.float32)
        next_states = np.stack([e.next_state for e in batch])

        # Q-learning: calcular targets para la cabeza de regresión
        # Usamos la recompensa directa para los parámetros (supervised signal)
        # y los pesos de la recompensa para ponderar las muestras
        weights = np.abs(rewards) + 0.01  # priorizar experiencias con reward alto

        try:
            self.brain.train_step(
                states=states,
                actions=actions,
                params=params_arr,
                sample_weight=weights,
            )
        except Exception as e:
            logger.error(f"[OnlineTrainer] Error en train_step: {e}")

    def notify_episode_end(self):
        """Llamar al final del partido."""
        if self._prev_state is not None and len(self.buffer) > 0:
            # Marcar el último step como terminal
            self.buffer[-1].done = True
        self.reward_calc.reset()
        self._prev_state  = None
        self._prev_action = None
        self._prev_params = None