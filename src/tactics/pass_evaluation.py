import math
import logging

logger = logging.getLogger(__name__)

W_DIST = 0.20
W_RISK = 0.35
W_SPACE = 0.25
W_TACTICAL = 0.20
MAX_PASS_DISTANCE = 35.0
PASS_THRESHOLD = 0.50

SHORT_PASS_MAX = 12.0
SAFE_RECEPTOR_DIST = 5.0

class PassOption:
    def __init__(self, receiver_unum, target_x, target_y, distance, score, risk):
        self.receiver_unum = receiver_unum
        self.target_x = target_x
        self.target_y = target_y
        self.distance = distance
        self.score = score
        self.risk = risk
        self.is_short = distance <= SHORT_PASS_MAX

    def __repr__(self):
        return f"Pass(r{self.receiver_unum} d={self.distance:.1f} s={self.score:.2f})"

class PassEvaluator:
    def __init__(self):
        self.ball_predictor = None

    def set_ball_predictor(self, predictor):
        self.ball_predictor = predictor

    def evaluate(self, passer_pos, passer_side, teammates, opponents, ball_pos=None):
        if not teammates:
            return None

        best_pass = None

        for tm in teammates:
            rx, ry = tm["pos"] if "pos" in tm else (tm.get("x", 0), tm.get("y", 0))
            dist = math.hypot(rx - passer_pos[0], ry - passer_pos[1])

            if dist > MAX_PASS_DISTANCE:
                continue

            angle = math.degrees(math.atan2(
                ry - passer_pos[0], rx - passer_pos[1]
            ))

            dist_score = 1.0 - (dist / MAX_PASS_DISTANCE)

            risk, interceptor = self._calculate_risk(
                passer_pos, (rx, ry), opponents
            )
            risk_score = 1.0 - risk

            space_score = self._calculate_receiver_space(
                (rx, ry), teammates, opponents
            )

            tactical_score = self._calculate_tactical_value(
                (rx, ry), dist, passer_side
            )

            pass_score = (
                W_DIST * dist_score
                + W_RISK * risk_score
                + W_SPACE * space_score
                + W_TACTICAL * tactical_score
            )

            option = PassOption(
                tm["unum"], rx, ry, dist, pass_score, risk
            )

            if best_pass is None or pass_score > best_pass.score:
                best_pass = option

        if best_pass and best_pass.score >= PASS_THRESHOLD:
            return best_pass
        return None

    def _calculate_risk(self, passer_pos, receiver_pos, opponents):
        px1, py1 = passer_pos
        px2, py2 = receiver_pos

        dx = px2 - px1
        dy = py2 - py1
        line_len = math.hypot(dx, dy)
        if line_len < 0.01:
            return (0.0, None)

        min_risk = float("inf")
        closest_interceptor = None
        for opp in opponents:
            ox = opp.get("x", 0)
            oy = opp.get("y", 0)
            t = ((ox - px1) * dx + (oy - py1) * dy) / (line_len * line_len)
            t = max(0.0, min(1.0, t))
            proj_x = px1 + t * dx
            proj_y = py1 + t * dy
            dist_to_line = math.hypot(ox - proj_x, oy - proj_y)
            if dist_to_line < 3.0:
                risk = max(0.0, 1.0 - dist_to_line / 3.0)
                if risk < min_risk:
                    min_risk = risk
                    closest_interceptor = opp.get("unum")

        if min_risk == float("inf"):
            return (0.0, None)
        return (min_risk, closest_interceptor)

    def _calculate_receiver_space(self, pos, teammates, opponents):
        min_enemy_dist = float("inf")
        for opp in opponents:
            d = math.hypot(opp["x"] - pos[0], opp["y"] - pos[1])
            if d < min_enemy_dist:
                min_enemy_dist = d
        for tm in teammates:
            d = math.hypot(tm["x"] - pos[0], tm["y"] - pos[1])
            if 0.5 < d < min_enemy_dist:
                min_enemy_dist = d
        safe_dist = min_enemy_dist if min_enemy_dist != float("inf") else 20.0
        return min(1.0, safe_dist / SAFE_RECEPTOR_DIST)

    def _calculate_tactical_value(self, pos, dist, side):
        x, y = pos
        if side == "l":
            if x > 0:
                return 0.6 + 0.4 * min(1.0, x / 52.5)
            return 0.2 + 0.3 * min(1.0, (x + 52.5) / 52.5)
        else:
            if x < 0:
                return 0.6 + 0.4 * min(1.0, abs(x) / 52.5)
            return 0.2 + 0.3 * min(1.0, (52.5 - x) / 52.5)

    def find_possession_pass(self, passer_pos, passer_side, teammates, opponents):
        best = self.evaluate(passer_pos, passer_side, teammates, opponents)
        if best and best.score >= PASS_THRESHOLD:
            return best
        safe = self._find_safe_possession_pass(passer_pos, teammates, opponents)
        return safe

    def _find_safe_possession_pass(self, passer_pos, teammates, opponents):
        safest = None
        best_score = -1.0
        for tm in teammates:
            rx = tm.get("x", 0)
            ry = tm.get("y", 0)
            dist = math.hypot(rx - passer_pos[0], ry - passer_pos[1])
            if dist < 1.0 or dist > SHORT_PASS_MAX:
                continue
            risk, _ = self._calculate_risk(passer_pos, (rx, ry), opponents)
            if risk < 0.4:
                safety = 1.0 - risk
                if safety > best_score:
                    best_score = safety
                    safest = PassOption(tm["unum"], rx, ry, dist, safety, risk)
        return safest
