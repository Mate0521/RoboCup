import logging

from coordination.blackboard import Blackboard

logger = logging.getLogger(__name__)


class StrategicPlanner:
    def __init__(self, team_name: str):
        self.team_name = team_name
        self.phase = "possession"
        self.pressing_counter = 0
        self.last_possession_side = None
        self.possession_loss_cycles = 0
        self.possession_gain_cycles = 0
        self.last_touch = None

    def update(self, my_side: str):
        bb = Blackboard()

        current_team = bb.ball.get("last_touch_team")

        if self.last_touch is None and current_team is not None:
            self.last_touch = current_team
            return

        if current_team != self.last_touch:
            if self.last_touch == my_side and current_team != my_side:
                self._on_possession_lost(my_side)
            elif current_team == my_side:
                self._on_possession_gained(my_side)
            self.last_touch = current_team

        if self.phase == "pressing":
            self.pressing_counter += 1
            if self.pressing_counter > 15:
                self._set_phase("defensive")
        else:
            self.pressing_counter = 0

        if current_team == my_side:
            self.possession_gain_cycles += 1
            self.possession_loss_cycles = 0
        elif current_team is not None:
            self.possession_loss_cycles += 1
            self.possession_gain_cycles = 0

        if self.phase == "defensive" and self.possession_gain_cycles > 3:
            self._set_phase("possession")

        bb.set_phase(self.phase)

    def _on_possession_lost(self, my_side):
        bb = Blackboard()
        ball_x = bb.ball["pos"][0]
        if ball_x is None:
            self._set_phase("defensive")
            return
        if my_side == "l" and ball_x > -10:
            self._set_phase("pressing")
        elif my_side == "r" and ball_x < 10:
            self._set_phase("pressing")
        else:
            self._set_phase("defensive")

    def _on_possession_gained(self, my_side):
        self._set_phase("possession")

    def _set_phase(self, phase):
        if phase != self.phase:
            self.phase = phase
            bb = Blackboard()
            bb.set_phase(phase)
            if phase == "pressing":
                self.pressing_counter = 0
            logger.info(f"[Estrategia] Fase → {phase}")
