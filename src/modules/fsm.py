"""
FSM — Máquina de estados finitos del agente.
Integrada con:
  - clamp_to_zone() de role_assignment (nunca sale de su zona)
  - field_constants (límites del campo)
  - GameRules (situaciones especiales)
  - Estimación de posición propia via flags

Estados:
  WAIT         → esperar (before_kick_off, half_time)
  SEARCH_BALL  → girar buscando el balón
  MOVE_TO_BALL → correr hacia el balón
  KICK_BALL    → patear (la red neuronal afina los parámetros)
  GO_TO_POS    → ir a posición táctica
  DEAD_BALL    → jugada muerta (tiro libre, corner, etc.)
"""

from enum import Enum, auto
import math
import logging

from modules.perception import Perception, PlayMode
from modules.role_assignment import (
    get_role, get_tactical_position, clamp_to_zone, get_strict_zone
)
from util.field_constants import (
    KICKABLE_MARGIN, GOAL_L_X, GOAL_R_X, GOAL_Y_TOP, GOAL_Y_BOT,
    clamp_to_field, is_near_boundary, FREE_KICK_DISTANCE,
    PENALTY_L_X_MAX, PENALTY_R_X_MIN,
)
from modules import actuators

logger = logging.getLogger(__name__)

POSITION_THRESHOLD = 2.5   # metros — distancia para considerar "llegué"
SEARCH_TURN_STEP   = 30.0  # grados por ciclo al buscar el balón


class State(Enum):
    WAIT         = auto()
    SEARCH_BALL  = auto()
    MOVE_TO_BALL = auto()
    KICK_BALL    = auto()
    GO_TO_POS    = auto()
    DEAD_BALL    = auto()


class FSM:
    def __init__(self, perception: Perception, role: str):
        self.perception = perception
        self.role       = role
        self.state      = State.WAIT

        self._search_dir    = 1
        self._search_steps  = 0
        self._current_target: tuple[float, float] | None = None

        # Para que decision.py pueda leer el estado actual
        self.current_state  = State.WAIT

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def step(self, game_context: dict | None = None) -> str | None:
        """
        game_context: resultado de GameRules.evaluate()
        Retorna el comando a enviar al servidor, o None.
        """
        state = self.perception.state
        pm    = state.play_mode

        # Fin de partido
        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            self.state = State.WAIT
            self.current_state = self.state
            return None

        # Portero con lógica propia
        if self.role == "goalkeeper":
            cmd = self._goalkeeper_step(game_context)
            self.current_state = self.state
            return cmd

        # Jugada muerta
        if game_context and self._is_dead_ball(pm):
            cmd = self._dead_ball_step(game_context)
            self.current_state = self.state
            return cmd

        # Juego normal
        cmd = self._field_player_step()
        self.current_state = self.state
        return cmd

    # ── Portero ───────────────────────────────────────────────────────────────

    def _goalkeeper_step(self, ctx: dict | None) -> str | None:
        state = self.perception.state
        pm    = state.play_mode
        side  = state.side

        # Posición base del portero
        gx = GOAL_L_X + 3 if side == "l" else GOAL_R_X - 3
        gy = 0.0

        # Jugada muerta — saque de meta lo ejecuta el portero
        if ctx and ctx.get("executor") and pm in (PlayMode.GOAL_KICK_L, PlayMode.GOAL_KICK_R):
            if self.perception.is_ball_kickable():
                return actuators.kick(80, 0)
            return self._navigate(gx, gy)

        # Balón peligroso entrando al área
        if self.perception.state.ball_is_moving_toward_goal() and \
           (state.ball_distance or 999) < 20:
            if self.perception.is_ball_kickable():
                return actuators.kick(100, 0)
            return actuators.catch(state.ball_angle or 0)

        # Si tenemos el balón
        if self.perception.is_ball_kickable():
            self.state = State.KICK_BALL
            return actuators.kick(80, 0)

        # Ajuste lateral según posición del balón
        if self.perception.can_see_ball():
            ball_y = (state.ball_distance or 0) * math.sin(
                math.radians(state.ball_angle or 0)
            )
            target_y = max(GOAL_Y_BOT + 1, min(GOAL_Y_TOP - 1, ball_y * 0.4))
            target_y, _ = clamp_to_zone(gx, target_y, 1, side)
            tx, ty = clamp_to_zone(gx, target_y, 1, side)
            return self._navigate(tx, ty)

        self.state = State.GO_TO_POS
        return self._navigate(gx, gy)

    # ── Jugador de campo ──────────────────────────────────────────────────────

    def _field_player_step(self) -> str | None:
        self._update_state()
        return self._execute()

    def _update_state(self):
        perc   = self.perception
        state  = perc.state
        radius = self._action_radius()

        if self.state == State.WAIT:
            self.state = State.SEARCH_BALL

        elif self.state == State.SEARCH_BALL:
            if perc.can_see_ball():
                dist = state.ball_distance or 999
                self.state = State.MOVE_TO_BALL if dist < radius else State.GO_TO_POS

        elif self.state == State.MOVE_TO_BALL:
            if not perc.can_see_ball():
                self.state = State.SEARCH_BALL
            elif perc.is_ball_kickable():
                self.state = State.KICK_BALL
            elif (state.ball_distance or 0) > radius * 1.4:
                self.state = State.GO_TO_POS

        elif self.state == State.KICK_BALL:
            if not perc.is_ball_kickable():
                self.state = State.GO_TO_POS

        elif self.state == State.GO_TO_POS:
            if perc.can_see_ball():
                dist = state.ball_distance or 999
                if dist < radius:
                    self.state = State.MOVE_TO_BALL

    def _execute(self) -> str | None:
        state = self.perception.state
        unum  = state.unum
        side  = state.side

        if self.state == State.SEARCH_BALL:
            self._search_steps += 1
            if self._search_steps > 5:
                self._search_steps = 0
                self._search_dir  *= -1
            return actuators.turn(SEARCH_TURN_STEP * self._search_dir)

        elif self.state == State.MOVE_TO_BALL:
            angle = state.ball_angle or 0.0
            if abs(angle) > 8:
                return actuators.turn(angle * 0.8)
            return actuators.dash(80)

        elif self.state == State.KICK_BALL:
            # La red neuronal sobreescribirá esto con parámetros más finos
            # Por ahora: patear hacia el arco rival
            return self._default_kick()

        elif self.state == State.GO_TO_POS:
            situation = self._situation()
            tx, ty = get_tactical_position(unum, side, situation)
            # SIEMPRE clampear a la zona estricta antes de navegar
            tx, ty = clamp_to_zone(tx, ty, unum, side)
            self._current_target = (tx, ty)
            return self._navigate(tx, ty)

        return actuators.turn(5)

    # ── Jugada muerta ─────────────────────────────────────────────────────────

    def _dead_ball_step(self, ctx: dict) -> str | None:
        state    = self.perception.state
        unum     = state.unum
        side     = state.side
        self.state = State.DEAD_BALL

        if ctx.get("wait"):
            return actuators.turn(1)  # micro-giro para seguir "activo"

        # Posición forzada por regla
        if ctx.get("forced_pos"):
            tx, ty = ctx["forced_pos"]
            tx, ty = clamp_to_zone(tx, ty, unum, side)
            return self._navigate(tx, ty)

        # Ejecutor — ir al balón y ejecutar
        if ctx.get("executor"):
            if self.perception.is_ball_kickable():
                return self._set_piece_kick()
            if self.perception.can_see_ball():
                angle = state.ball_angle or 0.0
                if abs(angle) > 8:
                    return actuators.turn(angle * 0.8)
                return actuators.dash(60)

        # Posicionarse tácticamente
        situation = ctx.get("situation", "base")
        tx, ty = get_tactical_position(unum, side, situation)
        tx, ty = clamp_to_zone(tx, ty, unum, side)
        return self._navigate(tx, ty)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _navigate(self, tx: float, ty: float) -> str:
        """
        Navega hacia (tx, ty) usando la posición estimada propia.
        Si no hay posición estimada, gira para buscar flags.
        """
        state = self.perception.state
        sx, sy = state.self_x, state.self_y

        if sx is None or sy is None:
            return actuators.turn(20)

        dx   = tx - sx
        dy   = ty - sy
        dist = math.hypot(dx, dy)

        if dist < POSITION_THRESHOLD:
            return actuators.turn(5)

        # Ángulo absoluto hacia el target
        target_abs_angle = math.degrees(math.atan2(dy, dx))

        # Diferencia con la dirección actual del cuerpo
        body_dir  = state.body_direction
        angle_diff = target_abs_angle - body_dir

        # Normalizar a [-180, 180]
        while angle_diff > 180:  angle_diff -= 360
        while angle_diff < -180: angle_diff += 360

        if abs(angle_diff) > 10:
            turn_amt = max(-30, min(30, angle_diff))
            return actuators.turn(turn_amt)

        power = min(100, dist * 4)
        return actuators.dash(power)

    # ── Kicks ─────────────────────────────────────────────────────────────────

    def _default_kick(self) -> str:
        """Patear al arco rival. La red neuronal refinará esto."""
        side = self.perception.state.side
        if side == "l":
            return actuators.kick(100, 0)
        return actuators.kick(100, 180)

    def _set_piece_kick(self) -> str:
        """Kick en jugada muerta — potencia moderada hacia adelante."""
        side = self.perception.state.side
        role = self.role
        if role == "goalkeeper":
            return actuators.kick(70, 0 if side == "l" else 180)
        return actuators.kick(85, 0 if side == "l" else 180)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _action_radius(self) -> float:
        """Radio de acción para ir al balón — evita que todos corran juntos."""
        return {"goalkeeper": 15, "defender": 25,
                "midfielder": 35, "forward": 50}.get(self.role, 30)

    def _situation(self) -> str:
        state = self.perception
        if not state.can_see_ball():
            return "base"
        ball_dist = state.state.ball_distance or 999
        min_opp   = min((o["distance"] for o in state.state.opponents), default=999)
        if ball_dist < min_opp - 3:
            return "offensive"
        if min_opp < ball_dist - 3:
            return "defensive"
        return "base"

    def _is_dead_ball(self, pm: PlayMode) -> bool:
        return pm not in (
            PlayMode.PLAY_ON, PlayMode.BEFORE_KICK_OFF,
            PlayMode.KICK_OFF_L, PlayMode.KICK_OFF_R,
            PlayMode.HALF_TIME, PlayMode.TIME_OVER,
            PlayMode.GOAL_L, PlayMode.GOAL_R, PlayMode.UNKNOWN,
        )

    def get_current_target(self) -> tuple[float, float] | None:
        return self._current_target