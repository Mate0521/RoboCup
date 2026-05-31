import logging
import math
import numpy as np

from coordination.blackboard import Blackboard

logger = logging.getLogger(__name__)


class GameAnalyzer:
    def __init__(self):
        self.cycle = 0
        self.metrics = {
            "possession_cycles": 0,
            "total_cycles": 0,
            "passes_attempted": 0,
            "passes_completed": 0,
            "kicks": 0,
            "dash_count": 0,
            "turn_count": 0,
            "ball_recoveries": 0,
            "possession_losses": 0,
            "interceptions": 0,
            "goals_scored": 0,
            "goals_conceded": 0,
            "last_touch_team": None,
            "prev_last_touch": None,
            "score_l": 0,
            "score_r": 0,
            "distance_covered": 0.0,
            "zone_exits": 0,
            "useless_kicks": 0,
        }
        self.agent_distances = {}
        self.possession_start_cycle = 0
        self.possession_sequences = []
        self.passes = []

    def update(self, my_side):
        bb = Blackboard()
        self.cycle += 1
        self.metrics["total_cycles"] = self.cycle

        state = bb.ball
        current_touch = state.get("last_touch_team")

        if current_touch == my_side:
            self.metrics["possession_cycles"] += 1
            if self.possession_start_cycle == 0:
                self.possession_start_cycle = self.cycle
        else:
            if self.possession_start_cycle > 0:
                duration = self.cycle - self.possession_start_cycle
                self.possession_sequences.append(duration)
            self.possession_start_cycle = 0

        if current_touch != self.metrics["prev_last_touch"]:
            if self.metrics["prev_last_touch"] == my_side and current_touch != my_side:
                self.metrics["possession_losses"] += 1
            elif current_touch == my_side and self.metrics["prev_last_touch"] != my_side:
                if self.metrics["prev_last_touch"] is not None:
                    self.metrics["ball_recoveries"] += 1
            self.metrics["prev_last_touch"] = current_touch

        score_l = bb.score.get("left", 0)
        score_r = bb.score.get("right", 0)
        if score_l > self.metrics["score_l"]:
            self.metrics["goals_scored" if my_side == "l" else "goals_conceded"] += 1
        if score_r > self.metrics["score_r"]:
            self.metrics["goals_scored" if my_side == "r" else "goals_conceded"] += 1
        self.metrics["score_l"] = score_l
        self.metrics["score_r"] = score_r

    def log_command(self, cmd_type):
        if cmd_type == "kick":
            self.metrics["kicks"] += 1
        elif cmd_type == "dash":
            self.metrics["dash_count"] += 1
        elif cmd_type == "turn":
            self.metrics["turn_count"] += 1

    def register_pass(self, success=True):
        self.metrics["passes_attempted"] += 1
        if success:
            self.metrics["passes_completed"] += 1

    def summary(self):
        tc = max(1, self.metrics["total_cycles"])
        pa = max(1, self.metrics["passes_attempted"])
        return {
            "posesion_%": round(self.metrics["possession_cycles"] / tc * 100, 1),
            "pases_completados": f"{self.metrics['passes_completed']}/{self.metrics['passes_attempted']}",
            "precision_pase_%": round(self.metrics["passes_completed"] / pa * 100, 1),
            "recuperaciones": self.metrics["ball_recoveries"],
            "perdidas": self.metrics["possession_losses"],
            "goles_favor": self.metrics["goals_scored"],
            "goles_contra": self.metrics["goals_conceded"],
            "distancia_recorrida_m": round(self.metrics["distance_covered"], 0),
            "kicks": self.metrics["kicks"],
            "dashes": self.metrics["dash_count"],
            "turns": self.metrics["turn_count"],
            "ratio_recuperacion/perdida": round(
                self.metrics["ball_recoveries"] / max(1, self.metrics["possession_losses"]), 2
            ),
        }
