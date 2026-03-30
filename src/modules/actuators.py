"""
Actuadores — genera los comandos que se envían al servidor.
Todos los métodos retornan el string del comando para que
el cliente lo envíe. El agente decide cuándo llamarlos.
"""


def move(x: float, y: float) -> str:
    """Teletransporta al jugador (solo antes de kick_off)."""
    return f"(move {x} {y})"


def turn(moment: float) -> str:
    """Gira el cuerpo. moment en grados [-180, 180]."""
    return f"(turn {moment})"


def turn_neck(angle: float) -> str:
    """Gira el cuello independientemente del cuerpo."""
    return f"(turn_neck {angle})"


def dash(power: float, direction: float = 0.0) -> str:
    """Mueve al jugador. power en [-100, 100], direction en [-180, 180]."""
    return f"(dash {power} {direction})"


def kick(power: float, direction: float) -> str:
    """Patear el balón. power en [0, 100], direction en [-180, 180]."""
    return f"(kick {power} {direction})"


def catch(direction: float) -> str:
    """Solo para el portero. Atrapar el balón."""
    return f"(catch {direction})"


def say(message: str) -> str:
    """Comunicarse con compañeros de equipo."""
    return f"(say {message})"


def change_view(width: str, quality: str) -> str:
    """
    Cambiar el ángulo de visión.
    width:   narrow | normal | wide
    quality: low | high
    """
    return f"(change_view {width} {quality})"


def attentionto(team: str, unum: int) -> str:
    """Prestar atención a un jugador específico."""
    return f"(attentionto {team} {unum})"


def tackle(power: float, foul: bool = False) -> str:
    """Realizar un tackle."""
    foul_str = "true" if foul else "false"
    return f"(tackle {power} {foul_str})"