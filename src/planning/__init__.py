import math

from util.field_constants import BOUNDARY_X_MAX, BOUNDARY_X_MIN, BOUNDARY_Y_MAX, BOUNDARY_Y_MIN

class AStarPlanner:
    def __init__(self, cell_size=2.0):
        self.cell_size = cell_size
        self.cols = int((BOUNDARY_X_MAX - BOUNDARY_X_MIN) / cell_size) + 1
        self.rows = int((BOUNDARY_Y_MAX - BOUNDARY_Y_MIN) / cell_size) + 1

    def _world_to_grid(self, x, y):
        c = int((x - BOUNDARY_X_MIN) / self.cell_size)
        r = int((y - BOUNDARY_Y_MIN) / self.cell_size)
        return (max(0, min(self.cols - 1, c)), max(0, min(self.rows - 1, r)))

    def _grid_to_world(self, c, r):
        x = BOUNDARY_X_MIN + c * self.cell_size + self.cell_size / 2
        y = BOUNDARY_Y_MIN + r * self.cell_size + self.cell_size / 2
        return (x, y)

    def plan(self, start, goal, obstacles=None, zone_limits=None):
        start_c = self._world_to_grid(start[0], start[1])
        goal_c = self._world_to_grid(goal[0], goal[1])

        open_set = {start_c}
        came_from = {}
        g_score = {start_c: 0.0}
        f_score = {start_c: self._heuristic(start_c, goal_c)}

        while open_set:
            current = min(open_set, key=lambda p: f_score.get(p, float("inf")))
            if current == goal_c:
                return self._reconstruct_path(came_from, current)

            open_set.remove(current)
            for neighbor in self._get_neighbors(current):
                if obstacles and neighbor in obstacles:
                    continue
                if zone_limits and not self._in_zone(self._grid_to_world(*neighbor), zone_limits):
                    continue

                tentative_g = g_score[current] + self._cost(current, neighbor, obstacles)
                if tentative_g < g_score.get(neighbor, float("inf")):
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal_c)
                    if neighbor not in open_set:
                        open_set.add(neighbor)

        return [start]

    def _heuristic(self, a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def _cost(self, current, neighbor, obstacles=None):
        base = 1.0
        if obstacles:
            cx, cy = self._grid_to_world(*neighbor)
            for obs in obstacles:
                d = math.hypot(cx - obs[0], cy - obs[1])
                if d < 3.0:
                    base += 0.5 * (3.0 - d)
        return base

    def _get_neighbors(self, pos):
        c, r = pos
        neighbors = []
        for dc, dr in [(0, 1), (0, -1), (1, 0), (-1, 0),
                       (1, 1), (-1, 1), (1, -1), (-1, -1)]:
            nc, nr = c + dc, r + dr
            if 0 <= nc < self.cols and 0 <= nr < self.rows:
                neighbors.append((nc, nr))
        return neighbors

    def _in_zone(self, pos, zone):
        x, y = pos
        xmin, xmax, ymin, ymax = zone
        return xmin <= x <= xmax and ymin <= y <= ymax

    def _reconstruct_path(self, came_from, current):
        path = [self._grid_to_world(*current)]
        while current in came_from:
            current = came_from[current]
            path.append(self._grid_to_world(*current))
        path.reverse()
        return path


class FlowFieldPlanner:
    def __init__(self, cell_size=3.0):
        self.cell_size = cell_size
        self.cols = int(105 / cell_size) + 1
        self.rows = int(68 / cell_size) + 1
        self.field = [[(0.0, 0.0) for _ in range(self.cols)] for _ in range(self.rows)]

    def calculate(self, target_pos, allies=None, enemies=None):
        goal_c = self._world_to_grid(target_pos[0], target_pos[1])

        for r in range(self.rows):
            for c in range(self.cols):
                gx, gy = self._grid_to_world(c, r)
                dx = goal_c[0] - c
                dy = goal_c[1] - r
                dist = math.hypot(dx, dy)
                if dist > 0:
                    dir_x = dx / dist
                    dir_y = dy / dist
                else:
                    dir_x, dir_y = 0.0, 0.0

                avoidance = (0.0, 0.0)
                if enemies:
                    for ex, ey, _ in enemies:
                        ed = math.hypot(gx - ex, gy - ey)
                        if ed < 5.0 and ed > 0.1:
                            avoid_strength = (5.0 - ed) / 5.0
                            avoidance = (
                                avoidance[0] + avoid_strength * (gx - ex) / ed,
                                avoidance[1] + avoid_strength * (gy - ey) / ed,
                            )

                if allies:
                    for ax, ay, _ in allies:
                        ad = math.hypot(gx - ax, gy - ay)
                        if ad < 3.0 and ad > 0.1:
                            avoid_strength = (3.0 - ad) / 3.0 * 0.5
                            avoidance = (
                                avoidance[0] + avoid_strength * (gx - ax) / ad,
                                avoidance[1] + avoid_strength * (gy - ay) / ad,
                            )

                final_x = dir_x + avoidance[0]
                final_y = dir_y + avoidance[1]
                norm = math.hypot(final_x, final_y)
                if norm > 0:
                    self.field[r][c] = (final_x / norm, final_y / norm)

    def get_direction(self, pos):
        c, r = self._world_to_grid(pos[0], pos[1])
        c = max(0, min(self.cols - 1, c))
        r = max(0, min(self.rows - 1, r))
        return self.field[r][c]

    def _world_to_grid(self, x, y):
        c = int((x + 52.5) / self.cell_size)
        r = int((y + 34.0) / self.cell_size)
        return (max(0, min(self.cols - 1, c)), max(0, min(self.rows - 1, r)))

    def _grid_to_world(self, c, r):
        x = -52.5 + c * self.cell_size + self.cell_size / 2
        y = -34.0 + r * self.cell_size + self.cell_size / 2
        return (x, y)
