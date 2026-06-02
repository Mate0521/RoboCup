import logging
import time
import math

from comunication.client import RCSSClient
from comunication.parser import parse
from modules.perception import Perception, PlayMode
from modules import actuators
from modules.role_assignment import get_role, get_tactical_position, clamp_to_zone

from perception.localizer import Localizer
from prediction.ball_predictor import BallPredictor
from tactics.hybrid_fsm import HybridFSM
from coordination.blackboard import Blackboard

logger = logging.getLogger(__name__)


class Agent:
    def __init__(self, host, port, team_name, unum, training=False):
        self.host = host
        self.port = port
        self.team_name = team_name
        self.unum = unum
        self._training = training

        self.client = RCSSClient(host, port)
        self.perception = Perception(team_name=team_name)
        self.localizer = Localizer()
        self.ball_predictor = BallPredictor()
        self.blackboard = Blackboard()

        self._running = False
        self._role = None
        self._side = None
        self._initial_positioned = False
        self._view_set = False
        self._controller = None
        self._brain = None
        self._trainer = None
        self._last_pm = None
        self._prev_ball_pos = None
        self._prev_ball_vel = (0.0, 0.0)
        self._lost_ball_count = 0
        self._had_ball_last = False
        self._cycles_in_before_kickoff = 0

    def connect(self):
        logger.info(f"[{self.unum}] Conectando...")
        resp = self.client.init(self.team_name)
        if not resp:
            return False
        parsed = parse(resp)
        if parsed["type"] == "error":
            logger.error(f"[{self.unum}] Error: {parsed['data']}")
            return False
        if parsed["type"] == "init":
            self.perception.update(parsed)
            self._side = self.perception.state.side
            self._role = get_role(self.unum)
            logger.info(f"[{self.unum}] OK | {self._side} | {self._role}")
            self.blackboard.update_agent_position(self.unum, (0, 0), self._role)
            return True
        return False

    def run(self):
        if not self.connect():
            return
        self._running = True
        logger.info(f"[{self.unum}] Loop")
        try:
            while self._running:
                has_sense = False
                timeouts = 0
                for _ in range(30):
                    msg = self.client.receive()
                    if msg is None:
                        timeouts += 1
                        if timeouts >= 5:
                            break
                        continue
                    parsed = parse(msg)
                    self.perception.update(parsed)
                    t = parsed["type"]
                    d = parsed.get("data", {})

                    if self.perception.state.play_mode == PlayMode.TIME_OVER:
                        self._running = False
                        break

                    if t == "see":
                        self._on_see(d)
                    elif t == "sense_body" and not has_sense:
                        has_sense = True
                        self._on_sense()
                    elif t == "hear":
                        s = d.get("sender", "")
                        if s == "referee":
                            m = d.get("message", "")
                            if m in ("goal_l", "goal_r"):
                                self._initial_positioned = False
                                self._fsm = None

                if not self._running:
                    break

                cmd = self._decide()
                if cmd:
                    self.client.send(cmd)
                else:
                    self.client.send(actuators.turn(3))
        except Exception as e:
            logger.error(f"[{self.unum}] Error: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _on_see(self, data):
        objs = []
        for o in data.get("objects", []):
            n, di, a = o.get("name", ""), o.get("distance"), o.get("angle")
            if di is not None and a is not None:
                objs.append((n, di, a))

        bd, hd = self.perception.state.body_direction, self.perception.state.head_angle
        self.localizer.update(objs, bd, hd)
        pos = self.localizer.get_position()
        if pos[0] is not None:
            self.perception.state.self_x = pos[0]
            self.perception.state.self_y = pos[1]
            self.blackboard.update_agent_position(self.unum, pos, self._role)

        sx, sy = (pos[0], pos[1]) if pos[0] is not None else (0, 0)
        for n, di, a in objs:
            if n == "b":
                ar = math.radians(a + bd + hd)
                bx = sx + di * math.cos(ar)
                by = sy + di * math.sin(ar)
                if self._prev_ball_pos:
                    self._prev_ball_vel = (bx - self._prev_ball_pos[0], by - self._prev_ball_pos[1])
                self._prev_ball_pos = (bx, by)
                self.blackboard.update_ball((bx, by), self._prev_ball_vel, self.perception.state.time)
            elif n.startswith("p") and " " in n:
                parts = n.split()
                if len(parts) > 1 and parts[1].strip('"') != self.team_name:
                    ar = math.radians(a + bd + hd)
                    ox = sx + di * math.cos(ar)
                    oy = sy + di * math.sin(ar)
                    self.blackboard.update_opponent_position(0, (ox, oy))

    def _on_sense(self):
        self.blackboard.cycle_step()
        had = self._had_ball_last
        has = self.perception.is_ball_kickable()
        self._had_ball_last = has

        if has:
            self.blackboard.set_ball_owner(self.unum, self._side)
            self._lost_ball_count = 0
        elif had and not has:
            self._lost_ball_count = 1
        elif not had and not has:
            if self._lost_ball_count > 0:
                self._lost_ball_count += 1

    def _decide(self):
        s = self.perception.state
        pm = s.play_mode
        unum = s.unum or self.unum

        if self._role is None:
            self._role = get_role(unum)
        if self._side is None:
            self._side = s.side

        if not self._view_set and unum > 0:
            self._view_set = True
            return actuators.change_view("wide", "high")

        if pm != self._last_pm:
            logger.info(f"[{unum}] {pm.value}")
            if pm in (PlayMode.GOAL_L, PlayMode.GOAL_R, PlayMode.TIME_OVER, PlayMode.HALF_TIME):
                self._initial_positioned = False
                self._fsm = None
            self._last_pm = pm

        pressing = 1 <= self._lost_ball_count <= 20

        if pm == PlayMode.BEFORE_KICK_OFF:
            self._cycles_in_before_kickoff += 1
            if not self._initial_positioned and unum > 0:
                self._initial_positioned = True
                tx, ty = get_tactical_position(unum, self._side, "base")
                tx, ty = clamp_to_zone(tx, ty, unum, self._side)
                logger.info(f"[{unum}] Pos: ({tx:.1f}, {ty:.1f})")
                return actuators.move(tx, ty)
            if self._cycles_in_before_kickoff > 600:
                logger.warning(f"[{unum}] Forzando inicio tras {self._cycles_in_before_kickoff} ciclos")
                return actuators.turn(0)
            return actuators.turn(2)

        if self._controller is None:
            self._init_ml(unum)
            fsm = HybridFSM(self.perception, self._role, unum, self._side)
            from tactics.hybrid_controller import HybridController
            self._controller = HybridController(
                fsm=fsm,
                perception=self.perception,
                role=self._role,
                unum=unum,
                side=self._side,
                brain=self._brain,
                trainer=self._trainer,
            )

        cmd = self._controller.decide(pressing=pressing)

        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            return None

        return cmd if cmd is not None else actuators.turn(3)

    def _init_ml(self, unum):
        if not self._training:
            return
        try:
            from ml.model_v2 import AgentBrainV2
            self._brain = AgentBrainV2(self._role, training=True)

            from ml.reward_shaping import AdvancedReward
            reward_calc = AdvancedReward(self.perception, self._role, unum)

            from ml.ppo_trainer import PPOTrainer
            self._trainer = PPOTrainer(self._brain, reward_calc)

            import os
            os.makedirs("ml/weights", exist_ok=True)
            logger.info(f"[{unum}] ML iniciado (training mode) role={self._role}")
        except Exception as e:
            logger.warning(f"[{unum}] No se pudo inicializar ML: {e}")
            self._brain = None
            self._trainer = None
