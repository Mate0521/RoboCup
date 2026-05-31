import math
import logging
from enum import Enum

from modules import actuators
from modules.perception import PlayMode
from modules.role_assignment import get_tactical_position, clamp_to_zone
from util.field_constants import GOAL_L_X, GOAL_R_X, KICKABLE_MARGIN

logger = logging.getLogger(__name__)

TURN_SPEED = 15.0
DASH_POWER = 70
NEAR_THRESHOLD = 1.5


class State(Enum):
    SEARCH = "search"
    CHASE = "chase"
    KICK = "kick"
    POSITION = "position"
    DEAD = "dead"


class HybridFSM:
    def __init__(self, perception, role, unum, side):
        self.perception = perception
        self.role = role
        self.unum = unum
        self.side = side
        self.state = State.POSITION
        self._search_accum = 0.0
        self._search_dir = 1 if unum % 2 == 0 else -1
        self._last_cmd = "turn 0"

    def step(self, pressing=False):
        pm = self.perception.state.play_mode

        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME, PlayMode.BEFORE_KICK_OFF):
            return None

        if self.role == "goalkeeper":
            return self._gk()

        if pm != PlayMode.PLAY_ON:
            my_modes = {
                PlayMode.KICK_OFF_L, PlayMode.FREE_KICK_L, PlayMode.CORNER_KICK_L,
                PlayMode.KICK_IN_L, PlayMode.GOAL_KICK_L, PlayMode.INDIRECT_FREE_KICK_L,
            } if self.side == "l" else {
                PlayMode.KICK_OFF_R, PlayMode.FREE_KICK_R, PlayMode.CORNER_KICK_R,
                PlayMode.KICK_IN_R, PlayMode.GOAL_KICK_R, PlayMode.INDIRECT_FREE_KICK_R,
            }
            if pm in my_modes and self.unum in (7, 9, 10, 11):
                return self._executor_deadball()
            return self._go_dead_position()

        return self._play(pressing)

    def _gk(self):
        state = self.perception.state
        gx = GOAL_L_X + 2 if self.side == "l" else GOAL_R_X - 2

        if self.perception.is_ball_kickable():
            self.state = State.KICK
            return self._pass_or_clear()

        bd = state.ball_distance
        ba = state.ball_angle
        if bd is not None and bd < 15:
            gy = max(-6, min(6, bd * 0.3 * math.sin(math.radians(ba or 0))))
            return self._navigate(gx, gy)

        if bd is not None and bd < 20 and abs(ba or 0) < 30:
            return actuators.catch(ba or 0)

        self.state = State.POSITION
        return self._navigate(gx, 0)

    def _play(self, pressing=False):
        state = self.perception.state
        perc = self.perception

        if perc.is_ball_kickable():
            self.state = State.KICK
            return self._pass_to_teammate()

        bd = state.ball_distance
        radius = self._role_radius()
        if pressing:
            radius *= 1.6

        if bd is not None and bd < radius:
            self.state = State.CHASE
            return self._chase_ball()

        sx, sy = state.self_x, state.self_y
        if sx is not None and bd is not None and bd < radius * 1.2:
            self.state = State.CHASE
            return self._chase_ball()

        self.state = State.POSITION
        return self._go_position()

    def _pass_to_teammate(self):
        state = self.perception.state

        if not state.teammates:
            fwd = 0 if self.side == "l" else 180
            return actuators.kick(30, fwd)

        team = []
        for t in state.teammates:
            td = t.get("distance", 99)
            ta = t.get("angle", 0)
            if td < 2 or td > 35:
                continue
            team.append((td, ta, 0.0))

        if team:
            team.sort(key=lambda x: x[0])
            for td, ta, _ in team:
                risk = 0
                for o in state.opponents:
                    od = o.get("distance", 99)
                    if abs(od - td) < 3 and abs(o.get("angle", 0) - ta) < 20:
                        risk += 1
                if risk < 2:
                    power = min(50, max(15, td * 3))
                    logger.info(f"[{self.unum}] PASE a {td:.0f}m ⦣{ta:.0f}° riesgo={risk}")
                    return actuators.kick(power, ta)

        for td, ta, _ in team[:3]:
            power = min(40, max(10, td * 2.5))
            logger.info(f"[{self.unum}] PASE ({td:.0f}m)")
            return actuators.kick(power, ta)

        fwd = 0 if self.side == "l" else 180
        return actuators.kick(20, fwd)

    def _pass_or_clear(self):
        state = self.perception.state
        for t in state.teammates:
            td = t.get("distance", 99)
            if 5 < td < 25:
                ta = t.get("angle", 0)
                return actuators.kick(min(50, td * 3), ta)
        fwd = 0 if self.side == "l" else 180
        return actuators.kick(40, fwd)

    def _chase_ball(self):
        state = self.perception.state
        ba = state.ball_angle
        bd = state.ball_distance

        if ba is None:
            return self._search_ball()

        if abs(ba) > 6:
            turn = max(-15, min(15, ba * 0.4))
            return actuators.turn(turn)

        if bd is not None and bd < 3:
            return actuators.dash(40)

        return actuators.dash(DASH_POWER)

    def _go_position(self):
        sit = "defensive" if self.role == "defender" else \
              "offensive" if self.role == "forward" else "base"
        tx, ty = get_tactical_position(self.unum, self.side, sit)
        tx, ty = clamp_to_zone(tx, ty, self.unum, self.side)

        state = self.perception.state
        sx, sy = state.self_x, state.self_y
        if sx is not None:
            d = math.hypot(tx - sx, ty - sy)
            if d < NEAR_THRESHOLD:
                return actuators.turn(2)

        return self._navigate(tx, ty)

    def _go_dead_position(self):
        sit = "set_attack" if self.role in ("forward", "midfielder") else "set_defense"
        tx, ty = get_tactical_position(self.unum, self.side, sit)
        tx, ty = clamp_to_zone(tx, ty, self.unum, self.side)
        return self._navigate(tx, ty)

    def _executor_deadball(self):
        state = self.perception.state
        if self.perception.is_ball_kickable():
            fwd = 0 if self.side == "l" else 180
            return actuators.kick(50, fwd)
        bd = state.ball_distance
        ba = state.ball_angle
        if bd is not None and bd < 15:
            if abs(ba or 0) > 8:
                return actuators.turn((ba or 0) * 0.4)
            return actuators.dash(40)
        return self._go_dead_position()

    def _search_ball(self):
        self._search_accum += TURN_SPEED
        if self._search_accum > 360:
            self._search_accum = 0
        return actuators.turn(TURN_SPEED)

    def _navigate(self, tx, ty):
        state = self.perception.state
        sx, sy = state.self_x, state.self_y
        if sx is None or sy is None:
            return self._search_ball()

        dx = tx - sx
        dy = ty - sy
        dist = math.hypot(dx, dy)

        if dist < NEAR_THRESHOLD:
            return actuators.turn(2)

        target_abs = math.degrees(math.atan2(dy, dx))
        diff = target_abs - state.body_direction
        while diff > 180: diff -= 360
        while diff < -180: diff += 360

        if abs(diff) > 8:
            turn = max(-15, min(15, diff))
            return actuators.turn(turn)

        power = max(15, min(70, dist * 2.5))
        return actuators.dash(power)

    def _role_radius(self):
        return {"goalkeeper": 15, "defender": 18, "midfielder": 28, "forward": 40}.get(self.role, 22)
