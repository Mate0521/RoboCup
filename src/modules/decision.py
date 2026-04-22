"""
DecisionMaker — orquesta FSM + GameRules + red neuronal.
Cambios v3:
  - update_score() llamado desde agent.py
  - notify_episode_end() llamado al terminar el partido
  - _ensure_ready() inicializa todo lazy al conocer unum
"""
import logging
import os
import numpy as np

from modules.perception import Perception, PlayMode
from modules.fsm import FSM, State as FSMState
from modules.game_rules import GameRules
from modules.role_assignment import get_role, get_tactical_position, clamp_to_zone
from modules.state_vector import StateVector
from ml.model import AgentBrain, ACTION_KICK, ACTION_STAY
from ml.reward import RewardCalculator
from ml.online_trainer import OnlineTrainer
from modules import actuators

logger = logging.getLogger(__name__)

TRAINING_MODE = os.getenv("TRAINING", "false").lower() == "true"


class DecisionMaker:
    def __init__(self, perception: Perception, team_name: str = ""):
        self.perception  = perception
        self.perception._team_name_val = team_name

        self.fsm: FSM | None            = None
        self.game_rules: GameRules      = GameRules(perception)
        self.brain: AgentBrain | None   = None
        self.trainer: OnlineTrainer | None = None

        self._role: str | None = None
        self._positioned       = False
        self._prev_pm          = None
        self._view_set         = False
        self._score_diff       = 0.0
        self._time_norm        = 0.0

    # ── Inicialización lazy ───────────────────────────────────────────────────

    def _ensure_ready(self):
        state = self.perception.state
        if state.unum == 0:
            return

        if self._role is None:
            self._role = get_role(state.unum)
            logger.info(f"[Agente {state.unum}] rol: {self._role}")

        if self.fsm is None:
            self.fsm = FSM(self.perception, self._role)

        if self.brain is None:
            self.brain = AgentBrain(self._role, training=TRAINING_MODE)
            if TRAINING_MODE:
                reward_calc  = RewardCalculator(
                    self.perception, self._role, state.unum
                )
                self.trainer = OnlineTrainer(self.brain, reward_calc)
                logger.info(f"[Agente {state.unum}] Modo entrenamiento ON")

    # ── API pública para agent.py ─────────────────────────────────────────────

    def update_score(self, score_diff: float):
        """Llamar desde agent.py cuando cambia el marcador."""
        self._score_diff = score_diff

    def notify_episode_end(self):
        """Llamar desde agent.py al terminar el partido o desconectarse."""
        if self.trainer:
            self.trainer.notify_episode_end()
        if self.brain:
            self.brain.save_weights()
            logger.info(
                f"[Agente {self.perception.state.unum}] "
                f"Pesos guardados al finalizar episodio."
            )

    # ── Punto de entrada principal ────────────────────────────────────────────

    def decide(self) -> str | None:
        state = self.perception.state
        pm    = state.play_mode

        self._ensure_ready()
        if self.fsm is None:
            return None

        # Primer ciclo: pedir wide+high view para recibir velocidades del balón
        if not self._view_set and state.unum > 0:
            self._view_set = True
            return actuators.change_view("wide", "high")

        # Detectar cambio de play mode
        if pm != self._prev_pm:
            logger.info(f"[Agente {state.unum}] play_mode → {pm.value}")
            if pm in (PlayMode.GOAL_L, PlayMode.GOAL_R):
                self._positioned = False
                self.fsm = None
                self._ensure_ready()
                if self.trainer:
                    self.trainer.notify_episode_end()
            self._prev_pm = pm

        # Posicionamiento inicial / tras gol
        reset_modes = (
            PlayMode.BEFORE_KICK_OFF,
            PlayMode.KICK_OFF_L, PlayMode.KICK_OFF_R,
            PlayMode.GOAL_L,     PlayMode.GOAL_R,
        )
        if pm in reset_modes and not self._positioned and state.unum > 0:
            self._positioned = True
            x, y = get_tactical_position(state.unum, state.side, "base")
            x, y = clamp_to_zone(x, y, state.unum, state.side)
            logger.info(f"[Agente {state.unum}] → posición ({x:.1f}, {y:.1f})")
            return actuators.move(x, y)

        if pm == PlayMode.PLAY_ON:
            self._positioned = False

        # Evaluar situación especial
        game_ctx = self.game_rules.evaluate()

        # Tiempo normalizado
        self._time_norm = min(1.0, state.time / 6000.0)

        # Posición táctica
        situation = game_ctx.get("situation", "base")
        tx, ty = get_tactical_position(state.unum, state.side, situation)
        tx, ty = clamp_to_zone(tx, ty, state.unum, state.side)

        # Vector de estado
        sv = StateVector(
            perception     = self.perception,
            role           = self._role or "midfielder",
            fsm_state      = self.fsm.current_state,
            target_x       = tx,
            target_y       = ty,
            time_norm      = self._time_norm,
            score_diff     = self._score_diff,
            players_active = self.perception.active_players_my_team(),
        )
        state_vec = sv.build()

        # ── Decisión neuronal ─────────────────────────────────────────────────
        if TRAINING_MODE and self.trainer:
            action_idx, params = self.trainer.step(state_vec, self._score_diff)
        elif self.brain:
            action_idx, params = self.brain.predict(state_vec)
        else:
            return self.fsm.step(game_ctx)

        # FSM como árbitro de coherencia
        fsm_cmd   = self.fsm.step(game_ctx)
        fsm_state = self.fsm.current_state

        # Red quiere patear pero no tenemos el balón → usar FSM
        if action_idx == ACTION_KICK and fsm_state != FSMState.KICK_BALL:
            return fsm_cmd

        # Jugada muerta o pausa → respetar FSM siempre
        if fsm_state in (FSMState.DEAD_BALL, FSMState.WAIT):
            return fsm_cmd

        # Convertir acción de la red a comando
        cmd = self.brain.action_to_command(action_idx, params, state.side)

        # Red dice STAY pero hay urgencia → usar FSM
        if cmd is None and fsm_state in (FSMState.MOVE_TO_BALL, FSMState.KICK_BALL):
            return fsm_cmd

        return cmd if cmd is not None else fsm_cmd