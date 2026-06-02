import sys
import os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
print("=== Test PPOTrainer v2 ===\n")

ml_available = False
try:
    import tensorflow as tf
    ml_available = True
except ImportError:
    pass

if not ml_available:
    print("[SKIP] TensorFlow no disponible - no se puede testear PPOTrainer")
    print("  Instale: pip install tensorflow")
    sys.exit(0)

from ml.model_v2 import AgentBrainV2, N_ACTIONS
from ml.ppo_trainer import PPOTrainer, TrajectoryBuffer, GAMMA, GAE_LAMBDA
from unittest.mock import Mock

# --- Test 1: TrajectoryBuffer ---
print("[1/6] Test TrajectoryBuffer...")
buf = TrajectoryBuffer(max_size=10)
assert len(buf) == 0
buf.store(np.zeros(128), 0, np.zeros(4), 1.0, 0.5, -0.5, done=False)
assert len(buf) == 1
buf.store(np.zeros(128), 1, np.zeros(4), 0.5, 0.6, -0.3, done=True)
states, actions, params, rewards, values, log_probs, dones = buf.get()
assert states.shape == (2, 128)
assert actions.shape == (2,)
assert rewards.shape == (2,)
assert dones[1] == 1.0
buf.clear()
assert len(buf) == 0
print("  [OK] TrajectoryBuffer funciona correctamente")

# --- Test 2: GAE computation ---
print("[2/6] Test GAE computation...")
from ml.ppo_trainer import PPOTrainer
rewards = np.array([1.0, 0.5, 0.0, 2.0], dtype=np.float32)
dones = np.array([0, 0, 0, 1], dtype=np.float32)
values = np.array([0.8, 0.6, 0.4, 0.5], dtype=np.float32)
returns = PPOTrainer._compute_gae(rewards, dones, values, gamma=0.99, lam=0.95)
assert returns.shape == (4,)
assert np.all(np.isfinite(returns))
print(f"  [OK] GAE returns: {returns}")

# --- Test 3: GAE with no dones ---
print("[3/6] Test GAE sin terminal state...")
rewards2 = np.array([1.0, 0.5, 0.0], dtype=np.float32)
dones2 = np.zeros(3, dtype=np.float32)
values2 = np.array([0.8, 0.6, 0.4], dtype=np.float32)
returns2 = PPOTrainer._compute_gae(rewards2, dones2, values2)
assert returns2.shape == (3,)
assert np.all(np.isfinite(returns2))
last_step_reward = 0.0
expected_last_return = values2[2] + (0.0 + 0.99 * values2[2] - values2[2])  # bootstrap from last value
assert abs(returns2[2] - expected_last_return) < 1e-4
print(f"  [OK] GAE sin dones: {returns2}")

# --- Test 4: GAE edge cases ---
print("[4/6] Test GAE casos borde...")
returns3 = PPOTrainer._compute_gae(
    np.array([0.0], dtype=np.float32),
    np.array([1.0], dtype=np.float32),
    np.array([0.0], dtype=np.float32),
)
assert returns3.shape == (1,)
assert returns3[0] == 0.0  # terminal state, no future
print(f"  [OK] GAE terminal: {returns3}")

# --- Test 5: AgentBrainV2 predict_with_log_prob ---
print("[5/6] Test predict_with_log_prob...")
brain = AgentBrainV2("midfielder", training=True)
state = np.zeros(128, dtype=np.float32)
action_idx, params, value, log_prob = brain.predict_with_log_prob(state)
assert 0 <= action_idx < N_ACTIONS
assert params.shape == (4,)
assert isinstance(value, float)
assert isinstance(log_prob, float)
assert log_prob < 0  # log probability is negative
print(f"  [OK] predict_with_log_prob: action={action_idx}, value={value:.4f}, log_prob={log_prob:.4f}")

# --- Test 6: PPOTrainer full cycle ---
print("[6/6] Test PPOTrainer step/train cycle...")
from unittest.mock import Mock
from ml.reward_shaping import AdvancedReward

perception = Mock()
perception.state.side = "l"
perception.state.self_x = 0.0
perception.state.self_y = 0.0
perception.state.stamina = 7500.0
perception.state.effort = 0.9
perception.state.ball_distance = 10.0
perception.state.ball_angle = 5.0
perception.state.time = 100
perception.can_see_ball.return_value = True
perception.is_ball_kickable.return_value = False

reward_calc = AdvancedReward(perception, "midfielder", 7)
trainer = PPOTrainer(brain, reward_calc)

state_vec = np.zeros(128, dtype=np.float32)
for i in range(10):
    action_idx, params, value, log_prob = trainer.step(state_vec, 0.0)
    assert 0 <= action_idx < N_ACTIONS
    assert params.shape == (4,)

assert trainer._prev_state is not None

trainer.end_episode()
assert trainer._prev_state is None
print(f"  [OK] PPOTrainer ciclo completo funcionando (10 steps + end_episode)")
print(f"  [OK] Trajectory size after train: {len(trainer.trajectory)}")
print()

# --- Summary ---
print("=" * 50)
print(f"[PASS] 6/6 tests PPO Trainer v2 OK")
print("=" * 50)
