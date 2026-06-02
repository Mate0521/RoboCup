import math
import logging
import numpy as np

logger = logging.getLogger(__name__)

FLAGS = {
    "frt":  (52.5, -34.0), "fct":  (0.0,   0.0), "frt_b": (52.5,  34.0),
    "flt":  (0.0,  -34.0), "flt_b": (0.0,   34.0),
    "glt":  (-52.5, -7.01), "gl":  (-52.5,  0.0), "glb":  (-52.5,  7.01),
    "grt":  (52.5,  -7.01), "gr":  (52.5,   0.0), "grb":  (52.5,   7.01),
    "plt":  (-36.0, -20.16), "plc": (-36.0,  0.0), "plb":  (-36.0,  20.16),
    "prt":  (36.0,  -20.16), "prc": (36.0,   0.0), "prb":  (36.0,   20.16),
    "t":    (0.0,   -34.0),  "b":   (0.0,    34.0),
    "l":    (-52.5,  0.0),   "r":   (52.5,   0.0),
    "t l 0": (-52.5, -34.0), "t r 0": (52.5, -34.0),
    "b l 0": (-52.5, 34.0),  "b r 0": (52.5, 34.0),
    "f c t": (52.5, 0.0),    "f c b": (52.5, 0.0),
    "f g t": (0.0, -34.0),   "f g b": (0.0, 34.0),
    "c":     (0.0, 0.0),
    "c t":   (0.0, -34.0),   "c b":  (0.0, 34.0),
    "l t":   (-52.5, -34.0), "l b":  (-52.5, 34.0),
    "r t":   (52.5, -34.0),  "r b":  (52.5, 34.0),
}


class Localizer:
    def __init__(self):
        self.x = np.zeros(4)
        self.P = np.eye(4) * 50.0
        self.P[2:, 2:] *= 5.0
        self.Q = np.array([
            [0.01, 0.0, 0.02, 0.0],
            [0.0, 0.01, 0.0, 0.02],
            [0.02, 0.0, 0.1, 0.0],
            [0.0, 0.02, 0.0, 0.1],
        ])
        self.R_base = np.eye(2) * 0.5
        self.dt = 1.0
        self.F = np.array([
            [1, 0, self.dt, 0],
            [0, 1, 0, self.dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ])
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0],
        ])
        self._initialized = False
        self.confidence = 0.0
        self._no_observation_steps = 0
        self.I = np.eye(4)

    def update(self, visible_objects, body_direction, head_angle):
        self._predict()

        flag_obs = [(o, d, a) for o, d, a in visible_objects if o in FLAGS]
        if not flag_obs:
            self._no_observation_steps += 1
            self.confidence *= 0.95
            if self._no_observation_steps > 30:
                self._initialized = False
            return False

        self._no_observation_steps = 0
        measurements = []
        weights = []

        for i in range(len(flag_obs)):
            name_i, dist_i, ang_i = flag_obs[i]
            fx_i, fy_i = FLAGS.get(name_i, (0, 0))
            for j in range(i + 1, len(flag_obs)):
                name_j, dist_j, ang_j = flag_obs[j]
                fx_j, fy_j = FLAGS.get(name_j, (0, 0))
                result = self._triangulate(
                    (fx_i, fy_i), dist_i, ang_i,
                    (fx_j, fy_j), dist_j, ang_j,
                    body_direction, head_angle,
                )
                if result is not None:
                    cx, cy, err = result
                    weight = 1.0 / (err + 0.1)
                    measurements.append((cx, cy, err))
                    weights.append(weight)

        if not measurements:
            if self._initialized:
                self.confidence *= 0.98
            return False

        weights = np.array(weights)
        weights /= weights.sum()

        z_x = sum(m[0] * w for m, w in zip(measurements, weights))
        z_y = sum(m[1] * w for m, w in zip(measurements, weights))
        min_err = min(m[2] for m in measurements)

        if min_err > 25.0:
            if self._initialized:
                self.confidence *= 0.95
            return False

        R_adaptive = self.R_base * (1.0 + min_err)
        z = np.array([z_x, z_y])
        self._update(z, R_adaptive)

        if not self._initialized:
            self._initialized = True
            self.confidence = 0.5
        else:
            self.confidence = min(1.0, self.confidence + 0.02)

        logger.debug(f"Localizer: ({self.x[0]:.1f}, {self.x[1]:.1f}) err={min_err:.2f} conf={self.confidence:.2f}")
        return True

    def _predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q

    def _update(self, z, R):
        y = z - self.H @ self.x
        S = self.H @ self.P @ self.H.T + R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (self.I - K @ self.H) @ self.P

    def _triangulate(self, pos_a, dist_a, ang_a, pos_b, dist_b, ang_b, body, neck):
        body_rad = math.radians(body)
        neck_rad = math.radians(neck)
        total_angle = body_rad + neck_rad

        abs_angle_a = total_angle + math.radians(ang_a)
        abs_angle_b = total_angle + math.radians(ang_b)

        x1, y1 = pos_a
        x2, y2 = pos_b

        cos_a = math.cos(abs_angle_a)
        sin_a = math.sin(abs_angle_a)
        cos_b = math.cos(abs_angle_b)
        sin_b = math.sin(abs_angle_b)

        ax = x1 - dist_a * cos_a
        ay = y1 - dist_a * sin_a
        bx = x2 - dist_b * cos_b
        by = y2 - dist_b * sin_b

        cx = (ax + bx) / 2.0
        cy = (ay + by) / 2.0
        err = math.hypot(ax - bx, ay - by)
        return (cx, cy, err)

    def get_position(self):
        if not self._initialized:
            return (None, None)
        return (float(self.x[0]), float(self.x[1]))

    def get_velocity(self):
        if not self._initialized:
            return (0.0, 0.0)
        return (float(self.x[2]), float(self.x[3]))

    def get_confidence(self):
        return float(self.confidence)

    def reset(self):
        self.x.fill(0.0)
        self.P = np.eye(4) * 50.0
        self.P[2:, 2:] *= 5.0
        self._initialized = False
        self.confidence = 0.0
        self._no_observation_steps = 0
