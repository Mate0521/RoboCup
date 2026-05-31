import os
import numpy as np
import tensorflow as tf
from tensorflow import keras

VECTOR_SIZE = 128
N_ACTIONS = 8

ACTION_TURN_LEFT = 0
ACTION_TURN_RIGHT = 1
ACTION_DASH = 2
ACTION_KICK = 3
ACTION_PASS_SHORT = 4
ACTION_PASS_LONG = 5
ACTION_DRIBBLE = 6
ACTION_STAY = 7

LAMBDA_REGRESSION = 0.3

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ml", "weights")


def transformer_block(x, head_size=32, num_heads=4, ff_dim=64, dropout=0.15):
    attn_output = keras.layers.MultiHeadAttention(
        num_heads=num_heads, key_dim=head_size, dropout=dropout
    )(x, x)
    attn_output = keras.layers.Dropout(dropout)(attn_output)
    out1 = keras.layers.LayerNormalization(epsilon=1e-6)(x + attn_output)

    ffn = keras.layers.Dense(ff_dim, activation="relu")(out1)
    ffn = keras.layers.Dropout(dropout)(ffn)
    ffn = keras.layers.Dense(x.shape[-1])(ffn)
    out2 = keras.layers.LayerNormalization(epsilon=1e-6)(out1 + ffn)
    return out2


def build_model_v2(input_size=VECTOR_SIZE):
    inputs = keras.Input(shape=(input_size,), name="state_vector")

    x = keras.layers.Dense(128, activation="relu", name="input_proj")(inputs)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.1)(x)

    x = keras.layers.Reshape((1, 128))(x)

    x = transformer_block(x, head_size=32, num_heads=4, ff_dim=128)
    x = transformer_block(x, head_size=32, num_heads=4, ff_dim=128)

    x = keras.layers.Flatten()(x)

    x = keras.layers.Dense(64, activation="relu")(x)
    x = keras.layers.BatchNormalization()(x)
    x = keras.layers.Dropout(0.15)(x)

    x = keras.layers.Dense(32, activation="relu")(x)

    action_head = keras.layers.Dense(
        N_ACTIONS, activation="softmax", name="action_probs"
    )(x)

    param_head = keras.layers.Dense(
        4, activation="tanh", name="action_params"
    )(x)

    model = keras.Model(
        inputs=inputs,
        outputs={"action_probs": action_head, "action_params": param_head},
        name="agent_brain_v2",
    )
    return model


def compile_model_v2(model, learning_rate=1e-3):
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=learning_rate),
        loss={
            "action_probs": "sparse_categorical_crossentropy",
            "action_params": "mse",
        },
        loss_weights={
            "action_probs": 1.0,
            "action_params": LAMBDA_REGRESSION,
        },
        metrics={"action_probs": "accuracy"},
    )
    return model


class AgentBrainV2:
    def __init__(self, role, training=False):
        self.role = role
        self.training = training
        self.model = build_model_v2()
        self._compiled = False

        if not training:
            self._load_weights()

    def predict(self, state_vec):
        x = state_vec.reshape(1, -1)
        outputs = self.model(x, training=False)

        probs = outputs["action_probs"].numpy()[0]
        params = outputs["action_params"].numpy()[0]

        if self.training:
            action_idx = self._epsilon_greedy(probs)
        else:
            action_idx = int(np.argmax(probs))

        return action_idx, params

    def action_to_command(self, action_idx, params, side):
        from modules import actuators

        turn_angle = float(params[0]) * 30.0
        dash_power = float(params[1]) * 100.0
        kick_param = float(params[2]) * 90.0
        extra_param = float(params[3])

        if action_idx == ACTION_TURN_LEFT:
            return actuators.turn(-abs(turn_angle))
        elif action_idx == ACTION_TURN_RIGHT:
            return actuators.turn(abs(turn_angle))
        elif action_idx == ACTION_DASH:
            return actuators.dash(dash_power)
        elif action_idx == ACTION_KICK:
            k_angle = kick_param if side == "l" else 180 + kick_param
            return actuators.kick(min(100, abs(dash_power)), k_angle)
        elif action_idx == ACTION_PASS_SHORT:
            k_angle = kick_param if side == "l" else 180 + kick_param
            return actuators.kick(min(50, max(15, abs(dash_power) * 0.5)), k_angle)
        elif action_idx == ACTION_PASS_LONG:
            k_angle = kick_param if side == "l" else 180 + kick_param
            return actuators.kick(min(100, max(50, abs(dash_power))), k_angle)
        elif action_idx == ACTION_DRIBBLE:
            return actuators.dash(40)
        elif action_idx == ACTION_STAY:
            return None
        return None

    def train_step(self, states, actions, params, sample_weight=None):
        if not self._compiled:
            compile_model_v2(self.model)
            self._compiled = True

        return self.model.train_on_batch(
            states,
            {"action_probs": actions, "action_params": params},
            sample_weight=sample_weight,
        )

    def save_weights(self):
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        path = os.path.join(WEIGHTS_DIR, f"{self.role}.weights.h5")
        self.model.save_weights(path)

    def _load_weights(self):
        path = os.path.join(WEIGHTS_DIR, f"{self.role}.weights.h5")
        if os.path.exists(path):
            self.model.load_weights(path)

    _epsilon = 0.15

    def _epsilon_greedy(self, probs):
        import random
        if random.random() < self._epsilon:
            return random.randint(0, N_ACTIONS - 1)
        return int(np.argmax(probs))

    def decay_epsilon(self, factor=0.995, min_eps=0.02):
        self._epsilon = max(min_eps, self._epsilon * factor)
