"""
Percepción — mantiene el estado del mundo a partir de los
mensajes parseados del servidor.
"""
from dataclasses import dataclass, field


@dataclass
class WorldState:
    time: int = 0
    play_mode: str = "before_kick_off"
    side: str = "l"
    unum: int = 0

    # Stamina
    stamina: float = 8000.0
    effort: float = 1.0
    speed: float = 0.0
    head_angle: float = 0.0

    # Objetos visibles en el último ciclo
    visible_objects: list = field(default_factory=list)

    # Posición estimada del balón (None si no está visible)
    ball_distance: float | None = None
    ball_angle: float | None = None

    # Posición estimada propia (None si no hay flags visibles)
    self_x: float | None = None
    self_y: float | None = None


class Perception:
    """Actualiza el WorldState con cada mensaje del servidor."""

    def __init__(self):
        self.state = WorldState()

    def update(self, parsed: dict):
        msg_type = parsed.get("type")
        data = parsed.get("data", {})

        if msg_type == "init":
            self.state.side      = data.get("side", self.state.side)
            self.state.unum      = data.get("unum", self.state.unum)
            self.state.play_mode = data.get("play_mode", self.state.play_mode)

        elif msg_type == "see":
            self.state.time = data.get("time", self.state.time)
            objects = data.get("objects", [])
            self.state.visible_objects = objects
            self._update_ball(objects)

        elif msg_type == "sense_body":
            self.state.time       = data.get("time", self.state.time)
            self.state.stamina    = data.get("stamina", self.state.stamina)
            self.state.effort     = data.get("effort", self.state.effort)
            self.state.speed      = data.get("speed", self.state.speed)
            self.state.head_angle = data.get("head_angle", self.state.head_angle)

        elif msg_type == "hear":
            # Actualizar play_mode si viene del referee
            sender  = data.get("sender", "")
            message = data.get("message", "")
            if sender == "referee":
                self.state.play_mode = message.strip("()")

    def _update_ball(self, objects: list):
        self.state.ball_distance = None
        self.state.ball_angle    = None
        for obj in objects:
            if obj.get("name") == "b":
                self.state.ball_distance = obj.get("distance")
                self.state.ball_angle    = obj.get("angle")
                break

    def can_see_ball(self) -> bool:
        return self.state.ball_distance is not None

    def is_ball_kickable(self, kickable_margin: float = 1.0) -> bool:
        return (
            self.state.ball_distance is not None
            and self.state.ball_distance <= kickable_margin
        )