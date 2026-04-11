"""
Asignación de roles — formación 4-3-3.
Cada rol tiene posición táctica dinámica según el play mode.
"""

# Formación 4-3-3
ROLES = {
    1:  "goalkeeper",
    2:  "defender",
    3:  "defender",
    4:  "defender",
    5:  "defender",
    6:  "midfielder",
    7:  "midfielder",
    8:  "midfielder",
    9:  "forward",
    10: "forward",
    11: "forward",
}

# Posiciones base para side izquierdo (x, y)
# x negativo = mitad propia, x positivo = mitad rival
BASE_POSITIONS = {
    "goalkeeper": [(-48, 0)],
    "defender":   [(-30, -15), (-33, -5), (-33, 5), (-30, 15)],
    "midfielder": [(-10, -12), (-5, 0), (-10, 12)],
    "forward":    [(20, -10), (25, 0), (20, 10)],
}

# Posiciones defensivas (cuando el rival tiene el balón)
DEFENSIVE_POSITIONS = {
    "goalkeeper": [(-48, 0)],
    "defender":   [(-38, -12), (-40, -4), (-40, 4), (-38, 12)],
    "midfielder": [(-25, -10), (-22, 0), (-25, 10)],
    "forward":    [(-5, -8), (0, 0), (-5, 8)],
}

# Posiciones ofensivas (cuando mi equipo tiene el balón)
OFFENSIVE_POSITIONS = {
    "goalkeeper": [(-48, 0)],
    "defender":   [(-20, -15), (-22, -5), (-22, 5), (-20, 15)],
    "midfielder": [(5, -12), (10, 0), (5, 12)],
    "forward":    [(35, -10), (38, 0), (35, 10)],
}

# Posiciones para tiros libres/corners (mi equipo ejecuta)
SET_PIECE_ATTACK = {
    "goalkeeper": [(-48, 0)],
    "defender":   [(-15, -10), (-10, -5), (-10, 5), (-15, 10)],
    "midfielder": [(10, -8), (15, 0), (10, 8)],
    "forward":    [(38, -8), (40, 0), (38, 8)],
}

# Posiciones para tiros libres/corners (el rival ejecuta)
SET_PIECE_DEFENSE = {
    "goalkeeper": [(-48, 0)],
    "defender":   [(-42, -10), (-43, -3), (-43, 3), (-42, 10)],
    "midfielder": [(-30, -8), (-28, 0), (-30, 8)],
    "forward":    [(-10, -5), (-5, 0), (-10, 5)],
}


def get_role(unum: int) -> str:
    return ROLES.get(unum, "midfielder")


def _get_role_index(unum: int) -> int:
    role = get_role(unum)
    same = [u for u, r in ROLES.items() if r == role]
    return same.index(unum) if unum in same else 0


def get_tactical_position(unum: int, side: str, situation: str = "base") -> tuple[float, float]:
    """
    Retorna la posición táctica según la situación:
      base       — posición estándar
      defensive  — cuando el rival tiene el balón
      offensive  — cuando mi equipo tiene el balón
      set_attack — tiro libre/corner a favor
      set_defense— tiro libre/corner en contra
    """
    role = get_role(unum)
    idx  = _get_role_index(unum)

    tables = {
        "base":       BASE_POSITIONS,
        "defensive":  DEFENSIVE_POSITIONS,
        "offensive":  OFFENSIVE_POSITIONS,
        "set_attack": SET_PIECE_ATTACK,
        "set_defense":SET_PIECE_DEFENSE,
    }
    table = tables.get(situation, BASE_POSITIONS)
    positions = table.get(role, [(0, 0)])
    x, y = positions[idx % len(positions)]

    # Espejo para side derecho
    if side == "r":
        x = -x

    return (float(x), float(y))


def get_start_position(unum: int, side: str) -> tuple[float, float]:
    return get_tactical_position(unum, side, "base")