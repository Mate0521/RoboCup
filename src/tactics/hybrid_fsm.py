import math
import logging
from enum import Enum

from modules import actuators
from modules.perception import PlayMode
from modules.role_assignment import get_tactical_position, clamp_to_zone
from util.field_constants import GOAL_L_X, GOAL_R_X, GOAL_WIDTH, KICKABLE_MARGIN
from coordination.blackboard import Blackboard

logger = logging.getLogger(__name__)

TURN_SPEED = 15.0
DASH_POWER = 75
NEAR_THRESHOLD = 1.5
PRESS_DURATION_MAX = 15


class State(Enum):
    BEFORE_KICK_OFF = 0
    PLAY_ON = 1
    GO_TO_POSITION = 2
    CHASE_BALL = 3
    KICK_BALL = 4
    DRIBBLE = 5
    SUPPORT = 6
    PRESS = 7
    DEFEND = 8
    INTERCEPT = 9


class HybridFSM:
    def __init__(self, perception, role, unum, side):
        self.perception = perception
        self.role = role
        self.unum = unum
        self.side = side
        self.state = State.GO_TO_POSITION
        self._last_state = None
        self._state_duration = 0
        self._search_accum = 0.0
        self._search_dir = 1 if unum % 2 == 0 else -1
        self._last_cmd = "turn 0"
        self._press_cycles = 0

    def step(self, pressing=False):
        pm = self.perception.state.play_mode

        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            return None

        if pm == PlayMode.BEFORE_KICK_OFF:
            self.state = State.BEFORE_KICK_OFF
            return None

        if self.role == "goalkeeper":
            return self._gk()

        if pm != PlayMode.PLAY_ON:
            self.state = State.PLAY_ON
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

    def _transition_to(self, new_state):
        if self.state != new_state:
            old = self.state
            self.state = new_state
            self._last_state = old
            self._state_duration = 0
            logger.debug(f"FSM: {old.name} -> {new_state.name}")
        else:
            self._state_duration += 1

    def _gk(self):
        state = self.perception.state
        gx = GOAL_L_X + 2 if self.side == "l" else GOAL_R_X - 2

        if self.perception.is_ball_kickable():
            self._transition_to(State.KICK_BALL)
            return self._pass_or_clear()

        bd = state.ball_distance
        ba = state.ball_angle
        if bd is not None and bd < 15:
            gy = max(-6, min(6, bd * 0.3 * math.sin(math.radians(ba or 0))))
            return self._navigate(gx, gy)

        if bd is not None and bd < 20 and abs(ba or 0) < 30:
            return actuators.catch(ba or 0)

        self._transition_to(State.GO_TO_POSITION)
        return self._navigate(gx, 0)

    def _play(self, pressing=False):
        state = self.perception.state
        perc = self.perception

        if perc.is_ball_kickable():
            return self._handle_kick_ball()

        bd = state.ball_distance
        radius = self._role_radius()
        if pressing:
            radius *= 1.6

        sx, sy = state.self_x, state.self_y

        chase_radii = {"goalkeeper": 8, "defender": 12, "midfielder": 18, "forward": 22}
        chase_radius = chase_radii.get(self.role, 15) * (1.6 if pressing else 1.0)

        if bd is not None and bd < chase_radius:
            return self._handle_chase()

        bb = Blackboard()
        ball_owner = bb.get_ball_owner()
        ball_pos = bb.ball.get("pos")

        owner_dist = None
        if ball_pos and len(ball_pos) >= 2 and ball_pos[0] is not None and sx is not None:
            owner_dist = math.hypot(sx - ball_pos[0], sy - ball_pos[1])
        else:
            return self._handle_go_to_position()

        if self.role == "defender":
            goal_x = GOAL_L_X if self.side == "l" else GOAL_R_X
            if abs(ball_pos[0] - goal_x) > 30:
                return self._handle_go_to_position()

        if self.role == "forward":
            if (self.side == "l" and ball_pos[0] < -15) or (self.side == "r" and ball_pos[0] > 15):
                if abs(sx - ball_pos[0]) > 25:
                    return self._handle_go_to_position()

        if owner_dist > 25:
            return self._handle_go_to_position()

        if ball_owner and ball_owner > 0 and ball_owner != self.unum:
            if self.role in ("midfielder", "forward"):
                return self._handle_support()
            if owner_dist < 20:
                return self._handle_support()
            return self._handle_go_to_position()

        if ball_owner is not None and ball_owner < 0:
            if ball_pos and self._is_threat(ball_pos):
                return self._handle_intercept()
            nearest = bb.am_i_nearest_to_ball(self.unum)
            if nearest and owner_dist < 20:
                return self._handle_press()
            return self._handle_defend()

        return self._handle_go_to_position()

    def _handle_kick_ball(self):
        self._transition_to(State.KICK_BALL)
        state = self.perception.state
        sx, sy = state.self_x, state.self_y

        if sx is not None:
            shot = self._shoot_on_goal(sx, sy)
            if shot is not None:
                return shot

        from tactics.pass_evaluation import PassEvaluator
        bb = Blackboard()
        teammates = bb.get_all_agents_positions()
        opponents = bb.get_all_opponents_positions()

        if not opponents:
            opponents = [{"x": o.get("x", 0), "y": o.get("y", 0)} for o in state.opponents]
        if not teammates:
            teammates = []

        if sx is not None and opponents:
            evaluator = PassEvaluator()
            best_pass = evaluator.evaluate(
                (sx, sy), self.side, teammates, opponents
            )
            if best_pass and best_pass.score > 0.6:
                angle = math.degrees(math.atan2(
                    best_pass.target_y - sy, best_pass.target_x - sx
                ))
                target_angle = angle - state.body_direction
                while target_angle > 180: target_angle -= 360
                while target_angle < -180: target_angle += 360
                power = min(60, max(15, best_pass.distance * 2.5))
                logger.info(f"[{self.unum}] PASE EVALUADO → #{best_pass.receiver_unum} "
                            f"score={best_pass.score:.2f} risk={best_pass.risk:.2f}")
                self._transition_to(State.SUPPORT)
                return actuators.kick(power, target_angle)

        return self._pass_to_teammate()

    def _shoot_on_goal(self, sx, sy):
        goal_x = GOAL_R_X if self.side == "l" else GOAL_L_X
        goal_y = 0.0
        dx = goal_x - sx
        dy = goal_y - sy
        dist = math.hypot(dx, dy)

        if dist > 30:
            return None

        angle = math.degrees(math.atan2(dy, dx))
        target_angle = angle - self.perception.state.body_direction
        while target_angle > 180: target_angle -= 360
        while target_angle < -180: target_angle += 360

        power = min(80, max(20, dist * 2.0))
        logger.info(f"[{self.unum}] TIRO A PORTERÍA ⚽ d={dist:.0f}m p={power:.0f}")
        self._transition_to(State.SUPPORT)
        return actuators.kick(power, target_angle)

    def _handle_chase(self):
        self._transition_to(State.CHASE_BALL)
        state = self.perception.state
        ba = state.ball_angle
        bd = state.ball_distance

        if ba is None:
            return self._search_ball()

        if abs(ba) > 8:
            turn = max(-20, min(20, ba * 0.35))
            return actuators.turn(turn)

        if bd is None:
            return actuators.dash(DASH_POWER)

        if bd < 0.7:
            return actuators.dash(6)

        if bd < 1.5:
            return actuators.dash(8)

        if bd < 3.0:
            return actuators.dash(20)

        if bd < 6.0:
            return actuators.dash(45)

        return actuators.dash(DASH_POWER)

    def _handle_support(self):
        self._transition_to(State.SUPPORT)
        bb = Blackboard()
        ball_owner = bb.get_ball_owner()
        ball_pos = bb.ball.get("pos")
        state = self.perception.state

        if ball_pos is None or not ball_pos[0]:
            return self._handle_go_to_position()

        sx, sy = state.self_x, state.self_y
        if sx is None:
            return self._search_ball()

        support_spread = {"defender": 18, "midfielder": 14, "forward": 10, "goalkeeper": 25}
        spread = support_spread.get(self.role, 14)
        role_angle_offset = {"defender": 0, "midfielder": 30, "forward": 60}
        base_angle = role_angle_offset.get(self.role, 30)

        parity = 1 if self.unum % 2 == 0 else -1
        offset_angle = math.radians(base_angle) * parity
        tx = ball_pos[0] + spread * math.cos(offset_angle)
        ty = ball_pos[1] + spread * math.sin(offset_angle)

        return self._navigate(tx, ty)

    def _handle_press(self):
        self._press_cycles += 1
        self._transition_to(State.PRESS)

        if self._press_cycles > PRESS_DURATION_MAX:
            self._press_cycles = 0
            return self._handle_go_to_position()

        state = self.perception.state
        bd = state.ball_distance
        ba = state.ball_angle

        if ba is None:
            return self._search_ball()

        bb = Blackboard()
        if not bb.am_i_nearest_to_ball(self.unum):
            self._press_cycles = 0
            return self._handle_defend()

        if bd is not None and bd < 5:
            if abs(ba or 0) > 6:
                turn = max(-15, min(15, (ba or 0) * 0.4))
                return actuators.turn(turn)
            return actuators.dash(60)

        if abs(ba or 0) > 10:
            turn = max(-15, min(15, (ba or 0) * 0.5))
            return actuators.turn(turn)

        return actuators.dash(DASH_POWER + 25)

    def _handle_defend(self):
        self._transition_to(State.DEFEND)
        bb = Blackboard()
        ball_pos = bb.ball.get("pos")
        state = self.perception.state
        sx, sy = state.self_x, state.self_y

        if ball_pos is None or sx is None:
            return self._search_ball()

        nearest_opponent = bb.get_nearest_opponent_to_ball()
        if nearest_opponent:
            ox, oy = nearest_opponent["pos"]
            cx = (ball_pos[0] + ox) / 2
            cy = (ball_pos[1] + oy) / 2
            return self._navigate(cx, cy)

        return self._handle_go_to_position()

    def _handle_intercept(self):
        self._transition_to(State.INTERCEPT)
        state = self.perception.state
        sx, sy = state.self_x, state.self_y

        goal_x = GOAL_L_X if self.side == "l" else GOAL_R_X
        inter_x = (sx + goal_x) / 2 if sx is not None else (goal_x + 10)
        inter_y = 0

        bb = Blackboard()
        ball_pos = bb.ball.get("pos")
        if ball_pos:
            inter_y = max(-15, min(15, ball_pos[1] * 0.7))

        return self._navigate(inter_x, inter_y)

    def _is_threat(self, ball_pos):
        if ball_pos is None:
            return False
        goal_x = GOAL_L_X if self.side == "l" else GOAL_R_X
        dx = abs(ball_pos[0] - goal_x)
        return dx < 25 and abs(ball_pos[1]) < 15

    def _handle_go_to_position(self):
        self._transition_to(State.GO_TO_POSITION)
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

    def _pass_to_teammate(self):
        state = self.perception.state

        if not state.teammates:
            return self._dribble_forward()

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

        return self._dribble_forward()

    def _dribble_forward(self):
        self._transition_to(State.DRIBBLE)
        state = self.perception.state
        sx, sy = state.self_x, state.self_y
        if sx is not None:
            shot = self._shoot_on_goal(sx, sy)
            if shot is not None:
                return shot
        fwd = 0 if self.side == "l" else 180
        return actuators.dash(12)

    def _pass_or_clear(self):
        state = self.perception.state
        for t in state.teammates:
            td = t.get("distance", 99)
            if 5 < td < 25:
                ta = t.get("angle", 0)
                return actuators.kick(min(50, td * 3), ta)
        return self._dribble_forward()

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
        from modules.role_assignment import get_strict_zone, clamp_to_zone
        from util.field_constants import clamp_to_field

        tx, ty = clamp_to_zone(tx, ty, self.unum, self.side)
        tx, ty = clamp_to_field(tx, ty, margin=0.5)

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

        if abs(diff) > 25:
            turn = max(-20, min(20, diff * 0.4))
            return actuators.turn(turn)

        power = max(20, min(90, dist * 3.0))
        return actuators.dash(power)

    def _role_radius(self):
        return {"goalkeeper": 15, "defender": 18, "midfielder": 28, "forward": 40}.get(self.role, 22)
