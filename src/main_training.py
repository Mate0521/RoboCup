import os
import time
import json
import logging
import threading
from datetime import datetime
from collections import deque

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

TRAINING_CONFIG = {
    "host": os.getenv("SERVER_IP", "rcssserver"),
    "port": int(os.getenv("SERVER_PORT", "6000")),
    "team_name": os.getenv("TEAM", "TrainingTeam").capitalize(),
    "num_agents": int(os.getenv("NUM_AGENTS", "11")),
    "max_episodes": int(os.getenv("MAX_EPISODES", "1000")),
    "max_cycles": int(os.getenv("MAX_CYCLES", "6000")),
    "save_dir": os.getenv("SAVE_DIR", "models"),
    "log_dir": os.getenv("LOG_DIR", "training_logs"),
    "opponent_team": os.getenv("OPPONENT", ""),
}

RENDERING_INTERVAL = 5
SUMMARY_INTERVAL = 30


class TrainingStats:
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self.episode_rewards = deque(maxlen=100)
        self.episode_lengths = deque(maxlen=100)
        self.episode_goals = deque(maxlen=100)
        self.episode_conceded = deque(maxlen=100)
        self.total_episodes = 0
        self.total_cycles = 0
        self.start_time = datetime.now()
        self._lock = threading.Lock()
        self.history = []

    def record_episode(self, reward, length, goals_for=0, goals_against=0):
        with self._lock:
            self.episode_rewards.append(reward)
            self.episode_lengths.append(length)
            self.episode_goals.append(goals_for)
            self.episode_conceded.append(goals_against)
            self.total_episodes += 1
            self.total_cycles += length
            entry = {
                "episode": self.total_episodes,
                "reward": round(reward, 2),
                "length": length,
                "goals_for": goals_for,
                "goals_against": goals_against,
                "timestamp": datetime.now().isoformat(),
            }
            self.history.append(entry)
            self._save_entry(entry)

    def _save_entry(self, entry):
        path = os.path.join(self.log_dir, "training_history.jsonl")
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_summary(self):
        with self._lock:
            if self.total_episodes == 0:
                return {}
            avg_r = sum(self.episode_rewards) / len(self.episode_rewards) if self.episode_rewards else 0
            avg_l = sum(self.episode_lengths) / len(self.episode_lengths) if self.episode_lengths else 0
            elapsed = (datetime.now() - self.start_time).total_seconds()
            return {
                "episodes": self.total_episodes,
                "avg_reward_100": round(avg_r, 2),
                "avg_length_100": round(avg_l, 1),
                "avg_goals_for": round(sum(self.episode_goals) / len(self.episode_goals), 2) if self.episode_goals else 0,
                "avg_goals_against": round(sum(self.episode_conceded) / len(self.episode_conceded), 2) if self.episode_conceded else 0,
                "total_cycles": self.total_cycles,
                "elapsed_hours": round(elapsed / 3600, 2),
                "cycles_per_sec": round(self.total_cycles / elapsed, 1) if elapsed > 0 else 0,
            }

    def print_summary(self):
        s = self.get_summary()
        if not s:
            return
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split(".")[0]
        print("\n" + "=" * 60)
        print(f"  TRAINING REPORT  -  {elapsed_str}")
        print("=" * 60)
        print(f"  Episodios:        {s['episodes']}")
        print(f"  Avg Reward (100): {s['avg_reward_100']}")
        print(f"  Avg Length (100): {s['avg_length_100']}")
        print(f"  Avg Goals For:    {s['avg_goals_for']}")
        print(f"  Avg Goals Agst:   {s['avg_goals_against']}")
        print(f"  Total Cycles:     {s['total_cycles']}")
        print(f"  Cycles/sec:       {s['cycles_per_sec']}")
        print(f"  Elapsed:          {elapsed_str}")
        print("=" * 60 + "\n")


class TrainingManager:
    def __init__(self, config=None):
        self.config = config or TRAINING_CONFIG
        self.stats = TrainingStats(self.config["log_dir"])
        self._running = False
        self._agent_threads = []

    def launch_single_agent(self, unum):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        os.environ["TRAINING"] = "true"
        os.environ["NUM_AGENTS"] = "1"

        from main import launch_agent
        launch_agent(
            host=self.config["host"],
            port=self.config["port"] + unum - 1,
            team_name=self.config["team_name"],
            unum=unum,
            training=True,
        )

    def launch_all_agents(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

        from main import launch_agent
        self._running = True

        for unum in range(1, self.config["num_agents"] + 1):
            time.sleep(0.15)
            t = threading.Thread(
                target=launch_agent,
                args=(
                    self.config["host"],
                    self.config["port"],
                    self.config["team_name"],
                    unum,
                    True,
                ),
                daemon=True,
                name=f"agent-{unum}",
            )
            t.start()
            self._agent_threads.append(t)

    def run(self):
        logger.info("=" * 50)
        logger.info("TRAINING v1.0.0 - Iniciando entrenamiento PPO")
        logger.info(f"  Host: {self.config['host']}:{self.config['port']}")
        logger.info(f"  Team: {self.config['team_name']}")
        logger.info(f"  Agents: {self.config['num_agents']}")
        logger.info(f"  Max episodes: {self.config['max_episodes']}")
        logger.info(f"  Save dir: {self.config['save_dir']}")
        logger.info("=" * 50)

        os.makedirs(self.config["save_dir"], exist_ok=True)
        os.makedirs(self.config["log_dir"], exist_ok=True)

        self.launch_all_agents()

        last_summary = time.time()
        try:
            while self._running:
                time.sleep(1)
                now = time.time()
                if now - last_summary >= SUMMARY_INTERVAL:
                    self.stats.print_summary()
                    last_summary = now

        except KeyboardInterrupt:
            logger.info("Deteniendo entrenamiento...")
            self._running = False

        self.stats.print_summary()
        logger.info("Entrenamiento finalizado")
        self._save_final_report()

    def _save_final_report(self):
        summary = self.stats.get_summary()
        report_path = os.path.join(self.config["log_dir"], "training_final.json")
        with open(report_path, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Reporte guardado: {report_path}")


def main():
    manager = TrainingManager()
    manager.run()


if __name__ == "__main__":
    main()
