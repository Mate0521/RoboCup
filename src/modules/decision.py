"""
Capa de decisión — coordina percepción, FSM y posicionamiento inicial.
"""
import logging
from modules.perception import Perception, PlayMode
from modules.fsm import FSM
from modules.role_assignment import get_role, get_start_position
from modules import actuators

logger = logging.getLogger(__name__)


class DecisionMaker:
    def __init__(self, perception: Perception):
        self.perception  = perception
        self.fsm: FSM | None = None
        self._positioned = False
        self._prev_pm    = None

    def _ensure_fsm(self):
        if self.fsm is None:
            role     = get_role(self.perception.state.unum)
            self.fsm = FSM(self.perception, role)
            logger.info(f"[Agente {self.perception.state.unum}] rol: {role}")

    def decide(self) -> str | None:
        state = self.perception.state
        pm    = state.play_mode

        self._ensure_fsm()

        # Detectar cambio de play mode para loggear
        if pm != self._prev_pm:
            logger.info(f"[Agente {state.unum}] play_mode → {pm.value}")
            self._prev_pm = pm

        # Posicionarse al inicio del juego o tras un gol
        reset_modes = (
            PlayMode.BEFORE_KICK_OFF,
            PlayMode.KICK_OFF_L,
            PlayMode.KICK_OFF_R,
            PlayMode.GOAL_L,
            PlayMode.GOAL_R,
        )

        if pm in reset_modes:
            if not self._positioned and state.unum > 0:
                self._positioned = True
                x, y = get_start_position(state.unum, state.side)
                cmd = actuators.move(x, y)
                logger.info(f"[Agente {state.unum}] → posición inicial ({x}, {y})")
                return cmd

        # Resetear flag de posicionamiento cuando empieza el juego
        if pm == PlayMode.PLAY_ON:
            self._positioned = False

        return self.fsm.step()