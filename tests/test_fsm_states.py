import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from tactics.hybrid_fsm import State, HybridFSM
from modules.state_vector_v2 import _get_fsm_idx
from coordination.blackboard import Blackboard


def test_all_states_have_unique_indices():
    """Verifica que los 10 estados tengan índices únicos en state vector."""
    indices = set()
    for state in State:
        idx = _get_fsm_idx(state)
        assert 0 <= idx <= 9, f"Índice fuera de rango para {state}: {idx}"
        assert idx not in indices, f"Índice duplicado {idx} para {state}"
        indices.add(idx)
    print(f"OK: 10 estados unicos mapeados correctamente: {sorted(indices)}")


def test_all_states_mapped():
    """Verifica que cada estado tenga un mapping válido."""
    expected = {
        State.WAIT: 0,
        State.SEARCH_BALL: 1,
        State.MOVE_TO_BALL: 2,
        State.KICK_BALL: 3,
        State.GO_TO_POSITION: 4,
        State.DEAD_BALL: 5,
        State.SUPPORT: 6,
        State.PRESS: 7,
        State.DRIBBLE: 8,
        State.COVER_LANE: 9,
    }
    for state, expected_idx in expected.items():
        actual = _get_fsm_idx(state)
        assert actual == expected_idx, f"{state}: esperado {expected_idx}, obtenido {actual}"
    print("OK: Todos los estados mapean correctamente al state vector")


def test_state_enum_has_10_states():
    """Verifica exactamente 10 estados."""
    states = list(State)
    assert len(states) == 10, f"Esperados 10 estados, hay {len(states)}"
    print(f"OK: Enum State tiene {len(states)} estados: {[s.name for s in states]}")


def test_blackboard_methods_exist():
    """Verifica que los métodos nuevos del Blackboard existan."""
    bb = Blackboard()
    assert hasattr(bb, 'get_all_agents_positions')
    assert hasattr(bb, 'get_all_opponents_positions')
    assert hasattr(bb, 'am_i_nearest_to_ball')
    assert hasattr(bb, 'get_nearest_opponent_to_ball')
    assert hasattr(bb, 'get_agents_in_range')
    assert hasattr(bb, 'get_agent_position')
    print("OK: Todos los métodos de Blackboard existen")


def test_blackboard_returns_empty_lists():
    """Verifica que los métodos retornen listas vacías cuando no hay datos."""
    bb = Blackboard()
    bb.reset()

    assert bb.get_all_agents_positions() == []
    assert bb.get_all_opponents_positions() == []
    assert bb.get_nearest_opponent_to_ball() is None
    assert bb.get_agent_position(1) == (None, None)
    print("OK: Blackboard retorna valores por defecto correctamente")


def test_blackboard_nearest_to_ball():
    """Verifica am_i_nearest_to_ball."""
    bb = Blackboard()
    bb.reset()
    bb.ball["pos"] = (0, 0)
    bb.update_agent_position(1, (2, 2), "forward")
    bb.update_agent_position(2, (10, 10), "midfielder")

    assert bb.am_i_nearest_to_ball(1), "Agente 1 debería ser el más cercano"
    assert not bb.am_i_nearest_to_ball(2), "Agente 2 NO debería ser el más cercano"
    print("OK: am_i_nearest_to_ball funciona correctamente")


def test_transition_to():
    """Verifica el sistema de transiciones del FSM."""
    from unittest.mock import MagicMock
    mock_perc = MagicMock()
    mock_perc.state.play_mode = MagicMock()
    mock_perc.state.play_mode.value = "play_on"
    mock_perc.state.self_x = 0
    mock_perc.state.self_y = 0
    mock_perc.state.body_direction = 0
    mock_perc.state.unum = 7
    mock_perc.state.ball_distance = 50.0
    mock_perc.is_ball_kickable.return_value = False
    mock_perc.can_see_ball.return_value = False
    mock_perc.state.teammates = []
    mock_perc.state.opponents = []

    fsm = HybridFSM(mock_perc, "midfielder", 7, "l")

    # Estado inicial
    assert fsm.state == State.GO_TO_POSITION

    # Probar transición
    fsm._transition_to(State.SUPPORT)
    assert fsm.state == State.SUPPORT
    assert fsm._state_duration == 0

    # Probar que no cambia si es el mismo estado
    fsm._transition_to(State.SUPPORT)
    assert fsm.state == State.SUPPORT
    assert fsm._state_duration == 1
    print("OK: Sistema de transiciones funciona correctamente")


if __name__ == "__main__":
    test_all_states_have_unique_indices()
    test_all_states_mapped()
    test_state_enum_has_10_states()
    test_blackboard_methods_exist()
    test_blackboard_returns_empty_lists()
    test_blackboard_nearest_to_ball()
    test_transition_to()
    print("\n>>> Todos los tests pasaron exitosamente!")
