import logging
import math

from modules.perception import PlayMode
from modules.role_assignment import get_strict_zone
from tactics.hybrid_fsm import State
from coordination.blackboard import Blackboard

logger = logging.getLogger(__name__)


ML_ELIGIBLE_STATES = {
    State.KICK_BALL,
    State.SUPPORT,
    State.GO_TO_POSITION,
}


class HybridController:
    def __init__(self, fsm, perception, role, unum, side, brain=None, trainer=None):
        self.fsm = fsm
        self.perception = perception
        self.role = role
        self.unum = unum
        self.side = side
        self.brain = brain
        self.trainer = trainer

    def decide(self, pressing=False):
        if self._is_deterministic():
            return self.fsm.step(pressing=pressing)

        if self._can_use_ml() and self.fsm.state in ML_ELIGIBLE_STATES:
            cmd = self._decide_ml(pressing)
            if cmd is not None:
                return cmd

        return self.fsm.step(pressing=pressing)

    def _is_deterministic(self):
        if self.role == "goalkeeper":
            return True
        if self.perception.state.play_mode != PlayMode.PLAY_ON:
            return True
        return False

    def _can_use_ml(self):
        return self.trainer is not None or self.brain is not None

    def _decide_ml(self, pressing):
        try:
            state_vec = self._build_state_vector()

            if self.trainer:
                score_diff = self._get_score_diff()
                action_idx, params = self.trainer.step(state_vec, score_diff)
            elif self.brain:
                action_idx, params, _ = self.brain.predict(state_vec)
            else:
                return None

            cmd = self.brain.action_to_command(action_idx, params, self.side)
            if cmd is not None and self._is_action_safe(action_idx, params):
                return cmd
        except Exception as e:
            logger.warning(f"[{self.unum}] ML fallo: {e}")

        return None

    def _build_state_vector(self):
        from modules.state_vector_v2 import StateVectorV2

        bb = Blackboard()
        state = self.perception.state
        xmin, xmax, ymin, ymax = get_strict_zone(self.unum, self.side)
        sx, sy = state.self_x, state.self_y
        target_x = (xmin + xmax) / 2
        target_y = (ymin + ymax) / 2

        score_diff = self._get_score_diff()
        time_norm = (state.time % 3000) / 3000.0
        players_active = max(1, len(bb.agent_positions))

        ball_prediction = []
        ball_pos = bb.ball.get("pos")
        ball_vel = bb.ball.get("vel", (0.0, 0.0))
        if ball_pos and ball_pos[0] is not None:
            try:
                from prediction.ball_predictor import BallPredictor
                predictor = BallPredictor()
                ball_prediction = predictor.predict(ball_pos, ball_vel, 10)
            except Exception:
                ball_prediction = []

        pass_eval = self._compute_pass_eval(bb)

        sv = StateVectorV2(
            perception=self.perception,
            role=self.role,
            fsm_state=self.fsm.state,
            target_x=target_x,
            target_y=target_y,
            time_norm=time_norm,
            score_diff=score_diff,
            players_active=players_active,
            ball_prediction=ball_prediction,
            pass_eval=pass_eval,
        )
        return sv.build()

    def _compute_pass_eval(self, bb):
        state = self.perception.state
        if not self.perception.can_see_ball() or state.self_x is None:
            return {}

        from tactics.pass_evaluation import PassEvaluator
        teammates = bb.get_all_agents_positions()
        opponents = bb.get_all_opponents_positions()

        if not opponents:
            opponents = [{"x": o.get("x", 0), "y": o.get("y", 0)} for o in state.opponents]
        if not teammates:
            teammates = []

        ball_predictor = None
        try:
            from prediction.ball_predictor import BallPredictor
            ball_predictor = BallPredictor()
        except Exception:
            pass

        evaluator = PassEvaluator()
        best = evaluator.evaluate(
            (state.self_x, state.self_y), self.side, teammates, opponents,
            ball_predictor=ball_predictor,
        )
        if best:
            return {
                "best_score": best.score,
                "best_distance": best.distance,
                "best_risk": best.risk,
                "openings_count": len(teammates),
                "passing_lanes": sum(1 for t in teammates if t.get("x", 0) is not None),
            }
        return {}

    def _get_score_diff(self):
        bb = Blackboard()
        if self.side == "l":
            return bb.score.get("left", 0) - bb.score.get("right", 0)
        return bb.score.get("right", 0) - bb.score.get("left", 0)

    @staticmethod
    def _is_action_safe(action_idx, params):
        return True
