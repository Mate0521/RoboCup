"""
Máquina de estados finitos (FSM) para el comportamiento del agente.
Cada estado retorna el comando a ejecutar en ese ciclo.
"""
from enum import Enum, auto
from modules.perception import Perception
from modules import actuators


class State(Enum):
    WAIT        = auto()   # Esperar inicio del juego
    SEARCH_BALL = auto()   # Buscar el balón girando
    MOVE_TO_BALL = auto()  # Moverse hacia el balón
    KICK_BALL   = auto()   # Patear el balón
    POSITION    = auto()   # Ir a posición táctica


class FSM:
    """
    FSM básica. Cada llamada a step() retorna el comando
    a enviar al servidor en ese ciclo.
    """

    def __init__(self, perception: Perception, role: str = "field"):
        self.perception = perception
        self.role = role
        self.state = State.WAIT
        self._search_turn_count = 0

    def step(self) -> str | None:
        state = self.perception.state
        play_mode = state.play_mode

        # En modos de espera, no hacer nada
        if play_mode in ("before_kick_off", "half_time", "time_over"):
            self.state = State.WAIT
            return None

        # Transiciones de estado
        self._update_state()

        # Ejecutar acción según estado actual
        return self._execute()

    def _update_state(self):
        perc = self.perception

        if self.state == State.WAIT:
            self.state = State.SEARCH_BALL

        elif self.state == State.SEARCH_BALL:
            if perc.can_see_ball():
                self.state = State.MOVE_TO_BALL

        elif self.state == State.MOVE_TO_BALL:
            if not perc.can_see_ball():
                self.state = State.SEARCH_BALL
            elif perc.is_ball_kickable():
                self.state = State.KICK_BALL

        elif self.state == State.KICK_BALL:
            if not perc.is_ball_kickable():
                self.state = State.SEARCH_BALL

    def _execute(self) -> str | None:
        state = self.perception.state

        if self.state == State.SEARCH_BALL:
            # Girar para buscar el balón
            self._search_turn_count += 1
            return actuators.turn(30)

        elif self.state == State.MOVE_TO_BALL:
            # Primero alinearse con el balón, luego correr hacia él
            angle = state.ball_angle or 0.0
            if abs(angle) > 10:
                return actuators.turn(angle)
            else:
                return actuators.dash(80)

        elif self.state == State.KICK_BALL:
            # Patear al frente con máxima potencia
            return actuators.kick(100, 0)

        elif self.state == State.POSITION:
            return actuators.dash(50)

        return None