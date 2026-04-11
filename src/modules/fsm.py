"""
FSM completa con:
- Portero dedicado con comportamiento propio
- Reconocimiento de todos los play modes
- Posicionamiento táctico dinámico
- Solución al bug de "se quedan quietos"
"""
from enum import Enum, auto
from modules.perception import Perception, PlayMode
from modules.role_assignment import get_role, get_tactical_position
from modules import actuators
import math
import logging

logger = logging.getLogger(__name__)

# Radio máximo del portero desde el arco
GOALKEEPER_RADIUS = 12.0
# Distancia para considerar que llegamos a la posición
POSITION_THRESHOLD = 3.0
# Distancia kickable real del servidor
KICKABLE_DIST = 0.7


class State(Enum):
    WAIT         = auto()
    SEARCH_BALL  = auto()
    MOVE_TO_BALL = auto()
    KICK_BALL    = auto()
    GO_TO_POS    = auto()
    DEFEND_GOAL  = auto()
    DEAD_BALL    = auto()


class FSM:
    def __init__(self, perception: Perception, role: str):
        self.perception = perception
        self.role = role
        self.state = State.WAIT
        self._search_dir = 1
        self._search_steps = 0
        self._target_x: float | None = None
        self._target_y: float | None = None

    def step(self) -> str | None:
        state  = self.perception.state
        pm     = state.play_mode

        # Juego terminado o pausa
        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            return None

        # Portero tiene su propia lógica
        if self.role == "goalkeeper":
            return self._goalkeeper_step()

        # Play modes detenidos
        if self._is_stopped_play(pm):
            return self._handle_dead_ball()

        # Juego normal
        return self._field_player_step()

    # ── Portero ───────────────────────────────────────────────────────────────

    def _goalkeeper_step(self) -> str | None:
        state = self.perception.state
        pm    = state.play_mode

        # Posicionarse al inicio
        if pm in (PlayMode.BEFORE_KICK_OFF, PlayMode.GOAL_L, PlayMode.GOAL_R):
            return self._go_to_position(-48, 0)

        # Atrapar si el balón viene directo
        if state.ball_is_moving_toward_goal() and state.ball_distance and state.ball_distance < 15:
            return actuators.catch(state.ball_angle or 0)

        # Si tenemos el balón, despejarlo
        if self.perception.is_ball_kickable():
            return actuators.kick(100, 0)

        # Mantenerse en posición con pequeños ajustes según el balón
        if self.perception.can_see_ball():
            # Moverse lateralmente según donde esté el balón (y)
            ball_y_estimate = (state.ball_distance or 0) * math.sin(
                math.radians(state.ball_angle or 0)
            )
            target_y = max(-7.0, min(7.0, ball_y_estimate * 0.3))
            return self._go_to_position(-48, target_y)

        # Sin ver el balón, volver al centro del arco
        return self._go_to_position(-48, 0)

    # ── Jugador de campo ──────────────────────────────────────────────────────

    def _field_player_step(self) -> str | None:
        self._update_state()
        return self._execute()

    def _update_state(self):
        perc = self.perception

        if self.state == State.WAIT:
            self.state = State.SEARCH_BALL

        elif self.state == State.SEARCH_BALL:
            if perc.can_see_ball():
                ball_dist = perc.state.ball_distance or 999
                # Solo ir al balón si estoy cerca tácticamente
                if ball_dist < self._my_action_radius():
                    self.state = State.MOVE_TO_BALL
                else:
                    self.state = State.GO_TO_POS

        elif self.state == State.MOVE_TO_BALL:
            if not perc.can_see_ball():
                self.state = State.SEARCH_BALL
            elif perc.is_ball_kickable():
                self.state = State.KICK_BALL
            elif (perc.state.ball_distance or 0) > self._my_action_radius() * 1.5:
                # El balón está muy lejos, volver a posición
                self.state = State.GO_TO_POS

        elif self.state == State.KICK_BALL:
            if not perc.is_ball_kickable():
                self.state = State.GO_TO_POS

        elif self.state == State.GO_TO_POS:
            if perc.can_see_ball():
                ball_dist = perc.state.ball_distance or 999
                if ball_dist < self._my_action_radius():
                    self.state = State.MOVE_TO_BALL

    def _execute(self) -> str | None:
        state = self.perception.state

        if self.state == State.SEARCH_BALL:
            self._search_steps += 1
            if self._search_steps > 6:
                self._search_steps = 0
                self._search_dir *= -1
            return actuators.turn(30 * self._search_dir)

        elif self.state == State.MOVE_TO_BALL:
            angle = state.ball_angle or 0.0
            if abs(angle) > 8:
                return actuators.turn(angle * 0.7)
            return actuators.dash(80)

        elif self.state == State.KICK_BALL:
            return self._decide_kick()

        elif self.state == State.GO_TO_POS:
            situation = self._get_situation()
            tx, ty = get_tactical_position(state.unum, state.side, situation)
            return self._go_to_position(tx, ty)

        return actuators.turn(10)

    def _decide_kick(self) -> str:
        """Kick hacia adelante o al compañero más cercano al arco rival."""
        # Por ahora patear hacia el arco rival
        # Aquí se integrará la red neuronal en la fase 3
        if self.perception.state.side == "l":
            return actuators.kick(100, 0)   # derecha = arco rival
        else:
            return actuators.kick(100, 180)  # izquierda = arco rival

    # ── Pelota muerta ─────────────────────────────────────────────────────────

    def _handle_dead_ball(self) -> str | None:
        state = self.perception.state
        pm    = state.play_mode

        if self.perception.is_my_team_kickoff():
            # Mi equipo ejecuta — el ejecutor va al balón, los demás se posicionan
            situation = "set_attack"
            tx, ty = get_tactical_position(state.unum, state.side, situation)
            if self.perception.can_see_ball():
                ball_dist = state.ball_distance or 999
                # El jugador más cercano es quien ejecuta
                if ball_dist < 5 and self.role != "goalkeeper":
                    if self.perception.is_ball_kickable():
                        return self._decide_kick()
                    angle = state.ball_angle or 0.0
                    if abs(angle) > 8:
                        return actuators.turn(angle * 0.7)
                    return actuators.dash(60)
            return self._go_to_position(tx, ty)
        else:
            # Rival ejecuta — alejarse 9.15 metros del balón (regla)
            situation = "set_defense"
            tx, ty = get_tactical_position(state.unum, state.side, situation)
            return self._go_to_position(tx, ty)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _go_to_position(self, tx: float, ty: float) -> str:
        """Navegar a (tx, ty) usando flags visibles si los hay."""
        state = self.perception.state

        # Estimar posición propia con flags del campo
        self_x, self_y = self._estimate_position()

        if self_x is not None and self_y is not None:
            dx = tx - self_x
            dy = ty - self_y
            dist = math.hypot(dx, dy)

            if dist < POSITION_THRESHOLD:
                return actuators.turn(5)  # Ya estamos ahí, small turn para seguir activos

            # Ángulo hacia el target en coordenadas del campo
            target_angle = math.degrees(math.atan2(dy, dx))
            # Diferencia con la orientación actual (aproximada)
            angle_diff = target_angle  # simplificación — mejorar con odometría
            if abs(angle_diff) > 10:
                return actuators.turn(max(-30, min(30, angle_diff)))
            power = min(100, dist * 3)
            return actuators.dash(power)

        # Sin posición estimada — buscar flags
        return actuators.turn(20)

    def _estimate_position(self) -> tuple[float | None, float | None]:
        """Estima posición usando flags visibles."""
        state = self.perception.state
        FLAG_POSITIONS = {
            "f c":     (0, 0),
            "f c t":   (0, 34),
            "f c b":   (0, -34),
            "f l t":   (-52.5, 34),
            "f l b":   (-52.5, -34),
            "f r t":   (52.5, 34),
            "f r b":   (52.5, -34),
            "f l 0":   (-52.5, 0),
            "f r 0":   (52.5, 0),
            "f t 0":   (0, 34),
            "f b 0":   (0, -34),
            "f g l b": (-52.5, -7.01),
            "f g l t": (-52.5, 7.01),
            "f g r b": (52.5, -7.01),
            "f g r t": (52.5, 7.01),
        }

        best = None
        best_dist = 999
        for obj in state.visible_objects:
            name = obj.get("name", "")
            if name in FLAG_POSITIONS and obj.get("distance", 999) < best_dist:
                best = (name, obj["distance"], obj["angle"])
                best_dist = obj["distance"]

        if best is None:
            return None, None

        name, dist, angle = best
        fx, fy = FLAG_POSITIONS[name]
        angle_rad = math.radians(angle)
        self_x = fx - dist * math.cos(angle_rad)
        self_y = fy - dist * math.sin(angle_rad)
        return self_x, self_y

    def _my_action_radius(self) -> float:
        """Radio de acción según el rol — evita que todos vayan al balón."""
        radii = {
            "goalkeeper": 15,
            "defender":   25,
            "midfielder": 35,
            "forward":    50,
        }
        return float(radii.get(self.role, 30))

    def _get_situation(self) -> str:
        """Determina la situación táctica actual."""
        state = self.perception.state
        pm    = state.play_mode

        if self._is_stopped_play(pm):
            return "set_attack" if self.perception.is_my_team_kickoff() else "set_defense"

        # Estimar si tenemos el balón (simplificado: teammate más cercano)
        if self.perception.can_see_ball():
            ball_dist = state.ball_distance or 999
            min_opp   = min((o["distance"] for o in state.opponents), default=999)
            if ball_dist < min_opp:
                return "offensive"
            else:
                return "defensive"

        return "base"

    def _is_stopped_play(self, pm: PlayMode) -> bool:
        return pm not in (
            PlayMode.PLAY_ON,
            PlayMode.BEFORE_KICK_OFF,
            PlayMode.KICK_OFF_L,
            PlayMode.KICK_OFF_R,
            PlayMode.HALF_TIME,
            PlayMode.TIME_OVER,
            PlayMode.GOAL_L,
            PlayMode.GOAL_R,
            PlayMode.UNKNOWN,
        )