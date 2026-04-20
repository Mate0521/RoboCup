"""
Actuadores — genera los comandos que se envían al servidor.
Todos los valores se redondean a 2 decimales para mantener
los mensajes limpios y dentro del buffer UDP del servidor.
"""


def _r(v: float) -> str:
    """Redondea a 2 decimales y elimina ceros innecesarios."""
    return f"{round(v, 2):g}"


def move(x: float, y: float) -> str:
    """Teletransporta al jugador (solo antes de kick_off)."""
    return f"(move {_r(x)} {_r(y)})"


def turn(moment: float) -> str:
    """Gira el cuerpo. moment en grados [-180, 180]."""
    return f"(turn {_r(moment)})"


def turn_neck(angle: float) -> str:
    """Gira el cuello independientemente del cuerpo."""
    return f"(turn_neck {_r(angle)})"


def dash(power: float, direction: float = 0.0) -> str:
    """Mueve al jugador. power en [-100, 100], direction en [-180, 180]."""
    if direction == 0.0:
        return f"(dash {_r(power)})"
    return f"(dash {_r(power)} {_r(direction)})"


def kick(power: float, direction: float) -> str:
    """Patear el balón. power en [0, 100], direction en [-180, 180]."""
    return f"(kick {_r(power)} {_r(direction)})"


def catch(direction: float) -> str:
    """Solo para el portero. Atrapar el balón."""
    return f"(catch {_r(direction)})"


def say(message: str) -> str:
    """Comunicarse con compañeros de equipo."""
    return f"(say {message})"


def change_view(width: str, quality: str) -> str:
    """
    Cambiar el ángulo de visión.
    width:   narrow | normal | wide
    quality: low | high
    Con wide+high se reciben dist_change y dir_change del balón.
    """
    return f"(change_view {width} {quality})"


def attentionto(team: str, unum: int) -> str:
    """Prestar atención a un jugador específico."""
    return f"(attentionto {team} {unum})"


def tackle(power: float, foul: bool = False) -> str:
    """Realizar un tackle."""
    foul_str = "true" if foul else "false"
    return f"(tackle {_r(power)} {foul_str})"