"""
StateVector — vector de 58 features para la red neuronal.
Fix: importa State desde modules.fsm (no FSMState).
"""
import math
import numpy as np

from modules.perception import Perception, PlayMode
from util.field_constants import (
    normalize_x, normalize_y, normalize_dist, normalize_angle,
    normalize_stamina, is_in_penalty_area, is_near_boundary,
)

VECTOR_SIZE = 58

ROLE_IDX = {"goalkeeper": 0, "defender": 1, "midfielder": 2, "forward": 3}

# Importación diferida para evitar ciclos — se resuelve en build()
def _get_fsm_idx(fsm_state) -> int:
    from modules.fsm import State
    mapping = {
        State.WAIT:         0,
        State.SEARCH_BALL:  1,
        State.MOVE_TO_BALL: 2,
        State.KICK_BALL:    3,
        State.GO_TO_POS:    4,
        State.DEAD_BALL:    5,
    }
    return mapping.get(fsm_state, 0)

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


class StateVector:
    def __init__(self, perception: Perception, role: str, fsm_state,
                 target_x: float, target_y: float,
                 time_norm: float = 0.0, score_diff: float = 0.0,
                 players_active: int = 11):
        self.perception     = perception
        self.role           = role
        self.fsm_state      = fsm_state
        self.target_x       = target_x
        self.target_y       = target_y
        self.time_norm      = time_norm
        self.score_diff     = score_diff
        self.players_active = players_active

    def build(self) -> np.ndarray:
        v     = np.zeros(VECTOR_SIZE, dtype=np.float32)
        state = self.perception.state

        # [0-5] Balón
        if self.perception.can_see_ball():
            v[0] = normalize_dist(state.ball_distance or 0)
            v[1] = normalize_angle(state.ball_angle or 0)
            v[2] = float(max(-1.0, min(1.0, (state.ball_dist_change or 0) / 3.0)))
            v[3] = float(max(-1.0, min(1.0, (state.ball_dir_change or 0) / 10.0)))
            v[4] = 1.0
            v[5] = 1.0 if self.perception.is_ball_kickable() else 0.0

        # [6-12] Agente propio
        sx, sy = state.self_x, state.self_y
        v[6]  = normalize_x(sx) if sx is not None else 0.0
        v[7]  = normalize_y(sy) if sy is not None else 0.0
        v[8]  = normalize_stamina(state.stamina)
        v[9]  = float(min(1.0, state.effort))
        v[10] = normalize_dist(state.speed, max_dist=3.0)
        v[11] = normalize_angle(state.speed_dir)
        v[12] = normalize_angle(state.head_angle)

        # [13-16] Rol one-hot (4)
        v[13 + ROLE_IDX.get(self.role, 2)] = 1.0

        # [17-22] Estado FSM one-hot (6)
        v[17 + _get_fsm_idx(self.fsm_state)] = 1.0

        # [23-30] Play mode agrupado one-hot (8)
        pm = state.play_mode
        for i, name in enumerate(PM_GROUP_NAMES):
            if pm in PM_GROUPS[name]:
                v[23 + i] = 1.0
                break

        # [31-39] Compañeros más cercanos x3 + count
        teammates = sorted(state.teammates, key=lambda o: o["distance"])[:3]
        for i, t in enumerate(teammates):
            v[31 + i*2]     = normalize_dist(t["distance"])
            v[31 + i*2 + 1] = normalize_angle(t["angle"])
        v[37] = normalize_dist(float(len(state.teammates)), max_dist=10.0)

        # [40-48] Rivales más cercanos x3 + count
        opponents = sorted(state.opponents, key=lambda o: o["distance"])[:3]
        for i, o in enumerate(opponents):
            v[40 + i*2]     = normalize_dist(o["distance"])
            v[40 + i*2 + 1] = normalize_angle(o["angle"])
        v[46] = normalize_dist(float(len(state.opponents)), max_dist=10.0)

        # [49-52] Posición táctica
        v[49] = normalize_x(self.target_x)
        v[50] = normalize_y(self.target_y)
        if sx is not None and sy is not None:
            dist_t = math.hypot(self.target_x - sx, self.target_y - sy)
            v[51]  = normalize_dist(dist_t, max_dist=50.0)
            v[52]  = 1.0 if (
                (sx < 0 and state.side == "l") or
                (sx > 0 and state.side == "r")
            ) else 0.0

        # [53-57] Contexto del partido
        v[53] = float(self.time_norm)
        v[54] = float(max(-1.0, min(1.0, self.score_diff / 5.0)))
        v[55] = (self.players_active - 7) / 4.0
        if sx is not None and sy is not None:
            v[56] = 1.0 if is_in_penalty_area(sx, sy, state.side) else 0.0
            v[57] = 1.0 if is_near_boundary(sx, sy) else 0.0

        return v

    @staticmethod
    def size() -> int:
        return VECTOR_SIZE