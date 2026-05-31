import math
from util.field_constants import BOUNDARY_X_MAX, BOUNDARY_X_MIN, BOUNDARY_Y_MAX, BOUNDARY_Y_MIN

BALL_DECAY = 0.94
BALL_SPEED_MAX = 3.0

class BallPredictor:
    def predict(self, pos, vel, n_cycles=10):
        x, y = pos
        vx, vy = vel
        trajectory = [(x, y)]
        for _ in range(n_cycles):
            vx *= BALL_DECAY
            vy *= BALL_DECAY
            x += vx
            y += vy
            x = max(BOUNDARY_X_MIN, min(BOUNDARY_X_MAX, x))
            y = max(BOUNDARY_Y_MIN, min(BOUNDARY_Y_MAX, y))
            if abs(vx) < 0.001 and abs(vy) < 0.001:
                break
            trajectory.append((x, y))
        return trajectory

    def predict_position_at(self, pos, vel, cycle):
        traj = self.predict(pos, vel, cycle)
        if cycle < len(traj):
            return traj[cycle]
        return traj[-1]

    def time_to_reach(self, from_pos, target_pos, speed=1.2):
        dist = math.hypot(target_pos[0] - from_pos[0], target_pos[1] - from_pos[1])
        return dist / speed

    def will_enter_goal(self, pos, vel, side):
        gx = 52.5 if side == "r" else -52.5
        traj = self.predict(pos, vel, 30)
        for px, py in traj:
            if abs(px - gx) < 2.0 and abs(py) < 7.01:
                step = traj.index((px, py))
                return (True, step, (px, py))
        return (False, None, None)

    def interceptable_by(self, ball_pos, ball_vel, agent_pos, agent_speed=1.0, max_cycles=30):
        for step in range(1, max_cycles + 1):
            bp = self.predict_position_at(ball_pos, ball_vel, step)
            ad = math.hypot(bp[0] - agent_pos[0], bp[1] - agent_pos[1])
            if ad / agent_speed <= step * 0.9:
                return (True, step, bp)
        return (False, None, None)
