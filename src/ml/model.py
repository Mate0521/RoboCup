"""
Modelo de red neuronal — TensorFlow/Keras.

Arquitectura híbrida con dos cabezas:
  1. Cabeza de clasificación (softmax, 5 clases):
     [turn_left, turn_right, dash, kick, stay]
     → Decide QUÉ tipo de acción hacer

  2. Cabeza de regresión (tanh, 3 valores):
     [turn_angle_norm, dash_power_norm, kick_params_norm]
     → Decide CON QUÉ PARÁMETROS ejecutar la acción

Pérdida total = cross_entropy(clasificación) + λ · MSE(regresión)

Un modelo por rol:
  goalkeeper.weights, defender.weights,
  midfielder.weights, forward.weights
"""

import os
import numpy as np
import tensorflow as tf
from tensorflow import keras

from modules.state_vector import StateVector, VECTOR_SIZE

# Acciones discretas
ACTION_TURN_LEFT  = 0
ACTION_TURN_RIGHT = 1
ACTION_DASH       = 2
ACTION_KICK       = 3
ACTION_STAY       = 4
N_ACTIONS         = 5

# Pesos de la pérdida combinada
LAMBDA_REGRESSION = 0.3

# Directorio donde se guardan los pesos
WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")


def build_model(input_size: int = VECTOR_SIZE) -> keras.Model:
    """
    Construye el modelo compartido con dos cabezas de salida.
    """
    inputs = keras.Input(shape=(input_size,), name="state_vector")

    # Tronco compartido
    x = keras.layers.Dense(128, activation="relu", name="dense_1")(inputs)
    x = keras.layers.BatchNormalization(name="bn_1")(x)
    x = keras.layers.Dropout(0.2, name="drop_1")(x)

    x = keras.layers.Dense(64, activation="relu", name="dense_2")(x)
    x = keras.layers.BatchNormalization(name="bn_2")(x)
    x = keras.layers.Dropout(0.1, name="drop_2")(x)

    x = keras.layers.Dense(32, activation="relu", name="dense_3")(x)

    # Cabeza 1: clasificación de acción
    action_head = keras.layers.Dense(
        N_ACTIONS, activation="softmax", name="action_probs"
    )(x)

    # Cabeza 2: regresión de parámetros
    # [turn_angle ∈ [-1,1], dash_power ∈ [0,1], kick_power+dir ∈ [-1,1]]
    param_head = keras.layers.Dense(
        3, activation="tanh", name="action_params"
    )(x)

    model = keras.Model(
        inputs=inputs,
        outputs={"action_probs": action_head, "action_params": param_head},
        name="agent_brain",
    )
    return model


def compile_model(model: keras.Model, learning_rate: float = 1e-3) -> keras.Model:
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss={
            "action_probs":  "sparse_categorical_crossentropy",
            "action_params": "mse",
        },
        loss_weights={
            "action_probs":  1.0,
            "action_params": LAMBDA_REGRESSION,
        },
        metrics={"action_probs": "accuracy"},
    )
    return model


class AgentBrain:
    """
    Wrapper que encapsula el modelo TensorFlow y expone
    una interfaz simple para el agente.
    """

    def __init__(self, role: str, training: bool = False):
        self.role     = role
        self.training = training
        self.model    = build_model()
        self._compiled = False

        if not training:
            self._load_weights()

    # ── Inferencia ────────────────────────────────────────────────────────────

    def predict(self, state_vec: np.ndarray) -> tuple[int, np.ndarray]:
        """
        Dado el vector de estado, retorna:
          action_idx: entero [0-4]
          params:     array de 3 floats (parámetros de la acción)
        """
        x = state_vec.reshape(1, -1)
        outputs = self.model(x, training=False)

        probs  = outputs["action_probs"].numpy()[0]
        params = outputs["action_params"].numpy()[0]

        if self.training:
            # Durante entrenamiento: exploración epsilon-greedy
            action_idx = self._epsilon_greedy(probs)
        else:
            action_idx = int(np.argmax(probs))

        return action_idx, params

    def action_to_command(self, action_idx: int, params: np.ndarray,
                          side: str) -> str | None:
        """
        Convierte (action_idx, params) en un comando del actuador.
        params[0] → ángulo de giro normalizado [-1, 1] → [-180, 180]
        params[1] → potencia de dash normalizada [-1, 1] → [-100, 100]
        params[2] → parámetro de kick [-1, 1] → ángulo kick [-90, 90]
        """
        from modules import actuators

        turn_angle  = float(params[0]) * 30.0   # máx 30° por ciclo
        dash_power  = float(params[1]) * 100.0  # [-100, 100]
        kick_angle  = float(params[2]) * 90.0   # [-90, 90] relativo al frente

        # Ajustar dirección del kick según el lado del campo
        if side == "r":
            kick_angle = 180 + kick_angle

        if action_idx == ACTION_TURN_LEFT:
            return actuators.turn(-abs(turn_angle))
        elif action_idx == ACTION_TURN_RIGHT:
            return actuators.turn(abs(turn_angle))
        elif action_idx == ACTION_DASH:
            return actuators.dash(dash_power)
        elif action_idx == ACTION_KICK:
            return actuators.kick(min(100, abs(dash_power)), kick_angle)
        elif action_idx == ACTION_STAY:
            return None  # no hacer nada este ciclo

        return None

    # ── Entrenamiento ─────────────────────────────────────────────────────────

    def train_step(self, states: np.ndarray, actions: np.ndarray,
                   params: np.ndarray, sample_weight: np.ndarray | None = None):
        """Un paso de entrenamiento con batch de experiencias."""
        if not self._compiled:
            compile_model(self.model)
            self._compiled = True

        return self.model.train_on_batch(
            states,
            {"action_probs": actions, "action_params": params},
            sample_weight=sample_weight,
        )

    # ── Persistencia ──────────────────────────────────────────────────────────

    def save_weights(self):
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        path = os.path.join(WEIGHTS_DIR, f"{self.role}.weights.h5")
        self.model.save_weights(path)

    def _load_weights(self):
        path = os.path.join(WEIGHTS_DIR, f"{self.role}.weights.h5")
        if os.path.exists(path):
            self.model.load_weights(path)

    # ── Helpers ───────────────────────────────────────────────────────────────

    _epsilon = 0.15  # exploración durante entrenamiento

    def _epsilon_greedy(self, probs: np.ndarray) -> int:
        import random
        if random.random() < self._epsilon:
            return random.randint(0, N_ACTIONS - 1)
        return int(np.argmax(probs))

    def decay_epsilon(self, factor: float = 0.995, min_eps: float = 0.02):
        self._epsilon = max(min_eps, self._epsilon * factor)