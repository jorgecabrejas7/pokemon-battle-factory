import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backends.emerald.mock import MockEmeraldBackend

def test_mock_backend():
    print("Initializing Mock Backend...")
    backend = MockEmeraldBackend()
    backend.connect("test.gba")
    
    # Check Initial State
    state = backend.read_battle_state()
    print(f"Initial Turn: {state.turn_count}")
    print(f"Player HP: {state.active_pokemon.current_hp}")
    print(f"Waiting for input: {state.is_waiting_for_input}")
    
    assert state.turn_count == 0
    assert state.is_waiting_for_input == True
    
    # Simulate Action
    print("\nInjecting Action (ATTACK)...")
    backend.inject_action(1)
    
    state = backend.read_battle_state()
    print(f"Waiting for input (should be False): {state.is_waiting_for_input}")
    assert state.is_waiting_for_input == False
    
    # Simulate processing (Advance Frames)
    print("\nAdvancing Frames (Simulating turn)...")
    backend.advance_frame()
    
    state = backend.read_battle_state()
    print(f"Turn: {state.turn_count}")
    print(f"Player HP: {state.active_pokemon.current_hp}")
    print(f"Waiting for input: {state.is_waiting_for_input}")
    
    assert state.turn_count == 1
    assert state.active_pokemon.current_hp < 175 # Should have taken damage
    assert state.is_waiting_for_input == True
    
    print("\nMock Backend Test PASSED!")

if __name__ == "__main__":
    test_mock_backend()
