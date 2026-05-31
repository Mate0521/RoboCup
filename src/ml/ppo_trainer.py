import numpy as np
import tensorflow as tf
import logging
from collections import deque

from ml.model_v2 import AgentBrainV2, compile_model_v2, N_ACTIONS, LAMBDA_REGRESSION
from ml.reward_shaping import AdvancedReward

logger = logging.getLogger(__name__)

BUFFER_SIZE = 50_000
BATCH_SIZE = 128
TRAIN_EVERY = 5
SAVE_EVERY = 300
GAMMA = 0.95
CLIP_EPSILON = 0.2
PPO_EPOCHS = 3


class PrioritizedExperience:
    __slots__ = ("state", "action", "params", "reward", "next_state", "done", "priority")

    def __init__(self, state, action, params, reward, next_state, done, priority=1.0):
        self.state = state
        self.action = action
        self.params = params
        self.reward = reward
        self.next_state = next_state
        self.done = done
        self.priority = priority


class PrioritizedReplayBuffer:
    def __init__(self, max_size=BUFFER_SIZE, alpha=0.6):
        self.buffer = deque(maxlen=max_size)
        self.alpha = alpha
        self._max_priority = 1.0

    def push(self, exp):
        exp.priority = self._max_priority
        self.buffer.append(exp)

    def sample(self, batch_size, beta=0.4):
        if len(self.buffer) < batch_size:
            return None, None, None
        priorities = np.array([e.priority for e in self.buffer[-batch_size:]])
        probs = priorities ** self.alpha
        probs /= probs.sum()
        indices = np.random.choice(len(self.buffer), batch_size, p=probs)
        batch = [self.buffer[i] for i in indices]
        total = len(self.buffer)
        weights = (total * probs[indices]) ** (-beta)
        weights /= weights.max()
        return batch, indices, weights

    def update_priorities(self, indices, td_errors):
        for idx, td in zip(indices, td_errors):
            self.buffer[idx].priority = abs(td) + 1e-6
            self._max_priority = max(self._max_priority, self.buffer[idx].priority)

    def __len__(self):
        return len(self.buffer)


class PPOTrainer:
    def __init__(self, brain, reward_calc):
        self.brain = brain
        self.reward_calc = reward_calc
        self.buffer = PrioritizedReplayBuffer()
        self._cycle = 0
        self._prev_state = None
        self._prev_action = None
        self._prev_params = None
        self._beta = 0.4
        self._beta_increment = 0.001

    def step(self, state_vec, score_diff):
        reward = self.reward_calc.calculate(score_diff)

        if self._prev_state is not None:
            exp = PrioritizedExperience(
                state=self._prev_state,
                action=self._prev_action,
                params=self._prev_params,
                reward=reward,
                next_state=state_vec.copy(),
                done=False,
            )
            self.buffer.push(exp)

        action_idx, params = self.brain.predict(state_vec)

        self._prev_state = state_vec.copy()
        self._prev_action = action_idx
        self._prev_params = params.copy()

        self._cycle += 1
        self._beta = min(1.0, self._beta + self._beta_increment)

        if self._cycle % TRAIN_EVERY == 0 and len(self.buffer) >= BATCH_SIZE:
            self._train()

        if self._cycle % SAVE_EVERY == 0:
            self.brain.save_weights()
            logger.info(f"[PPOTrainer] Pesos guardados — ciclo {self._cycle}")

        return action_idx, params

    def _train(self):
        batch, indices, weights = self.buffer.sample(BATCH_SIZE, self._beta)
        if batch is None:
            return

        states = np.stack([e.state for e in batch])
        actions = np.array([e.action for e in batch], dtype=np.int32)
        params_arr = np.stack([e.params for e in batch])
        rewards = np.array([e.reward for e in batch], dtype=np.float32)
        next_states = np.stack([e.next_state for e in batch])
        dones = np.array([e.done for e in batch], dtype=np.float32)
        sample_weights = weights if weights is not None else None

        if not self.brain._compiled:
            compile_model_v2(self.brain.model)
            self.brain._compiled = True

        try:
            for _ in range(PPO_EPOCHS):
                with tf.GradientTape() as tape:
                    outputs = self.brain.model(states, training=True)
                    probs = outputs["action_probs"]

                    action_mask = tf.one_hot(actions, N_ACTIONS)
                    selected_probs = tf.reduce_sum(probs * action_mask, axis=1)
                    log_probs = tf.math.log(selected_probs + 1e-10)

                    next_outputs = self.brain.model(next_states, training=False)
                    next_probs = next_outputs["action_probs"]
                    next_values = tf.reduce_max(next_probs, axis=1)
                    targets = rewards + GAMMA * next_values * (1.0 - dones)

                    advantages = targets - tf.reduce_max(probs, axis=1)
                    advantages = (advantages - tf.reduce_mean(advantages)) / (tf.math.reduce_std(advantages) + 1e-8)

                    ratio = tf.exp(log_probs - tf.stop_gradient(log_probs))
                    clip_ratio = tf.clip_by_value(ratio, 1.0 - CLIP_EPSILON, 1.0 + CLIP_EPSILON)
                    actor_loss = -tf.reduce_mean(
                        tf.minimum(ratio * advantages, clip_ratio * advantages) * sample_weights
                    )

                    param_loss = tf.keras.losses.mse(params_arr, outputs["action_params"])
                    param_loss = tf.reduce_mean(param_loss * sample_weights)

                    total_loss = actor_loss + LAMBDA_REGRESSION * param_loss

                grads = tape.gradient(total_loss, self.brain.model.trainable_variables)
                self.brain.model.optimizer.apply_gradients(
                    zip(grads, self.brain.model.trainable_variables)
                )

            td_errors = np.abs(rewards - tf.reduce_max(probs, axis=1).numpy())
            if indices is not None:
                self.buffer.update_priorities(indices, td_errors)

            self.brain.decay_epsilon()

        except Exception as e:
            logger.error(f"[PPOTrainer] Error: {e}")

    def notify_episode_end(self):
        if self._prev_state is not None and len(self.buffer) > 0:
            self.buffer.buffer[-1].done = True
        self.reward_calc.reset()
        self._prev_state = None
        self._prev_action = None
        self._prev_params = None
