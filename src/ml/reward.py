"""
Función de recompensa para el entrenamiento online (RL).

La recompensa es densa — se calcula cada ciclo del simulador,
no solo al marcar gol. Esto acelera el aprendizaje enormemente.

Componentes:
  + Gol propio          → +10.0
  - Gol rival           → -10.0
  + Acercarse al balón  → +0.1 (solo si es mi rol perseguirlo)
  + Balón en campo rival → +0.05
  + Posesión del balón  → +0.2
  - Fuera de zona       → -0.5
  - Cerca del límite    → -0.1
  + Pase completado     → +0.3 (estimado)
"""

from modules.perception import Perception, PlayMode
from modules.role_assignment import get_strict_zone
from util.field_constants import (
    is_near_boundary, FIELD_HALF_LEN, KICKABLE_MARGIN
)
import math


class RewardCalculator:
    def __init__(self, perception: Perception, role: str, unum: int):
        self.perception = perception
        self.role       = role
        self.unum       = unum

        # Estado previo para calcular deltas
        self._prev_ball_dist   = None
        self._prev_play_mode   = None
        self._prev_score_diff  = 0.0

    def calculate(self, score_diff: float) -> float:
        """
        Calcula la recompensa del ciclo actual.
        score_diff: goles_propios - goles_rivales
        """
        state  = self.perception.state
        reward = 0.0

        # ── Recompensa por gol ────────────────────────────────────────────────
        delta_score = score_diff - self._prev_score_diff
        if delta_score > 0:
            reward += 10.0 * delta_score
        elif delta_score < 0:
            reward += 10.0 * delta_score  # negativo

        self._prev_score_diff = score_diff

        # ── Recompensa por acercarse al balón (solo rol relevante) ────────────
        if self.perception.can_see_ball():
            ball_dist = state.ball_distance or 999
            if self._prev_ball_dist is not None:
                delta_dist = self._prev_ball_dist - ball_dist
                if self.role in ("forward", "midfielder") and delta_dist > 0:
                    reward += 0.1 * min(delta_dist, 2.0)
                elif self.role == "defender" and ball_dist < 15:
                    reward += 0.05 * min(delta_dist, 1.0)
            self._prev_ball_dist = ball_dist
        else:
            self._prev_ball_dist = None

        # ── Recompensa por posesión del balón ─────────────────────────────────
        if self.perception.is_ball_kickable():
            reward += 0.2

        # ── Recompensa por posición del balón en campo rival ──────────────────
        # (solo si podemos ver el balón y tiene posición estimada)
        sx = state.self_x
        sy = state.self_y
        if sx is not None and self.perception.can_see_ball():
            ball_abs_x = sx + (state.ball_distance or 0) * math.cos(
                math.radians(state.ball_angle or 0)
            )
            if state.side == "l" and ball_abs_x > 0:
                reward += 0.05
            elif state.side == "r" and ball_abs_x < 0:
                reward += 0.05

        # ── Penalización por salir de zona ────────────────────────────────────
        if sx is not None and sy is not None:
            xmin, xmax, ymin, ymax = get_strict_zone(self.unum, state.side)
            if not (xmin <= sx <= xmax and ymin <= sy <= ymax):
                reward -= 0.5

            # Penalización suave por acercarse al límite del campo
            if is_near_boundary(sx, sy):
                reward -= 0.1

        # ── Penalización por play mode desfavorable ───────────────────────────
        pm = state.play_mode
        if pm in (PlayMode.OFFSIDE_L, PlayMode.OFFSIDE_R):
            if self.perception.is_my_team_kickoff():
                reward -= 0.3  # offside propio

        self._prev_play_mode = pm
        return float(reward)

    def reset(self):
        self._prev_ball_dist  = None
        self._prev_play_mode  = None
        self._prev_score_diff = 0.0