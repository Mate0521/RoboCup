"""
Capa de decisión de alto nivel.
Coordina percepción, FSM y actuadores.
"""
from modules.perception import Perception
from modules.fsm import FSM
from modules.role_assignment import get_role, get_start_position
from modules import actuators
import logging

logger = logging.getLogger(__name__)


class DecisionMaker:
    """
    Orquesta la toma de decisiones del agente cada ciclo.
    """

    def __init__(self, perception: Perception):
        self.perception = perception
        self.fsm = None
        self._positioned = False

    def _ensure_fsm(self):
        if self.fsm is None:
            role = get_role(self.perception.state.unum)
            self.fsm = FSM(self.perception, role)
            logger.info(f"Agente {self.perception.state.unum} — rol: {role}")

    def decide(self) -> str | None:
        """
        Retorna el comando a ejecutar en este ciclo.
        Retorna None si no hay acción.
        """
        state = self.perception.state
        play_mode = state.play_mode

        self._ensure_fsm()

        # Posicionarse al inicio o después de un gol
        if play_mode in ("before_kick_off", "kick_off_l", "kick_off_r"):
            if not self._positioned and state.unum > 0:
                self._positioned = True
                x, y = get_start_position(state.unum, state.side)
                cmd = actuators.move(x, y)
                logger.info(f"Posicionando en ({x}, {y})")
                return cmd

        # Resetear posicionamiento para próximos kick_offs
        if play_mode == "play_on":
            self._positioned = False

        # Delegar a la FSM
        cmd = self.fsm.step()
        if cmd:
            logger.debug(f"FSM → {cmd}")
        return cmd