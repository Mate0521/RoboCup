import numpy as np
import tensorflow as tf
import logging
from collections import deque

from ml.model_v2 import AgentBrainV2, compile_model_v2, N_ACTIONS, LAMBDA_REGRESSION

logger = logging.getLogger(__name__)

TRAJECTORY_LENGTH = 1024
MINIBATCH_SIZE = 64
TRAIN_EVERY = 128
SAVE_EVERY = 500
GAMMA = 0.99
GAE_LAMBDA = 0.95
CLIP_EPSILON = 0.2
PPO_EPOCHS = 10
ENTROPY_COEF = 0.01
VALUE_COEF = 0.5
MAX_GRAD_NORM = 0.5
LEARNING_RATE = 3e-4

_global_episode_accum = deque(maxlen=100)


class TrajectoryBuffer:
    def __init__(self, max_size=TRAJECTORY_LENGTH):
        self.max_size = max_size
        self.states = []
        self.actions = []
        self.params = []
        self.rewards = []
        self.values = []
        self.log_probs = []
        self.dones = []

    def store(self, state, action, params, reward, value, log_prob, done=False):
        self.states.append(state)
        self.actions.append(action)
        self.params.append(params)
        self.rewards.append(reward)
        self.values.append(value)
        self.log_probs.append(log_prob)
        self.dones.append(done)

    def get(self):
        return (
            np.array(self.states, dtype=np.float32),
            np.array(self.actions, dtype=np.int32),
            np.array(self.params, dtype=np.float32),
            np.array(self.rewards, dtype=np.float32),
            np.array(self.values, dtype=np.float32),
            np.array(self.log_probs, dtype=np.float32),
            np.array(self.dones, dtype=np.float32),
        )

    def clear(self):
        self.states.clear()
        self.actions.clear()
        self.params.clear()
        self.rewards.clear()
        self.values.clear()
        self.log_probs.clear()
        self.dones.clear()

    def __len__(self):
        return len(self.states)


class PPOTrainer:
    def __init__(self, brain, reward_calc):
        self.brain = brain
        self.reward_calc = reward_calc
        self.trajectory = TrajectoryBuffer()
        self._cycle = 0

        self._prev_state = None
        self._prev_action = None
        self._prev_params = None
        self._prev_value = None
        self._prev_log_prob = None

        self._episode_reward = 0.0
        self._best_ep_reward = -1e9

        if not brain._compiled:
            compile_model_v2(brain.model, LEARNING_RATE)
            brain._compiled = True

    def store_experience(self, state_vec, score_diff, action_idx, params, value, log_prob, done=False):
        reward = self.reward_calc.calculate(score_diff)
        self._episode_reward += reward

        if self._prev_state is not None:
            self.trajectory.store(
                self._prev_state,
                self._prev_action,
                self._prev_params,
                reward,
                self._prev_value,
                self._prev_log_prob,
                done=done,
            )

        self._prev_state = state_vec.copy()
        self._prev_action = action_idx
        self._prev_params = params.copy()
        self._prev_value = value
        self._prev_log_prob = log_prob
        self._cycle += 1

        if self._cycle % TRAIN_EVERY == 0 and len(self.trajectory) >= MINIBATCH_SIZE:
            self._train()

        if self._cycle % SAVE_EVERY == 0:
            self.brain.save_weights()
            avg_reward = np.mean(_global_episode_accum[-20:]) if _global_episode_accum else 0.0
            logger.info(
                f"[PPOTrainer] ciclo={self._cycle} | "
                f"buffer={len(self.trajectory)} | "
                f"ep_reward={self._episode_reward:.1f} | "
                f"avg20={avg_reward:.1f}"
            )

    def end_episode(self):
        if self._prev_state is not None and len(self.trajectory) > 0:
            self.trajectory.dones[-1] = True

        _global_episode_accum.append(self._episode_reward)

        if self._episode_reward > self._best_ep_reward:
            self._best_ep_reward = self._episode_reward
            self.brain.save_weights()

        self._episode_reward = 0.0
        self.reward_calc.reset()
        self._prev_state = None
        self._prev_action = None
        self._prev_params = None
        self._prev_value = None
        self._prev_log_prob = None

    def _train(self):
        states, actions, params, rewards, values, log_probs, dones = self.trajectory.get()
        n = len(states)
        if n < MINIBATCH_SIZE:
            return

        returns = self._compute_gae(rewards, dones, values)
        advantages = returns - values
        adv_mean = advantages.mean()
        adv_std = advantages.std() + 1e-8
        advantages = (advantages - adv_mean) / adv_std

        states_t = tf.constant(states)
        actions_t = tf.constant(actions)
        params_t = tf.constant(params)
        returns_t = tf.constant(returns)
        advantages_t = tf.constant(advantages)
        old_log_probs_t = tf.constant(log_probs)

        n_minibatches = max(1, n // MINIBATCH_SIZE)
        total_actor_loss = 0.0
        total_value_loss = 0.0
        total_entropy_loss = 0.0

        opt = self.brain.model.optimizer

        for _ in range(PPO_EPOCHS):
            indices = np.random.permutation(n)
            for mb in range(n_minibatches):
                batch = indices[mb * MINIBATCH_SIZE:(mb + 1) * MINIBATCH_SIZE]

                s_batch = tf.gather(states_t, batch)
                a_batch = tf.gather(actions_t, batch)
                p_batch = tf.gather(params_t, batch)
                r_batch = tf.gather(returns_t, batch)
                adv_batch = tf.gather(advantages_t, batch)
                old_lp_batch = tf.gather(old_log_probs_t, batch)

                with tf.GradientTape() as tape:
                    outputs = self.brain.model(s_batch, training=True)
                    new_probs = outputs["action_probs"]
                    new_params = outputs["action_params"]
                    new_values = tf.squeeze(outputs["value"], axis=-1)

                    action_mask = tf.one_hot(a_batch, N_ACTIONS)
                    selected_new_probs = tf.reduce_sum(new_probs * action_mask, axis=1)
                    new_log_probs = tf.math.log(selected_new_probs + 1e-10)

                    ratio = tf.exp(new_log_probs - old_lp_batch)
                    clipped_ratio = tf.clip_by_value(
                        ratio, 1.0 - CLIP_EPSILON, 1.0 + CLIP_EPSILON
                    )
                    actor_loss = -tf.reduce_mean(
                        tf.minimum(ratio * adv_batch, clipped_ratio * adv_batch)
                    )

                    value_loss = tf.reduce_mean(tf.square(new_values - r_batch))
                    param_loss = tf.reduce_mean(
                        tf.keras.losses.mse(p_batch, new_params)
                    )

                    entropy = -tf.reduce_sum(
                        new_probs * tf.math.log(new_probs + 1e-10), axis=1
                    )
                    entropy_loss = -tf.reduce_mean(entropy)

                    total_loss = (
                        actor_loss
                        + VALUE_COEF * value_loss
                        + LAMBDA_REGRESSION * param_loss
                        + ENTROPY_COEF * entropy_loss
                    )

                grads = tape.gradient(total_loss, self.brain.model.trainable_variables)
                if MAX_GRAD_NORM > 0:
                    grads, _ = tf.clip_by_global_norm(grads, MAX_GRAD_NORM)
                opt.apply_gradients(zip(grads, self.brain.model.trainable_variables))

                total_actor_loss += float(actor_loss)
                total_value_loss += float(value_loss)
                total_entropy_loss += float(entropy_loss)

        avg_actor = total_actor_loss / (PPO_EPOCHS * n_minibatches)
        avg_value = total_value_loss / (PPO_EPOCHS * n_minibatches)
        avg_entropy = total_entropy_loss / (PPO_EPOCHS * n_minibatches)

        logger.debug(
            f"[PPOTrainer] train n={n} | "
            f"actor={avg_actor:.4f} value={avg_value:.4f} "
            f"entropy={avg_entropy:.4f}"
        )

        self.brain.decay_epsilon()
        self.trajectory.clear()

    @staticmethod
    def _compute_gae(rewards, dones, values, gamma=GAMMA, lam=GAE_LAMBDA):
        n = len(rewards)
        advantages = np.zeros(n, dtype=np.float32)
        gae = 0.0
        for t in reversed(range(n)):
            if t == n - 1:
                next_val = 0.0 if dones[t] else values[t]
            else:
                next_val = values[t + 1]
            delta = rewards[t] + gamma * next_val * (1 - dones[t]) - values[t]
            gae = delta + gamma * lam * (1 - dones[t]) * gae
            advantages[t] = gae
        returns = advantages + np.array(values)
        return returns.astype(np.float32)
