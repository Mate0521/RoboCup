"""
Percepción — estado completo del mundo.
Cambios v3:
  - WorldState agrega score_l, score_r, players_l, players_r
  - _process_hear detecta goles y expulsiones del referee
  - Exporta score_diff como propiedad calculada
"""
from dataclasses import dataclass, field
from enum import Enum
import re


class PlayMode(Enum):
    BEFORE_KICK_OFF      = "before_kick_off"
    KICK_OFF_L           = "kick_off_l"
    KICK_OFF_R           = "kick_off_r"
    PLAY_ON              = "play_on"
    KICK_IN_L            = "kick_in_l"
    KICK_IN_R            = "kick_in_r"
    FREE_KICK_L          = "free_kick_l"
    FREE_KICK_R          = "free_kick_r"
    CORNER_KICK_L        = "corner_kick_l"
    CORNER_KICK_R        = "corner_kick_r"
    GOAL_KICK_L          = "goal_kick_l"
    GOAL_KICK_R          = "goal_kick_r"
    OFFSIDE_L            = "offside_l"
    OFFSIDE_R            = "offside_r"
    HALF_TIME            = "half_time"
    TIME_OVER            = "time_over"
    GOAL_L               = "goal_l"
    GOAL_R               = "goal_r"
    FOUL_CHARGE_L        = "foul_charge_l"
    FOUL_CHARGE_R        = "foul_charge_r"
    BACK_PASS_L          = "back_pass_l"
    BACK_PASS_R          = "back_pass_r"
    FREE_KICK_FAULT_L    = "free_kick_fault_l"
    FREE_KICK_FAULT_R    = "free_kick_fault_r"
    CATCH_FAULT_L        = "catch_fault_l"
    CATCH_FAULT_R        = "catch_fault_r"
    INDIRECT_FREE_KICK_L = "indirect_free_kick_l"
    INDIRECT_FREE_KICK_R = "indirect_free_kick_r"
    PENALTY_SETUP_L      = "penalty_setup_l"
    PENALTY_SETUP_R      = "penalty_setup_r"
    PENALTY_READY_L      = "penalty_ready_l"
    PENALTY_READY_R      = "penalty_ready_r"
    PENALTY_TAKEN_L      = "penalty_taken_l"
    PENALTY_TAKEN_R      = "penalty_taken_r"
    UNKNOWN              = "unknown"

    @classmethod
    def from_str(cls, s: str):
        for m in cls:
            if m.value == s:
                return m
        return cls.UNKNOWN


@dataclass
class WorldState:
    # Identidad
    time: int = 0
    side: str = "l"
    unum: int = 0
    play_mode: PlayMode = PlayMode.BEFORE_KICK_OFF

    # Cuerpo
    stamina: float       = 8000.0
    effort: float        = 1.0
    speed: float         = 0.0
    speed_dir: float     = 0.0
    head_angle: float    = 0.0
    body_direction: float = 0.0

    # Visión
    visible_objects: list = field(default_factory=list)

    # Balón
    ball_distance: float | None   = None
    ball_angle: float | None      = None
    ball_dist_change: float       = 0.0
    ball_dir_change: float        = 0.0

    # Jugadores visibles
    teammates: list = field(default_factory=list)
    opponents: list = field(default_factory=list)

    # Posición estimada propia
    self_x: float | None = None
    self_y: float | None = None

    # ── NUEVO: marcador y jugadores activos ──────────────────────────────────
    score_l: int    = 0     # goles equipo izquierdo
    score_r: int    = 0     # goles equipo derecho
    players_l: int  = 11   # jugadores activos izquierdo
    players_r: int  = 11   # jugadores activos derecho


class Perception:
    def __init__(self, team_name: str = ""):
        self.state = WorldState()
        self._team_name_val = team_name

    def update(self, parsed: dict):
        t = parsed.get("type")
        d = parsed.get("data", {})

        if t == "init":
            self.state.side      = d.get("side", self.state.side)
            self.state.unum      = d.get("unum", self.state.unum)
            self.state.play_mode = PlayMode.from_str(
                d.get("play_mode", "before_kick_off")
            )

        elif t == "see":
            self.state.time = d.get("time", self.state.time)
            self._process_see(d.get("objects", []))

        elif t == "sense_body":
            self.state.time          = d.get("time", self.state.time)
            self.state.stamina       = d.get("stamina", self.state.stamina)
            self.state.effort        = d.get("effort", self.state.effort)
            self.state.speed         = d.get("speed", self.state.speed)
            self.state.speed_dir     = d.get("speed_angle", self.state.speed_dir)
            self.state.head_angle    = d.get("head_angle", self.state.head_angle)
            if "body_dir" in d:
                self.state.body_direction = float(d["body_dir"])

        elif t == "hear":
            self._process_hear(d)

    def _process_see(self, objects: list):
        self.state.visible_objects = objects
        self.state.ball_distance   = None
        self.state.ball_angle      = None
        self.state.teammates       = []
        self.state.opponents       = []

        for obj in objects:
            name = obj.get("name", "")
            dist = obj.get("distance", 0.0)
            ang  = obj.get("angle", 0.0)

            if name == "b":
                self.state.ball_distance    = dist
                self.state.ball_angle       = ang
                self.state.ball_dist_change = obj.get("dist_change", 0.0)
                self.state.ball_dir_change  = obj.get("dir_change", 0.0)

            elif name.startswith("p"):
                parts      = name.split()
                is_teammate = (
                    len(parts) > 1 and
                    parts[1].strip('"') == self._team_name_val
                )
                entry = {"distance": dist, "angle": ang, "name": name}
                if is_teammate:
                    self.state.teammates.append(entry)
                else:
                    self.state.opponents.append(entry)

    def _process_hear(self, d: dict):
        sender  = d.get("sender", "")
        message = d.get("message", "").strip()

        if sender != "referee":
            return

        # Play mode
        pm = PlayMode.from_str(message)
        if pm != PlayMode.UNKNOWN:
            self.state.play_mode = pm

        # Gol — actualizar marcador
        if message == "goal_l":
            self.state.score_l += 1
        elif message == "goal_r":
            self.state.score_r += 1

        # Expulsión: "red_card_l" / "red_card_r"
        if "red_card_l" in message:
            self.state.players_l = max(7, self.state.players_l - 1)
        elif "red_card_r" in message:
            self.state.players_r = max(7, self.state.players_r - 1)

        # Score explícito: algunos servidores envían "score N N"
        m = re.match(r"score\s+(\d+)\s+(\d+)", message)
        if m:
            self.state.score_l = int(m.group(1))
            self.state.score_r = int(m.group(2))

    # ── Propiedades calculadas ────────────────────────────────────────────────

    def score_diff(self) -> float:
        """Goles propios menos goles rivales."""
        if self.state.side == "l":
            return float(self.state.score_l - self.state.score_r)
        return float(self.state.score_r - self.state.score_l)

    def active_players_my_team(self) -> int:
        return self.state.players_l if self.state.side == "l" else self.state.players_r

    def notify_turn(self, moment: float):
        self.state.body_direction = (self.state.body_direction + moment) % 360
        if self.state.body_direction > 180:
            self.state.body_direction -= 360

    def can_see_ball(self) -> bool:
        return self.state.ball_distance is not None

    def is_ball_kickable(self, margin: float = 0.7) -> bool:
        return self.can_see_ball() and (self.state.ball_distance or 999) <= margin

    def is_my_team_kickoff(self) -> bool:
        pm   = self.state.play_mode
        side = self.state.side
        my   = {
            "l": {PlayMode.KICK_OFF_L, PlayMode.FREE_KICK_L, PlayMode.CORNER_KICK_L,
                  PlayMode.KICK_IN_L, PlayMode.GOAL_KICK_L, PlayMode.INDIRECT_FREE_KICK_L,
                  PlayMode.PENALTY_SETUP_L, PlayMode.PENALTY_READY_L, PlayMode.PENALTY_TAKEN_L},
            "r": {PlayMode.KICK_OFF_R, PlayMode.FREE_KICK_R, PlayMode.CORNER_KICK_R,
                  PlayMode.KICK_IN_R, PlayMode.GOAL_KICK_R, PlayMode.INDIRECT_FREE_KICK_R,
                  PlayMode.PENALTY_SETUP_R, PlayMode.PENALTY_READY_R, PlayMode.PENALTY_TAKEN_R},
        }
        return pm in my.get(side, set())

    def ball_is_moving_toward_goal(self) -> bool:
        return (
            self.can_see_ball()
            and self.state.ball_dist_change < -0.5
            and abs(self.state.ball_angle or 180) < 20
        )