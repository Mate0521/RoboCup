"""
Capa de decisión — coordina percepción, FSM y posicionamiento inicial.
Fixes:
  - Reset de FSM y _positioned al recibir gol (antes quedaba en estado inválido)
  - Solicitar change_view(wide, high) en el primer ciclo para recibir
    dist_change y dir_change del balón (necesarios para intercepción)
  - _positioned se resetea correctamente en PLAY_ON y tras cada gol
"""
import logging
from modules.perception import Perception, PlayMode
from modules.fsm import FSM
from modules.role_assignment import get_role, get_start_position
from modules import actuators

logger = logging.getLogger(__name__)


class DecisionMaker:
    def __init__(self, perception: Perception, team_name: str = ""):
        self.perception  = perception
        self.perception._team_name_val = team_name
        self.fsm: FSM | None = None
        self._positioned = False
        self._prev_pm    = None
        self._view_set   = False   # Si ya pedimos wide/high view

    def _ensure_fsm(self):
        if self.fsm is None:
            role     = get_role(self.perception.state.unum)
            self.fsm = FSM(self.perception, role)
            logger.info(f"[Agente {self.perception.state.unum}] rol: {role}")

    def decide(self) -> str | None:
        state = self.perception.state
        pm    = state.play_mode

        self._ensure_fsm()

        # Primer ciclo: pedir wide+high para recibir velocidades del balón
        if not self._view_set and state.unum > 0:
            self._view_set = True
            return actuators.change_view("wide", "high")

        # Log de cambio de play mode
        if pm != self._prev_pm:
            logger.info(f"[Agente {state.unum}] play_mode → {pm.value}")
            # Al marcar gol, resetear posicionamiento para el siguiente kick_off
            if pm in (PlayMode.GOAL_L, PlayMode.GOAL_R):
                self._positioned = False
                # Resetear FSM para limpiar cooldowns y estado interno
                self.fsm = None
            self._prev_pm = pm

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
                self._ensure_fsm()
                x, y = get_start_position(state.unum, state.side)
                cmd = actuators.move(x, y)
                logger.info(f"[Agente {state.unum}] → posición inicial ({x}, {y})")
                return cmd

        if pm == PlayMode.PLAY_ON:
            self._positioned = False

        self._ensure_fsm()
        return self.fsm.step()