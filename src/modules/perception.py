"""
Percepción — estado completo del mundo.
Incluye todos los play modes del rcssserver.
"""
from dataclasses import dataclass, field
from enum import Enum


class PlayMode(Enum):
    BEFORE_KICK_OFF   = "before_kick_off"
    KICK_OFF_L        = "kick_off_l"
    KICK_OFF_R        = "kick_off_r"
    PLAY_ON           = "play_on"
    KICK_IN_L         = "kick_in_l"
    KICK_IN_R         = "kick_in_r"
    FREE_KICK_L       = "free_kick_l"
    FREE_KICK_R       = "free_kick_r"
    CORNER_KICK_L     = "corner_kick_l"
    CORNER_KICK_R     = "corner_kick_r"
    GOAL_KICK_L       = "goal_kick_l"
    GOAL_KICK_R       = "goal_kick_r"
    OFFSIDE_L         = "offside_l"
    OFFSIDE_R         = "offside_r"
    HALF_TIME         = "half_time"
    TIME_OVER         = "time_over"
    GOAL_L            = "goal_l"
    GOAL_R            = "goal_r"
    FOUL_CHARGE_L     = "foul_charge_l"
    FOUL_CHARGE_R     = "foul_charge_r"
    BACK_PASS_L       = "back_pass_l"
    BACK_PASS_R       = "back_pass_r"
    FREE_KICK_FAULT_L = "free_kick_fault_l"
    FREE_KICK_FAULT_R = "free_kick_fault_r"
    CATCH_FAULT_L     = "catch_fault_l"
    CATCH_FAULT_R     = "catch_fault_r"
    INDIRECT_FREE_KICK_L = "indirect_free_kick_l"
    INDIRECT_FREE_KICK_R = "indirect_free_kick_r"
    PENALTY_SETUP_L   = "penalty_setup_l"
    PENALTY_SETUP_R   = "penalty_setup_r"
    PENALTY_READY_L   = "penalty_ready_l"
    PENALTY_READY_R   = "penalty_ready_r"
    PENALTY_TAKEN_L   = "penalty_taken_l"
    PENALTY_TAKEN_R   = "penalty_taken_r"
    UNKNOWN           = "unknown"

    @classmethod
    def from_str(cls, s: str):
        for member in cls:
            if member.value == s:
                return member
        return cls.UNKNOWN


@dataclass
class VisibleObject:
    name: str
    distance: float = 0.0
    angle: float = 0.0
    dist_change: float = 0.0
    dir_change: float = 0.0


@dataclass
class WorldState:
    # Identidad
    time: int = 0
    side: str = "l"
    unum: int = 0
    play_mode: PlayMode = PlayMode.BEFORE_KICK_OFF

    # Cuerpo
    stamina: float = 8000.0
    effort: float = 1.0
    speed: float = 0.0
    speed_dir: float = 0.0
    head_angle: float = 0.0

    # Visión
    visible_objects: list = field(default_factory=list)

    # Balón
    ball_distance: float | None = None
    ball_angle: float | None = None
    ball_dist_change: float = 0.0
    ball_dir_change: float = 0.0

    # Compañeros y rivales visibles
    teammates: list = field(default_factory=list)
    opponents: list = field(default_factory=list)

    # Posición propia estimada (via flags)
    self_x: float | None = None
    self_y: float | None = None


class Perception:
    def __init__(self):
        self.state = WorldState()

    def update(self, parsed: dict):
        t = parsed.get("type")
        d = parsed.get("data", {})

        if t == "init":
            self.state.side      = d.get("side", self.state.side)
            self.state.unum      = d.get("unum", self.state.unum)
            pm_str               = d.get("play_mode", "before_kick_off")
            self.state.play_mode = PlayMode.from_str(pm_str)

        elif t == "see":
            self.state.time = d.get("time", self.state.time)
            self._process_see(d.get("objects", []))

        elif t == "sense_body":
            self.state.time       = d.get("time", self.state.time)
            self.state.stamina    = d.get("stamina", self.state.stamina)
            self.state.effort     = d.get("effort", self.state.effort)
            self.state.speed      = d.get("speed", self.state.speed)
            self.state.speed_dir  = d.get("speed_angle", self.state.speed_dir)
            self.state.head_angle = d.get("head_angle", self.state.head_angle)

        elif t == "hear":
            sender  = d.get("sender", "")
            message = d.get("message", "").strip("()")
            if sender == "referee":
                self.state.play_mode = PlayMode.from_str(message)

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
                self.state.ball_distance  = dist
                self.state.ball_angle     = ang
                self.state.ball_dist_change = obj.get("dist_change", 0.0)
                self.state.ball_dir_change  = obj.get("dir_change", 0.0)

            elif name.startswith("p"):
                parts = name.split()
                is_teammate = len(parts) > 1 and parts[1].strip('"') == self._team_name()
                entry = {"distance": dist, "angle": ang, "name": name}
                if is_teammate:
                    self.state.teammates.append(entry)
                else:
                    self.state.opponents.append(entry)

    def _team_name(self) -> str:
        return ""  # Se sobreescribe en DecisionMaker si se necesita

    # --- Helpers para la FSM ---

    def can_see_ball(self) -> bool:
        return self.state.ball_distance is not None

    def is_ball_kickable(self, margin: float = 0.7) -> bool:
        return self.can_see_ball() and self.state.ball_distance <= margin

    def is_my_team_kickoff(self) -> bool:
        pm = self.state.play_mode
        if self.state.side == "l":
            return pm in (PlayMode.KICK_OFF_L, PlayMode.FREE_KICK_L,
                          PlayMode.CORNER_KICK_L, PlayMode.KICK_IN_L,
                          PlayMode.GOAL_KICK_L, PlayMode.INDIRECT_FREE_KICK_L)
        else:
            return pm in (PlayMode.KICK_OFF_R, PlayMode.FREE_KICK_R,
                          PlayMode.CORNER_KICK_R, PlayMode.KICK_IN_R,
                          PlayMode.GOAL_KICK_R, PlayMode.INDIRECT_FREE_KICK_R)

    def is_dead_ball(self) -> bool:
        """Juego detenido — nadie debe moverse excepto el ejecutor."""
        return self.state.play_mode not in (
            PlayMode.PLAY_ON,
            PlayMode.BEFORE_KICK_OFF,
            PlayMode.HALF_TIME,
            PlayMode.TIME_OVER,
            PlayMode.UNKNOWN,
        ) and self.state.play_mode not in (
            PlayMode.KICK_OFF_L, PlayMode.KICK_OFF_R,
        )

    def ball_is_moving_toward_goal(self) -> bool:
        """El balón se acerca rápido (señal de peligro para el portero)."""
        return (
            self.can_see_ball()
            and self.state.ball_dist_change < -0.5
            and abs(self.state.ball_angle) < 20
        )