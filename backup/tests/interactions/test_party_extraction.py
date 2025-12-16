import sys
import os
import time

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.backends.emerald.mock import MockEmeraldBackend
try:
    from src.backends.emerald.backend import EmeraldBackend
except ImportError:
    EmeraldBackend = None

def test_party_extraction(backend_class, rom_path):
    print(f"--- Testing Party Extraction with {backend_class.__name__} ---")
    try:
        backend = backend_class(rom_path)
    except Exception as e:
        print(f"Skipping: {e}")
        return

    backend.connect(rom_path)
    
    # In a real scenario, we might need to load a save state where a party exists
    # backend.connect(rom_path, save_state="save_with_party.ss1")
    
    # Read State
    state = backend.read_battle_state()
    
    print(f"Party Size: {len(state.party)}")
    for i, mon in enumerate(state.party):
        print(f"Slot {i+1}: {mon.nickname} (Species: {mon.species_id}) - HP: {mon.current_hp}/{mon.hp}")
        
    if len(state.party) > 0:
        print("SUCCESS: Party data successfully extracted.")
    else:
        print("WARNING: Party is empty.")
    print("\n")

if __name__ == "__main__":
    # 1. Test Mock
    test_party_extraction(MockEmeraldBackend, "test.gba")
    
    # 2. Test Real (if available)
    if EmeraldBackend:
        # Note: This requires a real ROM path to function correctly
        test_party_extraction(EmeraldBackend, "Pokemon Emerald.gba")
    else:
        print("EmeraldBackend not available (mgba missing).")
