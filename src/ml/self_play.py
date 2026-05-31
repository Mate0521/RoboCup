import logging
import os
import numpy as np

from ml.model_v2 import AgentBrainV2, compile_model_v2, N_ACTIONS
from modules.state_vector_v2 import StateVectorV2

logger = logging.getLogger(__name__)


class SelfPlayManager:
    def __init__(self, role, checkpoint_dir="ml/checkpoints"):
        self.role = role
        self.checkpoint_dir = checkpoint_dir
        self.generation = 0
        self.best_score = -float("inf")
        os.makedirs(checkpoint_dir, exist_ok=True)

    def save_checkpoint(self, brain, score, episode):
        if score > self.best_score:
            self.best_score = score
            path = os.path.join(
                self.checkpoint_dir, f"{self.role}_gen{self.generation}_s{score:.1f}.weights.h5"
            )
            brain.save_weights(path)
            self.generation += 1
            logger.info(f"Checkpoint guardado: {path} (score={score:.1f})")

    def load_best(self, brain):
        checkpoints = [
            f for f in os.listdir(self.checkpoint_dir)
            if f.startswith(self.role) and f.endswith(".weights.h5")
        ]
        if not checkpoints:
            return False
        best = max(checkpoints, key=lambda f: float(f.split("_s")[1].split(".")[0]))
        path = os.path.join(self.checkpoint_dir, best)
        brain.model.load_weights(path)
        logger.info(f"Cargado mejor checkpoint: {path}")
        return True

    def create_opponent(self, brain, version=-1):
        opponent = AgentBrainV2(self.role, training=False)
        if version == -1:
            path = os.path.join(
                self.checkpoint_dir, f"{self.role}_gen{self.generation-1}_s*.weights.h5"
            )
            import glob
            matches = glob.glob(path)
            if matches:
                best = max(matches, key=os.path.getctime)
                opponent.model.load_weights(best)
        return opponent


class CurriculumScheduler:
    def __init__(self):
        self.level = 0
        self.levels = [
            {"name": "basic_passing", "num_opponents": 0, "reward_threshold": 0.8, "episodes": 200},
            {"name": "1v1", "num_opponents": 1, "reward_threshold": 0.7, "episodes": 500},
            {"name": "3v2", "num_opponents": 2, "reward_threshold": 0.65, "episodes": 1000},
            {"name": "5v5", "num_opponents": 5, "reward_threshold": 0.6, "episodes": 2000},
            {"name": "7v7", "num_opponents": 7, "reward_threshold": 0.55, "episodes": 3000},
            {"name": "11v11", "num_opponents": 11, "reward_threshold": 0.5, "episodes": 5000},
        ]

    def get_current_level(self):
        return self.levels[self.level]

    def should_advance(self, avg_reward):
        level = self.get_current_level()
        return avg_reward >= level["reward_threshold"]

    def advance(self):
        if self.level < len(self.levels) - 1:
            self.level += 1
            logger.info(f"Curriculum avanzado a nivel {self.level}: {self.levels[self.level]['name']}")
            return True
        return False
