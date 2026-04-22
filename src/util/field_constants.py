"""
Constantes globales del campo de juego — RoboCup Soccer Simulator.

Todas las medidas están en unidades del simulador (aprox. 1 unidad = 1 metro).
El origen (0, 0) es el centro del campo.

Eje X: negativo = lado izquierdo, positivo = lado derecho
Eje Y: negativo = parte inferior, positivo = parte superior
"""

# ── Límites del campo ─────────────────────────────────────────────────────────

FIELD_LENGTH    = 105.0   # largo total
FIELD_WIDTH     = 68.0    # ancho total
FIELD_HALF_LEN  = 52.5    # mitad del largo
FIELD_HALF_WID  = 34.0    # mitad del ancho

# Límites absolutos — el balón y los jugadores NUNCA los rebasan
BOUNDARY_X_MAX  =  52.5
BOUNDARY_X_MIN  = -52.5
BOUNDARY_Y_MAX  =  34.0
BOUNDARY_Y_MIN  = -34.0

# Margen de seguridad antes del límite (para navegación)
BOUNDARY_MARGIN =  2.0

# ── Porterías ─────────────────────────────────────────────────────────────────

GOAL_WIDTH      = 14.02   # ancho de la portería
GOAL_HALF_WIDTH =  7.01
GOAL_DEPTH      =  2.0    # profundidad de la portería

# Posición X de cada portería
GOAL_L_X        = -52.5
GOAL_R_X        =  52.5

# Límites Y de cada portería
GOAL_Y_TOP      =  7.01
GOAL_Y_BOT      = -7.01

# ── Área grande (penalty area) ────────────────────────────────────────────────

PENALTY_AREA_LENGTH = 16.5    # largo desde la línea de fondo
PENALTY_AREA_WIDTH  = 40.32   # ancho total
PENALTY_AREA_HALF_W = 20.16

# Área grande izquierda
PENALTY_L_X_MIN = -52.5
PENALTY_L_X_MAX = -52.5 + PENALTY_AREA_LENGTH   # = -36.0
PENALTY_L_Y_MIN = -PENALTY_AREA_HALF_W           # = -20.16
PENALTY_L_Y_MAX =  PENALTY_AREA_HALF_W           # =  20.16

# Área grande derecha
PENALTY_R_X_MIN =  52.5 - PENALTY_AREA_LENGTH    # =  36.0
PENALTY_R_X_MAX =  52.5
PENALTY_R_Y_MIN = -PENALTY_AREA_HALF_W
PENALTY_R_Y_MAX =  PENALTY_AREA_HALF_W

# ── Área pequeña (goal area) ──────────────────────────────────────────────────

GOAL_AREA_LENGTH = 5.5
GOAL_AREA_WIDTH  = 18.32
GOAL_AREA_HALF_W =  9.16

# Área pequeña izquierda
GOAL_AREA_L_X_MIN = -52.5
GOAL_AREA_L_X_MAX = -52.5 + GOAL_AREA_LENGTH    # = -47.0
GOAL_AREA_L_Y_MIN = -GOAL_AREA_HALF_W
GOAL_AREA_L_Y_MAX =  GOAL_AREA_HALF_W

# Área pequeña derecha
GOAL_AREA_R_X_MIN =  52.5 - GOAL_AREA_LENGTH    # =  47.0
GOAL_AREA_R_X_MAX =  52.5
GOAL_AREA_R_Y_MIN = -GOAL_AREA_HALF_W
GOAL_AREA_R_Y_MAX =  GOAL_AREA_HALF_W

# ── Punto de penalti ──────────────────────────────────────────────────────────

PENALTY_SPOT_L_X = -52.5 + 11.0   # = -41.5
PENALTY_SPOT_R_X =  52.5 - 11.0   # =  41.5
PENALTY_SPOT_Y   =  0.0

# ── Centro del campo ──────────────────────────────────────────────────────────

CENTER_X = 0.0
CENTER_Y = 0.0
CENTER_CIRCLE_RADIUS = 9.15

# ── Distancias reglamentarias ─────────────────────────────────────────────────

FREE_KICK_DISTANCE  = 9.15   # distancia mínima en tiro libre / corner
KICKABLE_MARGIN     = 0.7    # radio en el que un jugador puede patear
CATCHABLE_LENGTH    = 1.2    # longitud del área de atrape del portero
CATCHABLE_WIDTH     = 1.0    # ancho del área de atrape del portero

# ── Normalización para la red neuronal ───────────────────────────────────────

def normalize_x(x: float) -> float:
    """Normaliza coordenada X al rango [-1, 1]."""
    return x / FIELD_HALF_LEN

def normalize_y(y: float) -> float:
    """Normaliza coordenada Y al rango [-1, 1]."""
    return y / FIELD_HALF_WID

def normalize_dist(d: float, max_dist: float = 100.0) -> float:
    """Normaliza una distancia al rango [0, 1]."""
    return min(1.0, d / max_dist)

def normalize_angle(a: float) -> float:
    """Normaliza un ángulo [-180, 180] al rango [-1, 1]."""
    return a / 180.0

def normalize_stamina(s: float, max_stamina: float = 8000.0) -> float:
    return min(1.0, s / max_stamina)

# ── Helpers de posición ───────────────────────────────────────────────────────

def is_in_penalty_area(x: float, y: float, side: str) -> bool:
    """¿Está el punto dentro del área de penalti del lado indicado?"""
    if side == "l":
        return (PENALTY_L_X_MIN <= x <= PENALTY_L_X_MAX and
                PENALTY_L_Y_MIN <= y <= PENALTY_L_Y_MAX)
    else:
        return (PENALTY_R_X_MIN <= x <= PENALTY_R_X_MAX and
                PENALTY_R_Y_MIN <= y <= PENALTY_R_Y_MAX)

def is_in_goal_area(x: float, y: float, side: str) -> bool:
    """¿Está el punto dentro del área pequeña del lado indicado?"""
    if side == "l":
        return (GOAL_AREA_L_X_MIN <= x <= GOAL_AREA_L_X_MAX and
                GOAL_AREA_L_Y_MIN <= y <= GOAL_AREA_L_Y_MAX)
    else:
        return (GOAL_AREA_R_X_MIN <= x <= GOAL_AREA_R_X_MAX and
                GOAL_AREA_R_Y_MIN <= y <= GOAL_AREA_R_Y_MAX)

def dist_to_boundary(x: float, y: float) -> float:
    """Distancia al límite más cercano del campo."""
    dist_x = min(abs(x - BOUNDARY_X_MAX), abs(x - BOUNDARY_X_MIN))
    dist_y = min(abs(y - BOUNDARY_Y_MAX), abs(y - BOUNDARY_Y_MIN))
    return min(dist_x, dist_y)

def is_near_boundary(x: float, y: float, margin: float = BOUNDARY_MARGIN) -> bool:
    return dist_to_boundary(x, y) <= margin

def clamp_to_field(x: float, y: float,
                   margin: float = 0.5) -> tuple[float, float]:
    """Asegura que el punto esté dentro del campo con un margen de seguridad."""
    x = max(BOUNDARY_X_MIN + margin, min(BOUNDARY_X_MAX - margin, x))
    y = max(BOUNDARY_Y_MIN + margin, min(BOUNDARY_Y_MAX - margin, y))
    return x, y

def my_goal_pos(side: str) -> tuple[float, float]:
    """Centro de mi portería."""
    return (GOAL_L_X if side == "l" else GOAL_R_X, 0.0)

def rival_goal_pos(side: str) -> tuple[float, float]:
    """Centro de la portería rival."""
    return (GOAL_R_X if side == "l" else GOAL_L_X, 0.0)

def is_in_my_half(x: float, side: str) -> bool:
    if side == "l":
        return x < 0
    return x > 0