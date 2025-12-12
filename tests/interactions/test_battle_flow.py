import sys
import os
import time

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.backends.emerald.mock import MockEmeraldBackend

def test_battle_flow(backend):
    print(f"--- Testing Battle Flow Interaction ---")
    backend.connect("test.gba")
    
    # 1. Check Initial State
    state = backend.read_battle_state()
    print(f"Current Turn: {state.turn_count}")
    print(f"Waiting for Input: {state.is_waiting_for_input}")
    
    if not state.is_waiting_for_input:
        print("Emulator is busy... Fast-forwarding...")
        state = backend.run_until_input_required()
        print(f"Now Waiting: {state.is_waiting_for_input}")

    # 2. Inject Action
    print("Injecting Move (Slot 1)...")
    backend.inject_action(1)
    
    # 3. Step forward
    print("Advancing frames...")
    backend.advance_frame(60) # Simulate 1 second
    
    # 4. Check Result
    new_state = backend.read_battle_state()
    print(f"New Turn: {new_state.turn_count}")
    
    if new_state.turn_count > state.turn_count:
        print("SUCCESS: Turn counter advanced.")
    else:
        print("NOTE: Turn did not advance (Mock might need more frames or logic).")

if __name__ == "__main__":
    # Use Mock for now
    backend = MockEmeraldBackend()
    test_battle_flow(backend)
