"""
FSM v5 — Zonas estrictas + tiki-taka + freeze fix
==================================================

Correcciones vs v4:
  1. ZONAS ESTRICTAS POR NÚMERO: cada jugador tiene límites x/y que
     NUNCA puede cruzar. Se aplica en _nav() con clamp_to_zone() antes
     de cualquier movimiento. El portero nunca sale del área, los
     defensas no cruzan la mitad, los delanteros solo van al campo rival.

  2. FIX FREEZE (~500 ciclos): el freeze ocurría porque _last_x/_last_y
     acumulaba error con el tiempo y el jugador creía que "ya llegó"
     a su posición cuando en realidad estaba lejos. Fix: al llegar a
     posición táctica se resetea la memoria de posición para forzar
     re-triangulación en el siguiente ciclo.

  3. FIX RECEPTOR SE VA tras pase: el receptor (en SUPPORT) caminaba hacia
     el balón SIN cooldown. Ahora los jugadores en soporte se quedan en
     su posición de apoyo y solo se activan cuando el balón llega cerca
     o cuando son explícitamente los más cercanos.

  4. Pase SOLO hacia compañeros dentro de su zona: antes se pasaba a
     compañeros que luego tenían que salir de su zona para atrapar el
     balón. Ahora se verifica que el receptor esté en su zona estricta
     antes de hacer el pase.

  5. body_direction: se usa directamente el valor del servidor (body_dir
     de sense_body) como fuente de verdad. notify_turn() solo ajusta
     entre sense_bodys para suavizar el control.
"""

import math
import logging
from enum import Enum, auto

from modules.perception import Perception, PlayMode
from modules.role_assignment import (
    get_role, get_tactical_position, get_strict_zone, clamp_to_zone
)
from modules import actuators

logger = logging.getLogger(__name__)

# ── Constantes ─────────────────────────────────────────────────────────────────

KICKABLE        = 0.85    # Distancia kickable real del servidor
POS_THRESHOLD   = 2.2     # Distancia para considerar "llegué" a una posición
CLOSER_MARGIN   = 2.0     # Margen para ceder el paso a compañero más cercano
PASS_COOLDOWN   = 7       # Ciclos de espera tras pasar (≈ 700 ms)
SUPPORT_COOLDOWN = 4      # Ciclos en posición de soporte antes de poder moverse
INTERC_ANGLE    = 22.0    # Ángulo máx para intentar intercepción
INTERC_SPEED    = -0.25   # dist_change umbral para "el balón viene hacia mí"
MAX_POS_AGE     = 40      # Ciclos antes de invalidar memoria de posición

ACTION_RADIUS = {
    "goalkeeper": 14.0,
    "defender":   20.0,
    "midfielder": 27.0,
    "forward":    34.0,
}


# ── Estados ────────────────────────────────────────────────────────────────────

class St(Enum):
    INIT       = auto()
    HOLD_POS   = auto()   # Esperando en posición táctica
    APPROACH   = auto()   # Yendo al balón
    HAVE_BALL  = auto()   # Tengo el balón
    SUPPORT    = auto()   # Soporte posicional (compañero tiene el balón)
    GOALKEEPER = auto()   # Lógica exclusiva del portero


# ── FSM principal ──────────────────────────────────────────────────────────────

class FSM:
    def __init__(self, perception: Perception, role: str):
        self.perception    = perception
        self.role          = role
        self.state         = St.GOALKEEPER if role == "goalkeeper" else St.INIT
        self._turn_dir     = 1
        self._turn_cnt     = 0
        self._pass_cd      = 0          # cooldown tras pasar
        self._support_cd   = 0          # cooldown en posición de soporte
        self._last_x: float | None = None
        self._last_y: float | None = None
        self._pos_age: int = 0          # ciclos desde última triangulación real

    # ── Ciclo principal ────────────────────────────────────────────────────────

    def step(self) -> str | None:
        pm = self.perception.state.play_mode
        if pm in (PlayMode.TIME_OVER, PlayMode.HALF_TIME):
            return None

        if self._pass_cd > 0:
            self._pass_cd -= 1
        if self._support_cd > 0:
            self._support_cd -= 1

        # Invalidar memoria de posición si es muy vieja
        self._pos_age += 1
        if self._pos_age > MAX_POS_AGE:
            self._last_x = None
            self._last_y = None
            self._pos_age = 0

        if self.role == "goalkeeper":
            return self._goalkeeper()
        if self._is_stopped(pm):
            return self._dead_ball()
        return self._field_player()

    # ── Portero ────────────────────────────────────────────────────────────────

    def _goalkeeper(self) -> str:
        perc  = self.perception
        state = perc.state
        side  = state.side
        unum  = state.unum

        # Zona estricta del portero
        xmin, xmax, ymin, ymax = get_strict_zone(unum, side)
        gx = xmin + 2 if side == "l" else xmax - 2

        # Despejar si tengo el balón — hacia el flanco con menos rivales
        if perc.is_ball_kickable():
            opp_left  = sum(1 for o in state.opponents if o.get("angle", 0) > 0)
            opp_right = sum(1 for o in state.opponents if o.get("angle", 0) < 0)
            kick_dir = 40.0 if opp_left <= opp_right else -40.0
            self._pass_cd = PASS_COOLDOWN
            return actuators.kick(100, kick_dir)

        # Atrapar si el balón viene directo
        if perc.ball_is_moving_toward_goal() and \
           state.ball_distance and state.ball_distance < 10:
            return actuators.catch(state.ball_angle or 0.0)

        # Posicionarse lateralmente con el balón, dentro del área
        if perc.can_see_ball():
            sx, sy = self._pos()
            if sx is not None:
                bd    = state.body_direction
                bang  = state.ball_angle or 0.0
                bdist = state.ball_distance or 0.0
                by_abs = sy + bdist * math.sin(math.radians(bang + bd))
                ty = max(ymin + 1, min(ymax - 1, by_abs * 0.3))
            else:
                ty = 0.0
        else:
            ty = 0.0

        return self._nav(gx, ty)

    # ── Jugador de campo ───────────────────────────────────────────────────────

    def _field_player(self) -> str:
        perc  = self.perception
        state = perc.state

        # Tengo el balón y puedo actuar
        if perc.is_ball_kickable() and self._pass_cd == 0:
            self.state = St.HAVE_BALL
            return self._decide_action()

        # Cooldown activo (acabo de pasar) → soporte
        if self._pass_cd > 0:
            self.state = St.SUPPORT
            return self._go_support()

        # Veo el balón
        if perc.can_see_ball():
            ball_dist = state.ball_distance or 999.0

            # El balón viene hacia mí → interceptar (prioridad máxima)
            if self._ball_coming_to_me(ball_dist):
                self.state = St.APPROACH
                return self._approach_ball()

            # Balón fuera de mi zona de rol → posición táctica
            if not self._ball_in_my_zone():
                self.state = St.HOLD_POS
                return self._go_tactical()

            # Balón demasiado lejos → posición táctica
            if ball_dist > ACTION_RADIUS[self.role]:
                self.state = St.HOLD_POS
                return self._go_tactical()

            # Hay compañero más cercano al balón → soporte (si cooldown permite)
            if self._teammate_closer_to_ball(ball_dist):
                if self._support_cd == 0:
                    self.state = St.SUPPORT
                    return self._go_support()
                else:
                    # Cooldown activo: quedarse quieto en posición actual
                    return actuators.turn(5)

            # Soy el más cercano → perseguir
            self.state = St.APPROACH
            return self._approach_ball()

        # No veo el balón → scan girando (dentro de zona)
        self.state = St.HOLD_POS
        return self._scan()

    # ── Aproximarse al balón ───────────────────────────────────────────────────

    def _approach_ball(self) -> str:
        state = self.perception.state
        angle = state.ball_angle or 0.0

        if abs(angle) > 6:
            turn_pow = max(10.0, min(50.0, abs(angle) * 0.85))
            turn_amt = math.copysign(turn_pow, angle)
            self.perception.notify_turn(turn_amt)
            return actuators.turn(turn_amt)

        dist  = state.ball_distance or 10.0
        power = 100.0 if dist > 4.0 else max(55.0, dist * 14.0)
        return actuators.dash(power)

    # ── Decidir acción con el balón ────────────────────────────────────────────

    def _decide_action(self) -> str:
        cmd = self._try_pass()
        if cmd:
            self._pass_cd = PASS_COOLDOWN
            return cmd

        # Sin pase disponible → avanzar con control
        state    = self.perception.state
        kick_dir = 6.0 if state.side == "l" else -6.0
        self._pass_cd = 3
        return actuators.kick(70, kick_dir)

    # ── Pase (tiki-taka) ───────────────────────────────────────────────────────

    def _try_pass(self) -> str | None:
        """
        Selecciona el mejor compañero para pasar.
        Solo pasa a compañeros que puedan recibir DENTRO de su zona estricta.
        """
        state     = self.perception.state
        teammates = state.teammates
        sx, sy    = self._pos()

        best       = None
        best_score = -9999.0

        for tm in teammates:
            dist = tm.get("distance", 9999.0)
            ang  = tm.get("angle",    0.0)
            name = tm.get("name",     "")

            # Rango útil de pase
            if not (3.0 < dist < 28.0):
                continue

            # Estimar posición absoluta del compañero
            tm_x, tm_y = None, None
            if sx is not None:
                bd     = state.body_direction
                tm_rad = math.radians(ang + bd)
                tm_x   = sx + dist * math.cos(tm_rad)
                tm_y   = sy + dist * math.sin(tm_rad)

            # Intentar extraer número del compañero para verificar su zona
            # El nombre tiene formato "p <team> <unum>" o "p <team>"
            tm_unum = self._extract_unum(name)
            if tm_unum is not None and tm_x is not None and tm_y is not None:
                cx, cy = clamp_to_zone(tm_x, tm_y, tm_unum, state.side)
                # Si el punto de recepción está muy lejos de su zona, skip
                if math.hypot(cx - tm_x, cy - tm_y) > 4.0:
                    continue

            # Score: preferir compañeros libres, adelantados, no demasiado lejos
            angle_pen  = abs(ang) * 0.25
            dist_pen   = dist * 0.12
            score      = 28.0 - angle_pen - dist_pen

            # Bonus si está más adelantado que yo
            if tm_x is not None and sx is not None:
                my_x = sx
                if state.side == "l" and tm_x > my_x + 4:
                    score += 6.0
                elif state.side == "r" and tm_x < my_x - 4:
                    score += 6.0

            # Bonus si no tiene rival cerca
            rivals_near = sum(
                1 for o in state.opponents
                if abs(o.get("angle", 999) - ang) < 14
                and o.get("distance", 999) < dist + 2
            )
            if rivals_near == 0:
                score += 10.0

            if score > best_score:
                best_score = score
                best = tm

        if best is None or best_score < 4.0:
            return None

        ang   = best["angle"]
        dist  = best["distance"]
        power = max(32.0, min(82.0, 9.0 + dist * 2.4))
        logger.debug(f"[{state.unum}] PASE ang={ang:.1f}° dist={dist:.1f}m pow={power:.0f}")
        return actuators.kick(power, ang)

    def _extract_unum(self, name: str) -> int | None:
        """Extrae el número de jugador del nombre del objeto (ej: 'p Team 7' → 7)."""
        parts = name.split()
        if len(parts) >= 3:
            try:
                return int(parts[2])
            except ValueError:
                pass
        return None

    # ── Soporte posicional ─────────────────────────────────────────────────────

    def _go_support(self) -> str:
        """
        Moverse a posición de soporte dentro de la zona estricta.
        El offset Y alterna por número de jugador para no amontonarse.
        IMPORTANTE: la posición de soporte SIEMPRE queda dentro de la zona.
        """
        state  = self.perception.state
        unum   = state.unum
        side   = state.side
        sit    = self._situation()
        tx, ty = get_tactical_position(unum, side, sit)

        # Offset Y para abrir ángulo de pase
        offset = 6.0 if unum % 2 == 0 else -6.0
        ty_raw = ty + offset

        # Clamp estricto a zona del jugador
        tx, ty = clamp_to_zone(tx, ty_raw, unum, side)

        # Marcar cooldown para no moverse agresivamente
        self._support_cd = SUPPORT_COOLDOWN
        return self._nav(tx, ty)

    # ── Ir a posición táctica ─────────────────────────────────────────────────

    def _go_tactical(self) -> str:
        state  = self.perception.state
        unum   = state.unum
        side   = state.side
        sit    = self._situation()
        tx, ty = get_tactical_position(unum, side, sit)
        # clamp extra por seguridad (debería ya estar dentro)
        tx, ty = clamp_to_zone(tx, ty, unum, side)
        return self._nav(tx, ty)

    # ── Pelota muerta ─────────────────────────────────────────────────────────

    def _dead_ball(self) -> str | None:
        state = self.perception.state
        perc  = self.perception
        unum  = state.unum
        side  = state.side

        if perc.is_my_team_kickoff():
            if perc.can_see_ball():
                bd = state.ball_distance or 999
                if bd < 4.0 and self.role != "goalkeeper":
                    if perc.is_ball_kickable() and self._pass_cd == 0:
                        cmd = self._try_pass()
                        if cmd:
                            self._pass_cd = PASS_COOLDOWN
                            return cmd
                        return actuators.kick(68, 8.0 if side == "l" else -8.0)
                    ang = state.ball_angle or 0.0
                    if abs(ang) > 7:
                        return actuators.turn(ang)
                    return actuators.dash(88)
            tx, ty = get_tactical_position(unum, side, "set_attack")
            tx, ty = clamp_to_zone(tx, ty, unum, side)
            return self._nav(tx, ty)
        else:
            tx, ty = get_tactical_position(unum, side, "set_defense")
            tx, ty = clamp_to_zone(tx, ty, unum, side)
            return self._nav(tx, ty)

    # ── Navegación ────────────────────────────────────────────────────────────

    def _nav(self, tx: float, ty: float) -> str:
        """
        Navega a (tx, ty) SIEMPRE dentro de la zona estricta del jugador.
        Fix freeze: si _pos() devuelve None más de N veces seguidas, hacer
        scan en vez de congelar.
        """
        state = self.perception.state
        unum  = state.unum
        side  = state.side

        # Garantía final: el destino nunca sale de la zona estricta
        tx, ty = clamp_to_zone(tx, ty, unum, side)

        sx, sy = self._pos()
        if sx is None:
            return self._scan()

        dx   = tx - sx
        dy   = ty - sy
        dist = math.hypot(dx, dy)

        if dist < POS_THRESHOLD:
            # Llegamos — resetear memoria para forzar re-triangulación
            # Esto evita el freeze por posición acumulada incorrecta
            self._last_x = None
            self._last_y = None
            self._pos_age = 0
            return actuators.turn(8)

        target_abs = math.degrees(math.atan2(dy, dx))
        diff       = self._angle_diff(target_abs, state.body_direction)

        if abs(diff) > 8:
            turn_amt = max(-42.0, min(42.0, diff * 0.88))
            self.perception.notify_turn(turn_amt)
            return actuators.turn(turn_amt)

        power = max(80.0, min(100.0, dist * 9.0))
        return actuators.dash(power)

    def _scan(self) -> str:
        """Giro alterno para buscar flags o balón."""
        self._turn_cnt += 1
        if self._turn_cnt > 3:
            self._turn_cnt = 0
            self._turn_dir *= -1
        amt = 38 * self._turn_dir
        self.perception.notify_turn(amt)
        return actuators.turn(amt)

    # ── Estimación de posición con memoria ───────────────────────────────────

    _FLAGS = {
        "f c":      (  0.0,   0.0), "f c t":   (  0.0,  34.0),
        "f c b":    (  0.0, -34.0), "f l t":   (-52.5,  34.0),
        "f l b":    (-52.5, -34.0), "f r t":   ( 52.5,  34.0),
        "f r b":    ( 52.5, -34.0), "f l 0":   (-52.5,   0.0),
        "f r 0":    ( 52.5,   0.0), "f t 0":   (  0.0,  34.0),
        "f b 0":    (  0.0, -34.0), "f g l b": (-52.5,  -7.01),
        "f g l t":  (-52.5,   7.01),"f g r b": ( 52.5,  -7.01),
        "f g r t":  ( 52.5,   7.01),
        "f l t 30": (-52.5,  30.0), "f l t 20": (-52.5,  20.0),
        "f l t 10": (-52.5,  10.0), "f l b 10": (-52.5, -10.0),
        "f l b 20": (-52.5, -20.0), "f l b 30": (-52.5, -30.0),
        "f r t 10": ( 52.5,  10.0), "f r t 20": ( 52.5,  20.0),
        "f r t 30": ( 52.5,  30.0), "f r b 10": ( 52.5, -10.0),
        "f r b 20": ( 52.5, -20.0), "f r b 30": ( 52.5, -30.0),
        "f t l 10": (-10.0,  34.0), "f t l 20": (-20.0,  34.0),
        "f t l 30": (-30.0,  34.0), "f t l 40": (-40.0,  34.0),
        "f t l 50": (-50.0,  34.0), "f t r 10": ( 10.0,  34.0),
        "f t r 20": ( 20.0,  34.0), "f t r 30": ( 30.0,  34.0),
        "f t r 40": ( 40.0,  34.0), "f t r 50": ( 50.0,  34.0),
        "f b l 10": (-10.0, -34.0), "f b l 20": (-20.0, -34.0),
        "f b l 30": (-30.0, -34.0), "f b l 40": (-40.0, -34.0),
        "f b l 50": (-50.0, -34.0), "f b r 10": ( 10.0, -34.0),
        "f b r 20": ( 20.0, -34.0), "f b r 30": ( 30.0, -34.0),
        "f b r 40": ( 40.0, -34.0), "f b r 50": ( 50.0, -34.0),
    }

    def _pos(self) -> tuple[float | None, float | None]:
        """
        Triangulación ponderada con memoria limitada.
        La memoria expira en MAX_POS_AGE ciclos para evitar freeze
        por posición acumulada incorrecta.
        """
        state   = self.perception.state
        bd      = state.body_direction
        samples = []

        for obj in state.visible_objects:
            name = obj.get("name", "")
            d    = obj.get("distance", 9999.0)
            ang  = obj.get("angle",    0.0)
            if name not in self._FLAGS or d > 56:
                continue
            fx, fy  = self._FLAGS[name]
            abs_ang = math.radians(ang + bd)
            ex = fx - d * math.cos(abs_ang)
            ey = fy - d * math.sin(abs_ang)
            w  = 1.0 / max(d * d, 0.01)
            samples.append((ex, ey, w))

        if samples:
            samples.sort(key=lambda s: -s[2])
            samples = samples[:5]
            tw  = sum(s[2] for s in samples)
            x   = sum(s[0] * s[2] for s in samples) / tw
            y   = sum(s[1] * s[2] for s in samples) / tw
            # Actualizar memoria y resetear edad
            self._last_x  = x
            self._last_y  = y
            self._pos_age = 0
            return x, y

        # Sin flags → usar memoria (válida hasta MAX_POS_AGE ciclos)
        return self._last_x, self._last_y

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ball_coming_to_me(self, ball_dist: float) -> bool:
        state = self.perception.state
        return (
            ball_dist < ACTION_RADIUS[self.role]
            and state.ball_dist_change < INTERC_SPEED
            and abs(state.ball_angle or 0) < INTERC_ANGLE
        )

    def _ball_in_my_zone(self) -> bool:
        """
        Verifica si el balón está dentro de la zona de rol del jugador
        usando la posición estimada del balón en coordenadas absolutas.
        """
        state  = self.perception.state
        unum   = state.unum
        side   = state.side
        sx, sy = self._pos()

        if sx is None or not self.perception.can_see_ball():
            return True  # Sin información, no restringir

        bd      = state.body_direction
        bang    = state.ball_angle or 0.0
        bdist   = state.ball_distance or 0.0
        bx      = sx + bdist * math.cos(math.radians(bang + bd))
        by      = sy + bdist * math.sin(math.radians(bang + bd))

        xmin, xmax, ymin, ymax = get_strict_zone(unum, side)
        # Zona de atracción del balón: ligeramente más grande que la zona estricta
        margin = 8.0
        return (xmin - margin) <= bx <= (xmax + margin) and \
               (ymin - margin) <= by <= (ymax + margin)

    def _teammate_closer_to_ball(self, my_dist_to_ball: float) -> bool:
        """
        Compara la distancia estimada del compañero al BALÓN
        (no al jugador que pregunta) usando ley del coseno.
        """
        state    = self.perception.state
        ball_ang = state.ball_angle or 0.0

        for tm in state.teammates:
            tm_dist = tm.get("distance", 9999.0)
            tm_ang  = tm.get("angle",    0.0)
            delta   = math.radians(tm_ang - ball_ang)
            tm_to_ball = math.sqrt(
                tm_dist ** 2 + my_dist_to_ball ** 2
                - 2 * tm_dist * my_dist_to_ball * math.cos(delta)
            )
            if tm_to_ball < my_dist_to_ball - CLOSER_MARGIN:
                return True
        return False

    def _situation(self) -> str:
        perc  = self.perception
        state = perc.state

        if not perc.can_see_ball():
            return "base"

        ball_dist = state.ball_distance or 999.0
        min_opp   = min((o.get("distance", 999) for o in state.opponents), default=999.0)

        if ball_dist < 8 and len(state.teammates) > 0:
            return "offensive"
        if ball_dist < min_opp - 3:
            return "offensive"
        elif min_opp < ball_dist - 3:
            return "defensive"
        return "base"

    @staticmethod
    def _angle_diff(a: float, b: float) -> float:
        d = (a - b) % 360
        if d > 180:
            d -= 360
        return d

    @staticmethod
    def _is_stopped(pm: PlayMode) -> bool:
        return pm not in (
            PlayMode.PLAY_ON,
            PlayMode.BEFORE_KICK_OFF,
            PlayMode.KICK_OFF_L,
            PlayMode.KICK_OFF_R,
            PlayMode.HALF_TIME,
            PlayMode.TIME_OVER,
            PlayMode.GOAL_L,
            PlayMode.GOAL_R,
            PlayMode.UNKNOWN,
        )