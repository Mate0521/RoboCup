import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from unittest.mock import MagicMock
from tactics.hybrid_fsm import HybridFSM, State
from tactics.hybrid_controller import HybridController, ML_ELIGIBLE_STATES
from modules.perception import PlayMode


def test_controller_imports():
    assert HybridController is not None
    assert len(ML_ELIGIBLE_STATES) == 3
    assert State.KICK_BALL in ML_ELIGIBLE_STATES
    assert State.SUPPORT in ML_ELIGIBLE_STATES
    assert State.GO_TO_POSITION in ML_ELIGIBLE_STATES
    print("[OK] Controller imports + ML_ELIGIBLE_STATES")


def test_deterministic_goalkeeper():
    mock_perc = MagicMock()
    mock_perc.state.play_mode = PlayMode.PLAY_ON
    fsm = HybridFSM(mock_perc, "goalkeeper", 1, "l")
    controller = HybridController(fsm, mock_perc, "goalkeeper", 1, "l")
    assert controller._is_deterministic() is True
    print("[OK] Goalkeeper es deterministico -> FSM")


def test_deterministic_set_play():
    mock_perc = MagicMock()
    mock_perc.state.play_mode = PlayMode.FREE_KICK_L
    fsm = HybridFSM(mock_perc, "forward", 9, "l")
    controller = HybridController(fsm, mock_perc, "forward", 9, "l")
    assert controller._is_deterministic() is True
    print("[OK] Set piece es deterministico -> FSM")


def test_ml_eligible_when_play_on():
    mock_perc = MagicMock()
    mock_perc.state.play_mode = PlayMode.PLAY_ON
    mock_perc.state.self_x = 0
    mock_perc.state.self_y = 0
    mock_perc.state.body_direction = 0
    mock_perc.state.ball_distance = 50
    mock_perc.is_ball_kickable.return_value = False
    mock_perc.can_see_ball.return_value = False
    mock_perc.state.teammates = []
    mock_perc.state.opponents = []
    mock_perc.state.stamina = 8000
    mock_perc.state.effort = 1.0
    mock_perc.state.speed = 0
    mock_perc.state.speed_dir = 0
    mock_perc.state.head_angle = 0
    mock_perc.state.unum = 7
    mock_perc.state.side = "l"

    fsm = HybridFSM(mock_perc, "midfielder", 7, "l")
    controller = HybridController(fsm, mock_perc, "midfielder", 7, "l")

    assert controller._is_deterministic() is False
    print("[OK] PLAY_ON no es deterministico -> ML elegible")


def test_decide_fallback_to_fsm():
    mock_perc = MagicMock()
    mock_perc.state.play_mode = PlayMode.PLAY_ON
    mock_perc.state.self_x = 0
    mock_perc.state.self_y = 0
    mock_perc.state.body_direction = 0
    mock_perc.state.ball_distance = 50
    mock_perc.is_ball_kickable.return_value = False
    mock_perc.can_see_ball.return_value = False
    mock_perc.state.teammates = []
    mock_perc.state.opponents = []
    mock_perc.state.stamina = 8000
    mock_perc.state.effort = 1.0
    mock_perc.state.speed = 0
    mock_perc.state.speed_dir = 0
    mock_perc.state.head_angle = 0
    mock_perc.state.unum = 7
    mock_perc.state.side = "l"

    fsm = HybridFSM(mock_perc, "midfielder", 7, "l")
    # Sin brain ni trainer -> debe usar FSM siempre
    controller = HybridController(fsm, mock_perc, "midfielder", 7, "l")
    assert controller._can_use_ml() is False
    cmd = controller.decide()
    assert cmd is not None
    print(f"[OK] decide() sin ML retorna comando FSM: {cmd[:30]}")


def test_decide_with_brain_ml_state():
    mock_perc = MagicMock()
    mock_perc.state.play_mode = PlayMode.PLAY_ON
    mock_perc.state.self_x = 0
    mock_perc.state.self_y = 0
    mock_perc.state.body_direction = 0
    mock_perc.state.ball_distance = 5
    mock_perc.is_ball_kickable.return_value = True
    mock_perc.can_see_ball.return_value = True
    mock_perc.state.teammates = [{"unum": 2, "distance": 10, "angle": 30}]
    mock_perc.state.opponents = []
    mock_perc.state.stamina = 8000
    mock_perc.state.effort = 1.0
    mock_perc.state.speed = 0
    mock_perc.state.speed_dir = 0
    mock_perc.state.head_angle = 0
    mock_perc.state.ball_dist_change = 0
    mock_perc.state.ball_dir_change = 0
    mock_perc.state.ball_angle = 0
    mock_perc.state.unum = 7
    mock_perc.state.side = "l"

    fsm = HybridFSM(mock_perc, "midfielder", 7, "l")
    mock_brain = MagicMock()
    mock_brain.predict.return_value = (2, [0.5, 0.5, 0.5, 0.0], 0.3)
    mock_brain.action_to_command.return_value = "dash 50"

    controller = HybridController(fsm, mock_perc, "midfielder", 7, "l", brain=mock_brain)
    assert controller._can_use_ml() is True
    cmd = controller.decide()
    assert cmd is not None
    print(f"[OK] decide() con brain retorna comando ML: {cmd}")


def test_score_diff():
    from coordination.blackboard import Blackboard
    bb = Blackboard()
    bb.reset()
    bb.score["left"] = 2
    bb.score["right"] = 1

    mock_perc = MagicMock()
    fsm = HybridFSM(mock_perc, "midfielder", 7, "l")
    controller = HybridController(fsm, mock_perc, "midfielder", 7, "l")
    assert controller._get_score_diff() == 1
    print("[OK] score_diff left=2 right=1 -> diff=1")


if __name__ == "__main__":
    test_controller_imports()
    test_deterministic_goalkeeper()
    test_deterministic_set_play()
    test_ml_eligible_when_play_on()
    test_decide_fallback_to_fsm()
    test_decide_with_brain_ml_state()
    test_score_diff()
    print("\n>>> Todos los tests del HybridController pasaron exitosamente!")
