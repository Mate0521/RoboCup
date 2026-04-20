"""
Asignación de roles y zonas — formación 4-3-3.

Cada jugador tiene:
  - Una posición táctica por situación (base/defensiva/ofensiva/set piece)
  - Una ZONA ESTRICTA que NUNCA puede abandonar (límites x/y absolutos)

Zonas por número (side izquierdo, se espejan para side derecho):

  #1  Portero    — solo dentro del área grande propia
  #2  Defensa    — costado izquierdo (y negativo), no pasa la mitad
  #3  Defensa    — costado derecho (y positivo), no pasa la mitad
  #4  Defensa    — central izquierda, no pasa la mitad
  #5  Defensa    — central derecha, no pasa la mitad
  #6  Mediocampista — banda izquierda, puede cruzar un poco la mitad
  #7  Mediocampista — centro, libre en su franja horizontal
  #8  Mediocampista — banda derecha, puede cruzar un poco la mitad
  #9  Delantero  — banda izquierda, solo campo rival
  #10 Delantero  — centro, solo campo rival
  #11 Delantero  — banda derecha, solo campo rival
"""

# ── Roles por número ──────────────────────────────────────────────────────────

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

# ── Zonas estrictas por número (side izquierdo) ───────────────────────────────
# Formato: (x_min, x_max, y_min, y_max) — coordenadas absolutas del campo
# El jugador NUNCA saldrá de estos límites.
# Para side derecho: x_min, x_max se niegan e intercambian.

STRICT_ZONES = {
    #       x_min   x_max   y_min   y_max
    1:  (-52.5, -36.0, -20.0,  20.0),   # Portero: solo dentro del área grande
    2:  (-52.5,  -2.0, -34.0,  -8.0),   # Defensa izq: banda izquierda
    3:  (-52.5,  -2.0,   8.0,  34.0),   # Defensa der: banda derecha
    4:  (-52.5,  -2.0, -12.0,   0.5),   # Defensa central izq
    5:  (-52.5,  -2.0,  -0.5,  12.0),   # Defensa central der
    6:  (-42.0,  20.0, -34.0, -10.0),   # Mediocampista banda izq
    7:  (-36.0,  26.0, -13.0,  13.0),   # Mediocampista centro
    8:  (-42.0,  20.0,  10.0,  34.0),   # Mediocampista banda der
    9:  ( -4.0,  52.5, -34.0, -10.0),   # Delantero banda izq
    10: ( -4.0,  52.5, -13.0,  13.0),   # Delantero centro
    11: ( -4.0,  52.5,  10.0,  34.0),   # Delantero banda der
}

# ── Posiciones tácticas (side izquierdo) ──────────────────────────────────────
# TODAS deben estar dentro de la zona estricta del jugador correspondiente.

BASE_POSITIONS = {
    1:  (-48.0,   0.0),
    2:  (-32.0, -18.0),
    3:  (-32.0,  18.0),
    4:  (-35.0,  -6.0),
    5:  (-35.0,   6.0),
    6:  (-12.0, -18.0),
    7:  ( -8.0,   0.0),
    8:  (-12.0,  18.0),
    9:  ( 22.0, -18.0),
    10: ( 26.0,   0.0),
    11: ( 22.0,  18.0),
}

DEFENSIVE_POSITIONS = {
    1:  (-48.0,   0.0),
    2:  (-40.0, -18.0),
    3:  (-40.0,  18.0),
    4:  (-42.0,  -5.0),
    5:  (-42.0,   5.0),
    6:  (-28.0, -16.0),
    7:  (-24.0,   0.0),
    8:  (-28.0,  16.0),
    9:  ( -2.0, -16.0),
    10: (  0.0,   0.0),
    11: ( -2.0,  16.0),
}

OFFENSIVE_POSITIONS = {
    1:  (-48.0,   0.0),
    2:  (-22.0, -18.0),
    3:  (-22.0,  18.0),
    4:  (-24.0,  -5.0),
    5:  (-24.0,   5.0),
    6:  (  4.0, -18.0),
    7:  (  8.0,   0.0),
    8:  (  4.0,  18.0),
    9:  ( 34.0, -18.0),
    10: ( 38.0,   0.0),
    11: ( 34.0,  18.0),
}

SET_PIECE_ATTACK = {
    1:  (-48.0,   0.0),
    2:  (-14.0, -16.0),
    3:  (-14.0,  16.0),
    4:  (-10.0,  -5.0),
    5:  (-10.0,   5.0),
    6:  ( 10.0, -16.0),
    7:  ( 14.0,   0.0),
    8:  ( 10.0,  16.0),
    9:  ( 36.0, -16.0),
    10: ( 40.0,   0.0),
    11: ( 36.0,  16.0),
}

SET_PIECE_DEFENSE = {
    1:  (-48.0,   0.0),
    2:  (-44.0, -16.0),
    3:  (-44.0,  16.0),
    4:  (-44.0,  -4.0),
    5:  (-44.0,   4.0),
    6:  (-32.0, -14.0),
    7:  (-28.0,   0.0),
    8:  (-32.0,  14.0),
    9:  (-10.0, -12.0),
    10: ( -4.0,   0.0),
    11: (-10.0,  12.0),
}


# ── API pública ───────────────────────────────────────────────────────────────

def get_role(unum: int) -> str:
    return ROLES.get(unum, "midfielder")


def get_strict_zone(unum: int, side: str) -> tuple[float, float, float, float]:
    """
    Retorna (x_min, x_max, y_min, y_max) de la zona estricta del jugador.
    Para side derecho se espeja en X.
    """
    zone = STRICT_ZONES.get(unum, (-52.5, 52.5, -34.0, 34.0))
    xmin, xmax, ymin, ymax = zone
    if side == "r":
        xmin, xmax = -xmax, -xmin
    return (float(xmin), float(xmax), float(ymin), float(ymax))


def clamp_to_zone(x: float, y: float, unum: int, side: str) -> tuple[float, float]:
    """
    Ajusta (x, y) para que quede DENTRO de la zona estricta del jugador.
    Llamar SIEMPRE antes de navegar a cualquier posición.
    """
    xmin, xmax, ymin, ymax = get_strict_zone(unum, side)
    return (
        max(xmin, min(xmax, x)),
        max(ymin, min(ymax, y)),
    )


def get_tactical_position(unum: int, side: str, situation: str = "base") -> tuple[float, float]:
    """
    Retorna la posición táctica del jugador según la situación.
    """
    tables = {
        "base":        BASE_POSITIONS,
        "defensive":   DEFENSIVE_POSITIONS,
        "offensive":   OFFENSIVE_POSITIONS,
        "set_attack":  SET_PIECE_ATTACK,
        "set_defense": SET_PIECE_DEFENSE,
    }
    table = tables.get(situation, BASE_POSITIONS)
    x, y  = table.get(unum, (0.0, 0.0))

    if side == "r":
        x = -x

    return (float(x), float(y))


def get_start_position(unum: int, side: str) -> tuple[float, float]:
    return get_tactical_position(unum, side, "base")