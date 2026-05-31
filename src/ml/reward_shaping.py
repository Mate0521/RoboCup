import math
from modules.perception import Perception, PlayMode
from modules.role_assignment import get_strict_zone
from util.field_constants import is_near_boundary, FIELD_HALF_LEN, KICKABLE_MARGIN


class AdvancedReward:
    def __init__(self, perception, role, unum):
        self.perception = perception
        self.role = role
        self.unum = unum

        self._prev_ball_dist = None
        self._prev_play_mode = None
        self._prev_score_diff = 0.0
        self._prev_ball_pos = None
        self._possession_cycles = 0
        self._passes_completed = 0
        self._pass_attempted_prev = False
        self._prev_ball_kickable = False

    def calculate(self, score_diff):
        state = self.perception.state
        reward = 0.0

        delta_score = score_diff - self._prev_score_diff
        if delta_score > 0:
            reward += 12.0
        elif delta_score < 0:
            reward -= 12.0
        self._prev_score_diff = score_diff

        if self.perception.is_ball_kickable():
            reward += 0.15
            self._possession_cycles += 1
            if self._possession_cycles > 5:
                reward += 0.05
        else:
            self._possession_cycles = 0

        if not self._prev_ball_kickable and self.perception.is_ball_kickable():
            reward += 0.5
        self._prev_ball_kickable = self.perception.is_ball_kickable()

        if self.perception.can_see_ball():
            ball_dist = state.ball_distance or 999
            if self._prev_ball_dist is not None:
                delta_dist = self._prev_ball_dist - ball_dist
                if self.role in ("forward", "midfielder") and delta_dist > 0:
                    reward += 0.05 * min(delta_dist, 2.0)
                elif self.role == "defender" and ball_dist < 15:
                    reward += 0.03 * min(delta_dist, 1.0)
            self._prev_ball_dist = ball_dist
        else:
            self._prev_ball_dist = None

        sx = state.self_x
        sy = state.self_y
        if sx is not None and sy is not None:
            xmin, xmax, ymin, ymax = get_strict_zone(self.unum, state.side)
            if not (xmin <= sx <= xmax and ymin <= sy <= ymax):
                reward -= 0.6

            if is_near_boundary(sx, sy):
                reward -= 0.15

            if self.role in ("forward", "midfielder"):
                if state.side == "l" and sx > 0:
                    reward += 0.02
                elif state.side == "r" and sx < 0:
                    reward += 0.02
            elif self.role == "defender":
                if state.side == "l" and sx < -10:
                    reward += 0.02
                elif state.side == "r" and sx > 10:
                    reward += 0.02

        if self.perception.can_see_ball() and self.perception.is_ball_kickable():
            pass_angle = abs(state.ball_angle or 0)
            if self.role in ("midfielder", "forward") and pass_angle < 30:
                reward += 0.02

        pm = state.play_mode
        if pm in (PlayMode.OFFSIDE_L, PlayMode.OFFSIDE_R):
            if self.perception.is_my_team_kickoff():
                reward -= 0.5

        if pm == PlayMode.PLAY_ON:
            reward += 0.005

        if pm in (PlayMode.GOAL_L, PlayMode.GOAL_R):
            if self._prev_play_mode not in (PlayMode.GOAL_L, PlayMode.GOAL_R):
                pass

        self._prev_play_mode = pm
        return float(reward)

    def reset(self):
        self._prev_ball_dist = None
        self._prev_play_mode = None
        self._prev_score_diff = 0.0
        self._prev_ball_pos = None
        self._possession_cycles = 0
        self._passes_completed = 0
        self._prev_ball_kickable = False
