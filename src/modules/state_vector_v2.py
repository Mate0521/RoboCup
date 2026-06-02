import math
import numpy as np

from modules.perception import Perception, PlayMode
from util.field_constants import (
    normalize_x, normalize_y, normalize_dist, normalize_angle,
    normalize_stamina, is_in_penalty_area, is_near_boundary,
)

VECTOR_SIZE = 128

ROLE_IDX = {"goalkeeper": 0, "defender": 1, "midfielder": 2, "forward": 3}

PM_GROUPS = {
    "play_on":    {PlayMode.PLAY_ON},
    "kick_off":   {PlayMode.KICK_OFF_L, PlayMode.KICK_OFF_R},
    "free_kick":  {PlayMode.FREE_KICK_L, PlayMode.FREE_KICK_R,
                   PlayMode.INDIRECT_FREE_KICK_L, PlayMode.INDIRECT_FREE_KICK_R},
    "corner":     {PlayMode.CORNER_KICK_L, PlayMode.CORNER_KICK_R},
    "kick_in":    {PlayMode.KICK_IN_L, PlayMode.KICK_IN_R},
    "goal_kick":  {PlayMode.GOAL_KICK_L, PlayMode.GOAL_KICK_R},
    "penalty":    {PlayMode.PENALTY_SETUP_L, PlayMode.PENALTY_SETUP_R,
                   PlayMode.PENALTY_READY_L, PlayMode.PENALTY_READY_R,
                   PlayMode.PENALTY_TAKEN_L, PlayMode.PENALTY_TAKEN_R},
    "stopped":    {PlayMode.BEFORE_KICK_OFF, PlayMode.HALF_TIME,
                   PlayMode.TIME_OVER, PlayMode.GOAL_L, PlayMode.GOAL_R,
                   PlayMode.OFFSIDE_L, PlayMode.OFFSIDE_R,
                   PlayMode.FOUL_CHARGE_L, PlayMode.FOUL_CHARGE_R},
}
PM_GROUP_NAMES = list(PM_GROUPS.keys())


def _get_fsm_idx(fsm_state):
    from tactics.hybrid_fsm import State
    mapping = {
        State.BEFORE_KICK_OFF: 0, State.PLAY_ON: 1, State.GO_TO_POSITION: 2,
        State.CHASE_BALL: 3, State.KICK_BALL: 4, State.DRIBBLE: 5,
        State.SUPPORT: 6, State.PRESS: 7, State.DEFEND: 8, State.INTERCEPT: 9,
    }
    return mapping.get(fsm_state, 0)


class StateVectorV2:
    def __init__(self, perception, role, fsm_state,
                 target_x=0.0, target_y=0.0,
                 time_norm=0.0, score_diff=0.0, players_active=11,
                 ball_prediction=None, pass_eval=None):
        self.perception = perception
        self.role = role
        self.fsm_state = fsm_state
        self.target_x = target_x
        self.target_y = target_y
        self.time_norm = time_norm
        self.score_diff = score_diff
        self.players_active = players_active
        self.ball_prediction = ball_prediction or []
        self.pass_eval = pass_eval or {}

    def build(self):
        v = np.zeros(VECTOR_SIZE, dtype=np.float32)
        state = self.perception.state
        i = 0

        # [0-7] Balón
        if self.perception.can_see_ball():
            v[i] = normalize_dist(state.ball_distance or 0); i += 1
            v[i] = normalize_angle(state.ball_angle or 0); i += 1
            v[i] = float(max(-1.0, min(1.0, (state.ball_dist_change or 0) / 3.0))); i += 1
            v[i] = float(max(-1.0, min(1.0, (state.ball_dir_change or 0) / 10.0))); i += 1
            v[i] = 1.0; i += 1
            v[i] = 1.0 if self.perception.is_ball_kickable() else 0.0; i += 1
            if len(self.ball_prediction) >= 5:
                px, py = self.ball_prediction[4]
                v[i] = normalize_x(px); i += 1
                v[i] = normalize_y(py); i += 1
            else:
                i += 2
        else:
            i += 8

        # [8-15] Agente propio
        sx, sy = state.self_x, state.self_y
        v[i] = normalize_x(sx) if sx is not None else 0.0; i += 1
        v[i] = normalize_y(sy) if sy is not None else 0.0; i += 1
        v[i] = normalize_stamina(state.stamina); i += 1
        v[i] = float(min(1.0, state.effort)); i += 1
        v[i] = normalize_dist(state.speed, max_dist=3.0); i += 1
        v[i] = normalize_angle(state.speed_dir); i += 1
        v[i] = normalize_angle(state.head_angle); i += 1
        v[i] = normalize_angle(state.body_direction); i += 1

        # [16-19] Rol one-hot
        v[i + ROLE_IDX.get(self.role, 2)] = 1.0; i += 4

        # [20-29] FSM state one-hot (10)
        v[i + _get_fsm_idx(self.fsm_state)] = 1.0; i += 10

        # [30-38] Play mode one-hot (9)
        pm = state.play_mode
        for j, name in enumerate(PM_GROUP_NAMES):
            if pm in PM_GROUPS[name]:
                v[i + j] = 1.0
                break
        i += 9

        # [39-54] Compañeros top 4 (dist, angle, est_x, est_y) = 16
        teammates = sorted(state.teammates, key=lambda o: o["distance"])[:4]
        for t in teammates:
            v[i] = normalize_dist(t["distance"]); i += 1
            v[i] = normalize_angle(t["angle"]); i += 1
            t_ang = math.radians(t.get("angle", 0))
            total_ang = math.radians(state.body_direction + state.head_angle) + t_ang
            if sx is not None:
                ex = sx + t.get("distance", 0) * math.cos(total_ang)
                ey = sy + t.get("distance", 0) * math.sin(total_ang)
                v[i] = normalize_x(ex); i += 1
                v[i] = normalize_y(ey); i += 1
            else:
                i += 2
        i += (4 - len(teammates)) * 4

        # [55-70] Rivales top 4
        opponents = sorted(state.opponents, key=lambda o: o["distance"])[:4]
        for o in opponents:
            v[i] = normalize_dist(o["distance"]); i += 1
            v[i] = normalize_angle(o["angle"]); i += 1
            o_ang = math.radians(o.get("angle", 0))
            total_ang = math.radians(state.body_direction + state.head_angle) + o_ang
            if sx is not None:
                ex = sx + o.get("distance", 0) * math.cos(total_ang)
                ey = sy + o.get("distance", 0) * math.sin(total_ang)
                v[i] = normalize_x(ex); i += 1
                v[i] = normalize_y(ey); i += 1
            else:
                i += 2
        i += (4 - len(opponents)) * 4

        # [71-80] Posición táctica (10)
        v[i] = normalize_x(self.target_x); i += 1
        v[i] = normalize_y(self.target_y); i += 1
        if sx is not None:
            dist_t = math.hypot(self.target_x - sx, self.target_y - sy)
            v[i] = normalize_dist(dist_t, max_dist=50.0); i += 1
            v[i] = 1.0 if (
                (sx < 0 and state.side == "l") or
                (sx > 0 and state.side == "r")
            ) else 0.0; i += 1
        else:
            i += 2
        is_in_zone = 1.0
        from modules.role_assignment import get_strict_zone
        if sx is not None:
            xmin, xmax, ymin, ymax = get_strict_zone(state.unum, state.side)
            is_in_zone = 1.0 if (xmin <= sx <= xmax and ymin <= sy <= ymax) else 0.0
        v[i] = is_in_zone; i += 1
        v[i] = 1.0 if sx is not None and is_near_boundary(sx, sy) else 0.0; i += 1
        v[i] = 1.0 if sx is not None and is_in_penalty_area(sx, sy, state.side) else 0.0; i += 1

        if sx is not None:
            offside_x = 0.0 if state.side == "l" else 0.0
            v[i] = 1.0 if (state.side == "l" and sx > offside_x) or (state.side == "r" and sx < offside_x) else 0.0; i += 1
        else:
            i += 1
        i += 2

        # [81-90] Contexto partido (10)
        v[i] = float(self.time_norm); i += 1
        v[i] = float(max(-1.0, min(1.0, self.score_diff / 5.0))); i += 1
        v[i] = (self.players_active - 7) / 4.0; i += 1

        from coordination.blackboard import Blackboard
        bb = Blackboard()
        phase = bb.get_phase()
        phase_map = {"possession": 0, "pressing": 1, "defensive": 2}
        v[i] = phase_map.get(phase, 0) / 2.0; i += 1

        strategy_map = {"short_pass": 0, "counter": 1, "hold_ball": 2}
        strategy = bb.tactical.get("strategy", "short_pass")
        v[i] = strategy_map.get(strategy, 0) / 2.0; i += 1

        if sx is not None and self.perception.can_see_ball():
            ball_dist = state.ball_distance or 0
            v[i] = normalize_dist(
                len([t for t in state.teammates if t["distance"] < ball_dist + 5]),
                max_dist=4.0
            ); i += 1
        else:
            i += 1

        v[i] = float(len(state.teammates)) / 10.0; i += 1
        v[i] = float(len(state.opponents)) / 10.0; i += 1
        i += 2

        # [91-100] Predicciones (10)
        if self.ball_prediction:
            for step_idx in [2, 5, 8]:
                if step_idx < len(self.ball_prediction):
                    px, py = self.ball_prediction[step_idx]
                    v[i] = normalize_x(px); i += 1
                    v[i] = normalize_y(py); i += 1
                else:
                    i += 2
            near_rivals = len(state.opponents)
            v[i] = normalize_dist(float(near_rivals), max_dist=5.0); i += 1
        else:
            i += 7

        if sx is not None:
            for opp in state.opponents:
                od = opp.get("distance", 999)
                if od < 10:
                    o_angle_r = math.radians(opp.get("angle", 0))
                    total = math.radians(state.body_direction + state.head_angle) + o_angle_r
                    ox = sx + od * math.cos(total)
                    oy = sy + od * math.sin(total)
                    v[i] = normalize_x(ox); i += 1
                    v[i] = normalize_y(oy); i += 1
                    break
            else:
                i += 2
        else:
            i += 2
        i += 1

        # [101-110] Pases (10)
        pass_score = self.pass_eval.get("best_score", 0.0)
        pass_dist = self.pass_eval.get("best_distance", 0.0)
        pass_risk = self.pass_eval.get("best_risk", 1.0)
        v[i] = pass_score; i += 1
        v[i] = normalize_dist(pass_dist); i += 1
        v[i] = 1.0 - pass_risk; i += 1
        v[i] = self.pass_eval.get("openings_count", 0) / 5.0; i += 1
        v[i] = self.pass_eval.get("passing_lanes", 0) / 3.0; i += 1

        if sx is not None and self.perception.can_see_ball():
            bx = sx + (state.ball_distance or 0) * math.cos(math.radians(state.ball_angle or 0))
            by = sy + (state.ball_distance or 0) * math.sin(math.radians(state.ball_angle or 0))
            near_teammates = sum(
                1 for t in state.teammates
                if math.hypot(t["distance"] * math.cos(math.radians(t["angle"])),
                              t["distance"] * math.sin(math.radians(t["angle"]))) < 20
            )
            v[i] = near_teammates / 5.0; i += 1
        else:
            i += 1
        i += 3

        # [111-120] Historial (10) — reservado
        i += 10

        # [121-127] Embedding táctico (7) — reservado
        i += 7

        return v

    @staticmethod
    def size():
        return VECTOR_SIZE
