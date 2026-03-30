"""
Asignación de roles según el número de jugador (unum).
Fácil de extender con roles más complejos.
"""

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

# Posición inicial por rol (x, y) para side izquierdo
# Para side derecho se niegan las x
STARTING_POSITIONS = {
    "goalkeeper": (-48, 0),
    "defender":   (-30, 0),
    "midfielder": (-10, 0),
    "forward":    (10,  0),
}

# Offsets para distribuir jugadores del mismo rol
ROLE_OFFSETS = {
    "defender":   [(0, -15), (0, 0), (0, 15), (0, -8)],
    "midfielder": [(0, -10), (0, 0), (0, 10)],
    "forward":    [(0, -8),  (0, 8)],
}


def get_role(unum: int) -> str:
    return ROLES.get(unum, "field")


def get_start_position(unum: int, side: str) -> tuple[float, float]:
    """Retorna la posición de inicio para el jugador."""
    role = get_role(unum)
    base_x, base_y = STARTING_POSITIONS.get(role, (0, 0))

    # Calcular offset dentro del mismo rol
    same_role = [u for u, r in ROLES.items() if r == role]
    idx = same_role.index(unum) if unum in same_role else 0
    offsets = ROLE_OFFSETS.get(role, [(0, 0)])
    off_x, off_y = offsets[idx % len(offsets)]

    x = base_x + off_x
    y = base_y + off_y

    # Espejo para el equipo derecho
    if side == "r":
        x = -x

    return (x, y)