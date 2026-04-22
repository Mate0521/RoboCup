"""
GameRules — lógica centralizada de situaciones especiales.

Responde a la pregunta: dado el play mode actual y el rol/número
del agente, ¿qué debe hacer?

Situaciones cubiertas:
  - Kick-off (propio y rival)
  - Tiro libre directo e indirecto (propio y rival)
  - Corner (propio y rival)
  - Saque de banda (propio y rival)
  - Saque de meta (propio y rival)
  - Penalti (propio y rival)
  - Offside
  - Gol (reposicionamiento)
  - Expulsión (reorganización de formación)
  - Medio tiempo / fin de partido
"""

from modules.perception import PlayMode, Perception
from modules.role_assignment import get_role, get_tactical_position, clamp_to_zone
from util.field_constants import (
    FREE_KICK_DISTANCE, KICKABLE_MARGIN,
    PENALTY_SPOT_L_X, PENALTY_SPOT_R_X, PENALTY_SPOT_Y,
    GOAL_L_X, GOAL_R_X,
    rival_goal_pos, my_goal_pos,
)
import math
import logging

logger = logging.getLogger(__name__)


class GameRules:
    """
    Evalúa el contexto del partido y retorna:
      - situation: string que indica qué tabla táctica usar
      - executor: si este agente es el que ejecuta la jugada
      - override_target: (x, y) posición forzada si aplica
      - wait: True si el agente debe quedarse quieto
    """

    def __init__(self, perception: Perception):
        self.perception = perception
        self._active_players = {1: 11, 2: 11}  # team_id → jugadores activos
        self._score = {1: 0, 2: 0}

    # ── API pública ───────────────────────────────────────────────────────────

    def evaluate(self) -> dict:
        """
        Retorna un dict con el contexto actual del partido:
          situation    → "base" | "defensive" | "offensive" | "set_attack" | "set_defense"
          executor     → bool (¿soy yo quien ejecuta la jugada muerta?)
          forced_pos   → (x, y) | None (posición forzada por regla)
          wait         → bool (¿debo quedarme quieto?)
          penalty_exec → bool (¿soy el ejecutor del penalti?)
        """
        state = self.perception.state
        pm    = state.play_mode

        result = {
            "situation":    "base",
            "executor":     False,
            "forced_pos":   None,
            "wait":         False,
            "penalty_exec": False,
        }

        # ── Fin de partido / pausa ────────────────────────────────────────────
        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            result["wait"] = True
            return result

        # ── Juego normal ──────────────────────────────────────────────────────
        if pm == PlayMode.PLAY_ON:
            result["situation"] = self._dynamic_situation()
            return result

        # ── Kick-off ──────────────────────────────────────────────────────────
        if pm in (PlayMode.KICK_OFF_L, PlayMode.KICK_OFF_R):
            return self._handle_kickoff(pm)

        # ── Tiro libre directo ────────────────────────────────────────────────
        if pm in (PlayMode.FREE_KICK_L, PlayMode.FREE_KICK_R):
            return self._handle_free_kick(pm, indirect=False)

        # ── Tiro libre indirecto ──────────────────────────────────────────────
        if pm in (PlayMode.INDIRECT_FREE_KICK_L, PlayMode.INDIRECT_FREE_KICK_R):
            return self._handle_free_kick(pm, indirect=True)

        # ── Corner ────────────────────────────────────────────────────────────
        if pm in (PlayMode.CORNER_KICK_L, PlayMode.CORNER_KICK_R):
            return self._handle_corner(pm)

        # ── Saque de banda ────────────────────────────────────────────────────
        if pm in (PlayMode.KICK_IN_L, PlayMode.KICK_IN_R):
            return self._handle_kick_in(pm)

        # ── Saque de meta ─────────────────────────────────────────────────────
        if pm in (PlayMode.GOAL_KICK_L, PlayMode.GOAL_KICK_R):
            return self._handle_goal_kick(pm)

        # ── Penalti ───────────────────────────────────────────────────────────
        if pm in (PlayMode.PENALTY_SETUP_L, PlayMode.PENALTY_SETUP_R,
                  PlayMode.PENALTY_READY_L, PlayMode.PENALTY_READY_R,
                  PlayMode.PENALTY_TAKEN_L, PlayMode.PENALTY_TAKEN_R):
            return self._handle_penalty(pm)

        # ── Offside / faltas ──────────────────────────────────────────────────
        if pm in (PlayMode.OFFSIDE_L, PlayMode.OFFSIDE_R,
                  PlayMode.FOUL_CHARGE_L, PlayMode.FOUL_CHARGE_R,
                  PlayMode.BACK_PASS_L, PlayMode.BACK_PASS_R,
                  PlayMode.FREE_KICK_FAULT_L, PlayMode.FREE_KICK_FAULT_R,
                  PlayMode.CATCH_FAULT_L, PlayMode.CATCH_FAULT_R):
            return self._handle_foul(pm)

        # ── Gol (breve espera antes del kick-off) ─────────────────────────────
        if pm in (PlayMode.GOAL_L, PlayMode.GOAL_R):
            result["wait"] = True
            result["situation"] = "base"
            return result

        return result

    def notify_red_card(self, team_side: str):
        """Llamar cuando el referee expulsa un jugador."""
        key = 1 if team_side == "l" else 2
        self._active_players[key] = max(7, self._active_players[key] - 1)
        side = self.perception.state.side
        my_key = 1 if side == "l" else 2
        if key == my_key:
            logger.warning(f"[GameRules] Expulsión propia — jugadores activos: {self._active_players[key]}")
        else:
            logger.info(f"[GameRules] Expulsión rival — sus jugadores: {self._active_players[key]}")

    def active_players(self, side: str) -> int:
        key = 1 if side == "l" else 2
        return self._active_players[key]

    # ── Handlers internos ─────────────────────────────────────────────────────

    def _my_side(self) -> str:
        return self.perception.state.side

    def _unum(self) -> int:
        return self.perception.state.unum

    def _is_my_play(self, pm: PlayMode) -> bool:
        """¿Es mi equipo quien ejecuta esta jugada muerta?"""
        side = self._my_side()
        my_modes = {
            "l": {PlayMode.KICK_OFF_L, PlayMode.FREE_KICK_L, PlayMode.CORNER_KICK_L,
                  PlayMode.KICK_IN_L, PlayMode.GOAL_KICK_L, PlayMode.INDIRECT_FREE_KICK_L,
                  PlayMode.PENALTY_SETUP_L, PlayMode.PENALTY_READY_L, PlayMode.PENALTY_TAKEN_L},
            "r": {PlayMode.KICK_OFF_R, PlayMode.FREE_KICK_R, PlayMode.CORNER_KICK_R,
                  PlayMode.KICK_IN_R, PlayMode.GOAL_KICK_R, PlayMode.INDIRECT_FREE_KICK_R,
                  PlayMode.PENALTY_SETUP_R, PlayMode.PENALTY_READY_R, PlayMode.PENALTY_TAKEN_R},
        }
        return pm in my_modes.get(side, set())

    def _dynamic_situation(self) -> str:
        """
        Durante PLAY_ON determina la situación táctica según
        quién está más cerca del balón.
        """
        state = self.perception
        if not state.can_see_ball():
            return "base"

        ball_dist  = state.state.ball_distance or 999
        min_opp    = min((o["distance"] for o in state.state.opponents), default=999)
        min_tmate  = min((t["distance"] for t in state.state.teammates), default=999)

        # Si yo o un compañero estamos más cerca que el rival → ataque
        if min(ball_dist, min_tmate) < min_opp - 3:
            return "offensive"
        # Si el rival está significativamente más cerca → defensa
        if min_opp < min(ball_dist, min_tmate) - 3:
            return "defensive"
        return "base"

    def _handle_kickoff(self, pm: PlayMode) -> dict:
        my_play = self._is_my_play(pm)
        unum    = self._unum()
        side    = self._my_side()

        # El unum 7 (mediocampista centro) ejecuta el kick-off
        executor = my_play and unum == 7

        # Durante kick-off del rival, todos deben estar en su mitad
        forced_pos = None
        if not my_play and unum not in (9, 10, 11):
            # Asegurar que los jugadores no ofensivos estén en su mitad
            tx, ty = get_tactical_position(unum, side, "set_defense")
            forced_pos = clamp_to_zone(tx, ty, unum, side)

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   forced_pos,
            "wait":         False,
            "penalty_exec": False,
        }

    def _handle_free_kick(self, pm: PlayMode, indirect: bool) -> dict:
        my_play  = self._is_my_play(pm)
        unum     = self._unum()
        side     = self._my_side()
        role     = get_role(unum)

        # El jugador más cercano al balón ejecuta (simplificación)
        # En la práctica el servidor lo detecta automáticamente
        executor = my_play and role in ("forward", "midfielder") and unum not in (6, 8)

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   None,
            "wait":         not my_play and not executor,
            "penalty_exec": False,
        }

    def _handle_corner(self, pm: PlayMode) -> dict:
        my_play = self._is_my_play(pm)
        unum    = self._unum()
        side    = self._my_side()
        role    = get_role(unum)

        # En corner propio: delanteros al área, mediocampistas arriba
        # En corner rival: todos atrás
        executor = my_play and unum in (9, 10, 11)

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   None,
            "wait":         False,
            "penalty_exec": False,
        }

    def _handle_kick_in(self, pm: PlayMode) -> dict:
        my_play = self._is_my_play(pm)
        unum    = self._unum()
        role    = get_role(unum)

        executor = my_play and role in ("midfielder", "forward")

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   None,
            "wait":         False,
            "penalty_exec": False,
        }

    def _handle_goal_kick(self, pm: PlayMode) -> dict:
        my_play = self._is_my_play(pm)
        unum    = self._unum()

        # El portero (unum 1) ejecuta el saque de meta
        executor = my_play and unum == 1

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   None,
            "wait":         False,
            "penalty_exec": False,
        }

    def _handle_penalty(self, pm: PlayMode) -> dict:
        my_play = self._is_my_play(pm)
        unum    = self._unum()
        side    = self._my_side()

        # El delantero centro (unum 10) ejecuta el penalti
        executor = my_play and unum == 10

        # Posición del punto de penalti
        spot_x = PENALTY_SPOT_R_X if side == "l" else PENALTY_SPOT_L_X

        # Posiciones reglamentarias durante el penalti
        forced_pos = None
        if not executor:
            if unum == 1 and not my_play:
                # Portero rival en la línea de meta
                goal_x = GOAL_R_X if side == "l" else GOAL_L_X
                forced_pos = (goal_x, 0.0)
            elif unum == 1 and my_play:
                # Portero propio se queda
                forced_pos = (GOAL_L_X if side == "l" else GOAL_R_X, 0.0)

        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     executor,
            "forced_pos":   forced_pos,
            "wait":         not executor and unum != 1,
            "penalty_exec": executor,
        }

    def _handle_foul(self, pm: PlayMode) -> dict:
        """Offside, falta — esperar y posicionarse."""
        my_play = self._is_my_play(pm)
        return {
            "situation":    "set_attack" if my_play else "set_defense",
            "executor":     False,
            "forced_pos":   None,
            "wait":         True,
            "penalty_exec": False,
        }