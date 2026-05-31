import math
import logging

logger = logging.getLogger(__name__)

FLAGS = {
    "frt":  (52.5, -34.0), "fct":  (52.5,  0.0), "frt_b": (52.5,  34.0),
    "flt":  (0.0,  -34.0), "fct":  (0.0,   0.0), "flt_b": (0.0,   34.0),
    "glt":  (-52.5, -7.01),"gl":   (-52.5,  0.0),"glb":   (-52.5,  7.01),
    "grt":  (52.5,  -7.01),"gr":   (52.5,   0.0),"grb":   (52.5,   7.01),
    "plt":  (-36.0, -20.16),"plc":  (-36.0,  0.0),"plb":  (-36.0,  20.16),
    "prt":  (36.0,  -20.16),"prc":  (36.0,   0.0),"prb":  (36.0,   20.16),
    "t":    (0.0,   -34.0),"b":    (0.0,    34.0),
    "l":    (-52.5,  0.0), "r":   (52.5,   0.0),
    "t l 0": (-52.5, -34.0), "t r 0": (52.5, -34.0),
    "b l 0": (-52.5, 34.0), "b r 0": (52.5, 34.0),
    "f c t": (52.5, 0.0), "f c b": (52.5, 0.0),
    "f g t": (0.0, -34.0), "f g b": (0.0, 34.0),
    "c":     (0.0, 0.0),
    "c t":   (0.0, -34.0), "c b":  (0.0, 34.0),
    "l t":   (-52.5, -34.0), "l b": (-52.5, 34.0),
    "r t":   (52.5, -34.0), "r b":  (52.5, 34.0),
}

class EKFLocalizer:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.angle = 0.0
        self.confidence = 0.0
        self._initialized = False

    def update(self, visible_objects, body_direction, head_angle):
        flag_obs = [(o, d, a) for o, d, a in visible_objects if o in FLAGS]
        if not flag_obs:
            if not self._initialized:
                return False
            self.confidence *= 0.95
            return False

        best_x, best_y, best_err = None, None, None
        for i in range(len(flag_obs)):
            name_i, dist_i, ang_i = flag_obs[i]
            fx_i, fy_i = FLAGS.get(name_i)
            if fx_i is None:
                continue
            for j in range(i + 1, len(flag_obs)):
                name_j, dist_j, ang_j = flag_obs[j]
                fx_j, fy_j = FLAGS.get(name_j)
                if fx_j is None:
                    continue
                result = self._triangulate(
                    (fx_i, fy_i), dist_i, ang_i,
                    (fx_j, fy_j), dist_j, ang_j,
                    body_direction, head_angle,
                )
                if result is None:
                    continue
                cx, cy, err = result
                if best_err is None or err < best_err:
                    best_x, best_y, best_err = cx, cy, err

        if best_x is not None and best_err < 15.0:
            alpha = 0.05 if not self._initialized else 0.3
            if not self._initialized:
                self.x = best_x
                self.y = best_y
                self._initialized = True
                self.confidence = 0.5
            else:
                self.x += alpha * (best_x - self.x)
                self.y += alpha * (best_y - self.y)
            self.confidence = min(1.0, self.confidence + 0.01)
            logger.debug(f"Localizer: ({self.x:.1f}, {self.y:.1f}) err={best_err:.2f}")
            return True
        if self._initialized:
            self.confidence *= 0.98
        return False

    def _triangulate(self, pos_a, dist_a, ang_a, pos_b, dist_b, ang_b, body, neck):
        body_rad = math.radians(body)
        neck_rad = math.radians(neck)
        total_angle = body_rad + neck_rad

        abs_angle_a = total_angle + math.radians(ang_a)
        abs_angle_b = total_angle + math.radians(ang_b)

        x1, y1 = pos_a
        x2, y2 = pos_b

        sin_a = math.sin(abs_angle_a)
        cos_a = math.cos(abs_angle_a)
        sin_b = math.sin(abs_angle_b)
        cos_b = math.cos(abs_angle_b)

        ax = x1 + dist_a * cos_a
        ay = y1 + dist_a * sin_a
        bx = x2 + dist_b * cos_b
        by = y2 + dist_b * sin_b

        cx = (ax + bx) / 2.0
        cy = (ay + by) / 2.0
        err = math.hypot(ax - bx, ay - by)
        return (cx, cy, err)

    def get_position(self):
        if not self._initialized:
            return (None, None)
        return (self.x, self.y)

    def get_confidence(self):
        return self.confidence

    def reset(self):
        self._initialized = False
        self.x = 0.0
        self.y = 0.0
        self.confidence = 0.0
