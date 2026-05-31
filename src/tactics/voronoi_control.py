import math
from util.field_constants import BOUNDARY_X_MAX, BOUNDARY_X_MIN, BOUNDARY_Y_MAX, BOUNDARY_Y_MIN

class VoronoiController:
    def __init__(self):
        self.cells = {}

    def calculate(self, allies, enemies):
        all_points = allies + enemies
        if not all_points:
            return {}

        self.cells = {}
        for agent in allies:
            unum = agent["unum"]
            self.cells[unum] = {
                "center": (agent["x"], agent["y"]),
                "area": 0.0,
                "neighbors": [],
                "control_value": 0.0,
            }

        for agent in allies:
            unum = agent["unum"]
            ax, ay = agent["x"], agent["y"]
            area = 0.0
            neighbors = []

            for other in all_points:
                if other["unum"] == unum:
                    continue
                ox, oy = other["x"], other["y"]
                d = math.hypot(ax - ox, ay - oy)
                if d < 0.1:
                    continue
                bisector_dist = d / 2.0
                if bisector_dist < 30.0:
                    area += bisector_dist * 0.5
                    neighbors.append(other["unum"])

            self.cells[unum]["area"] = area
            self.cells[unum]["neighbors"] = neighbors

            nearest_enemy = None
            min_enemy_dist = float("inf")
            for enemy in enemies:
                d = math.hypot(ax - enemy["x"], ay - enemy["y"])
                if d < min_enemy_dist:
                    min_enemy_dist = d
                    nearest_enemy = enemy["unum"]
            self.cells[unum]["control_value"] = min(1.0, area / 50.0) - max(0.0, 1.0 - min_enemy_dist / 15.0)

        return self.cells

    def get_largest_gap(self, allies, enemies, side):
        my_x = [a["x"] for a in allies]
        my_y = [a["y"] for a in allies]

        intervals = []
        sorted_allies = sorted(allies, key=lambda a: a["x"])
        for i in range(len(sorted_allies) - 1):
            gap_x = abs(sorted_allies[i + 1]["x"] - sorted_allies[i]["x"])
            gap_y = abs(sorted_allies[i + 1]["y"] - sorted_allies[i]["y"])
            mid_x = (sorted_allies[i]["x"] + sorted_allies[i + 1]["x"]) / 2.0
            mid_y = (sorted_allies[i]["y"] + sorted_allies[i + 1]["y"]) / 2.0
            intervals.append({
                "center": (mid_x, mid_y),
                "gap": math.hypot(gap_x, gap_y),
                "idx": i,
            })

        if not intervals:
            return None
        intervals.sort(key=lambda x: x["gap"], reverse=True)
        return intervals[0]

    def find_best_support_position(self, ball_pos, allies, enemies):
        if not allies:
            return ball_pos
        dists = [math.hypot(a["x"] - ball_pos[0], a["y"] - ball_pos[1]) for a in allies]
        nearest = min(dists) if dists else 0

        bx, by = ball_pos
        candidates = [
            (bx + 8, by + 6),
            (bx + 8, by - 6),
            (bx + 8, by + 0),
            (bx + 5, by + 10),
            (bx + 5, by - 10),
            (bx + 12, by + 0),
        ]
        for side_mult in [-1, 1]:
            candidates.append((bx + 8 * side_mult, by + 4 * side_mult))

        best = None
        best_score = -float("inf")
        for cx, cy in candidates:
            if abs(cx) > BOUNDARY_X_MAX - 1 or abs(cy) > BOUNDARY_Y_MAX - 1:
                continue
            enemy_dist = min(
                (math.hypot(cx - e["x"], cy - e["y"]) for e in enemies),
                default=float("inf")
            )
            ally_dist = min(
                (math.hypot(cx - a["x"], cy - a["y"]) for a in allies if math.hypot(cx - a["x"], cy - a["y"]) > 2.0),
                default=float("inf")
            )
            score = enemy_dist - ally_dist * 0.5
            if score > best_score:
                best_score = score
                best = (cx, cy)

        return best if best else ball_pos


class InfluenceMap:
    def __init__(self, width=105, height=68, resolution=5):
        self.resolution = resolution
        self.cols = width // resolution + 1
        self.rows = height // resolution + 1
        self.grid = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]

    def calculate(self, allies, enemies, ball_pos=None):
        self.grid = [[0.0 for _ in range(self.cols)] for _ in range(self.rows)]

        for r in range(self.rows):
            for c in range(self.cols):
                gx = -52.5 + c * self.resolution
                gy = -34.0 + r * self.resolution
                value = 0.0

                for ally in allies:
                    d = math.hypot(gx - ally["x"], gy - ally["y"])
                    if d > 0.1:
                        strength = {"goalkeeper": 3.0, "defender": 2.0,
                                   "midfielder": 1.5, "forward": 1.0}.get(ally.get("role", "midfielder"), 1.0)
                        value += strength / (1.0 + d * 0.1)

                for enemy in enemies:
                    d = math.hypot(gx - enemy["x"], gy - enemy["y"])
                    if d > 0.1:
                        value -= 2.0 / (1.0 + d * 0.1)

                if ball_pos:
                    d = math.hypot(gx - ball_pos[0], gy - ball_pos[1])
                    if d > 0.1:
                        value += 1.0 / (1.0 + d * 0.05)

                self.grid[r][c] = value

    def get_control_ratio(self):
        positive = sum(1 for r in self.grid for v in r if v > 0)
        total = sum(len(r) for r in self.grid)
        return positive / max(1, total)

    def get_safest_direction(self, from_pos):
        best_dir = 0.0
        best_value = -float("inf")
        for angle_deg in range(0, 360, 15):
            rad = math.radians(angle_deg)
            tx = from_pos[0] + 10 * math.cos(rad)
            ty = from_pos[1] + 10 * math.sin(rad)
            col = int((tx + 52.5) / self.resolution)
            row = int((ty + 34.0) / self.resolution)
            if 0 <= col < self.cols and 0 <= row < self.rows:
                val = self.grid[row][col]
                if val > best_value:
                    best_value = val
                    best_dir = angle_deg
        return best_dir
