import logging
import threading
import math

logger = logging.getLogger(__name__)

class Blackboard:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._data_lock = threading.Lock()
        self.reset()

    def reset(self):
        with self._data_lock:
            self.ball = {
                "pos": (None, None),
                "vel": (0.0, 0.0),
                "predicted_5": (None, None),
                "predicted_10": (None, None),
                "last_touch": None,
                "last_touch_team": None,
                "time": 0,
            }
            self.intents = {}
            self.zones = {}
            self.tactical = {
                "formation": "4-3-3",
                "phase": "possession",
                "pressing_active": False,
                "pressing_counter": 0,
                "strategy": "short_pass",
            }
            self.score = {"left": 0, "right": 0, "time": 0}
            self.roles = {}
            self.agent_positions = {}
            self.opponent_positions = {}
            self.ball_owner = None
            self.cycle = 0

    def update_ball(self, pos, vel, time):
        with self._data_lock:
            self.ball["pos"] = pos
            self.ball["vel"] = vel
            self.ball["time"] = time

    def update_agent_position(self, unum, pos, role):
        with self._data_lock:
            self.agent_positions[unum] = {"pos": pos, "role": role, "time": self.cycle}
            self.roles[unum] = role

    def update_opponent_position(self, unum, pos):
        with self._data_lock:
            self.opponent_positions[unum] = {"pos": pos, "time": self.cycle}

    def set_intent(self, unum, action, target, priority=0.5):
        with self._data_lock:
            self.intents[unum] = {
                "action": action,
                "target": target,
                "priority": priority,
                "cycle": self.cycle,
            }

    def clear_intents(self):
        with self._data_lock:
            self.intents = {}

    def get_nearest_to_ball(self, team="my"):
        with self._data_lock:
            bx, by = self.ball["pos"]
            if bx is None:
                return None
            positions = self.agent_positions if team == "my" else self.opponent_positions
            nearest = None
            min_dist = float("inf")
            for unum, data in positions.items():
                px, py = data["pos"]
                d = math.hypot(px - bx, py - by)
                if d < min_dist:
                    min_dist = d
                    nearest = unum
            return nearest

    def get_agents_by_role(self, role):
        with self._data_lock:
            return [u for u, r in self.roles.items() if r == role]

    def get_phase(self):
        with self._data_lock:
            return self.tactical["phase"]

    def set_phase(self, phase):
        with self._data_lock:
            self.tactical["phase"] = phase

    def get_ball_owner(self):
        with self._data_lock:
            return self.ball_owner

    def set_ball_owner(self, unum, team):
        with self._data_lock:
            self.ball_owner = unum
            self.ball["last_touch_team"] = team

    def is_my_team_possession(self, my_side):
        with self._data_lock:
            if self.ball["last_touch_team"] is None:
                return None
            return self.ball["last_touch_team"] == my_side

    def detect_possession_loss(self, my_side):
        with self._data_lock:
            if self.ball["last_touch_team"] is None:
                return False
            old_side = self.ball["last_touch_team"]
            return old_side == my_side and old_side != self.ball.get("_prev_team")

    def get_all_agents_positions(self):
        with self._data_lock:
            result = []
            for unum, data in self.agent_positions.items():
                px, py = data["pos"]
                if px is not None:
                    result.append({"unum": unum, "x": px, "y": py, "role": data.get("role", "")})
            return result

    def get_all_opponents_positions(self):
        with self._data_lock:
            result = []
            for oid, data in self.opponent_positions.items():
                px, py = data["pos"]
                if px is not None:
                    result.append({"id": oid, "x": px, "y": py})
            return result

    def get_agent_position(self, unum):
        with self._data_lock:
            data = self.agent_positions.get(unum)
            if data:
                return data["pos"]
            return (None, None)

    def am_i_nearest_to_ball(self, unum):
        with self._data_lock:
            bx, by = self.ball["pos"]
            if bx is None:
                return False
            my_pos = self.agent_positions.get(unum, {}).get("pos")
            if not my_pos or my_pos[0] is None:
                return False
            
            my_dist = math.hypot(my_pos[0] - bx, my_pos[1] - by)
            
            for other_unum, data in self.agent_positions.items():
                if other_unum == unum:
                    continue
                opx, opy = data["pos"]
                if opx is None:
                    continue
                other_dist = math.hypot(opx - bx, opy - by)
                if other_dist < my_dist - 1.5:
                    return False
                if abs(other_dist - my_dist) < 1.5 and other_unum < unum:
                    return False
            
            return True

    def get_nearest_opponent_to_ball(self):
        with self._data_lock:
            bx, by = self.ball["pos"]
            if bx is None:
                return None
            nearest = None
            min_dist = float("inf")
            for oid, data in self.opponent_positions.items():
                ox, oy = data["pos"]
                if ox is None:
                    continue
                d = math.hypot(ox - bx, oy - by)
                if d < min_dist:
                    min_dist = d
                    nearest = {"id": oid, "pos": (ox, oy), "dist": d}
            return nearest

    def get_agents_in_range(self, center_pos, max_dist):
        with self._data_lock:
            cx, cy = center_pos
            result = []
            for unum, data in self.agent_positions.items():
                px, py = data["pos"]
                if px is not None:
                    d = math.hypot(px - cx, py - cy)
                    if d <= max_dist:
                        result.append({"unum": unum, "pos": (px, py), "dist": d})
            return result

    def cycle_step(self):
        with self._data_lock:
            self.cycle += 1
            self.ball["_prev_team"] = self.ball["last_touch_team"]
