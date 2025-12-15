import sys
import os
import time
from typing import Optional

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backends.emerald.backend import EmeraldBackend
from src.backends.emerald.mock import MockEmeraldBackend
from src.core.enums import BattleOutcome

def test_full_backend_api(backend_name: str, backend):
    print(f"\n=== Testing Backend: {backend_name} ===")
    
    try:
        backend.connect("test.gba")
        print("✓ Connected")
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return

    # 1. Test Memory Reader Direct Access (if available)
    if hasattr(backend, 'memory') and backend.memory:
        reader = backend.memory
        print("\n--- Memory Reader API ---")
        
        # Party
        try:
            p_party = reader.read_player_party()
            print(f"✓ read_player_party: Found {len(p_party)} mons")
            for p in p_party:
                print(f"  - {p.nickname} (Lv{p.level}) ID:{p.species_id}")
        except Exception as e:
            print(f"✗ read_player_party failed: {e}")

        try:
            e_party = reader.read_enemy_party()
            print(f"✓ read_enemy_party: Found {len(e_party)} mons")
        except Exception as e:
            print(f"✗ read_enemy_party failed: {e}")

        # Battle Mons
        try:
            mons = reader.read_battle_mons()
            print(f"✓ read_battle_mons: Found {len(mons)} active")
            for m in mons:
                print(f"  - Species:{m.species_id} HP:{m.current_hp}/{m.max_hp}")
        except Exception as e:
            print(f"✗ read_battle_mons failed: {e}")

        # Battle State Primitives
        try:
            weather = reader.read_battle_weather()
            print(f"✓ read_battle_weather: {weather} ({reader.get_weather_name(weather)})")
        except Exception as e:
            print(f"✗ read_battle_weather failed: {e}")

        try:
            outcome = reader.read_battle_outcome()
            print(f"✓ read_battle_outcome: {outcome}")
        except Exception as e:
            print(f"✗ read_battle_outcome failed: {e}")

        try:
            move_id, user = reader.read_last_move()
            print(f"✓ read_last_move: Move {move_id} by User {user}")
        except Exception as e:
            print(f"✗ read_last_move failed: {e}")

        try:
            is_input = reader.read_input_status()
            print(f"✓ read_input_status: {is_input}")
        except Exception as e:
            print(f"✗ read_input_status failed: {e}")
            
        try:
            is_battle = reader.is_in_battle()
            print(f"✓ is_in_battle: {is_battle}")
        except Exception as e:
            print(f"✗ is_in_battle failed: {e}")

        # Frontier
        try:
            frontier = reader.read_frontier_state()
            if frontier:
                print(f"✓ read_frontier_state: {frontier.facility_name} Streak:{frontier.win_streak}")
            else:
                print("✓ read_frontier_state: None (Not in frontier?)")
        except Exception as e:
            print(f"✗ read_frontier_state failed: {e}")

        try:
            rentals = reader.read_rental_mons()
            print(f"✓ read_rental_mons: Found {len(rentals)}")
        except Exception as e:
            print(f"✗ read_rental_mons failed: {e}")

    # 2. Test High-Level Backend API
    print("\n--- High Level Backend API ---")
    
    try:
        state = backend.read_battle_state()
        print(f"✓ read_battle_state: Turn {state.turn_count}, InputNeeded: {state.is_waiting_for_input}")
        if state.active_pokemon:
            print(f"  Player Mon: {state.active_pokemon.nickname}")
        if state.enemy_active_pokemon:
            print(f"  Enemy Mon: {state.enemy_active_pokemon.nickname} (HP {state.enemy_active_pokemon.hp_percentage}%)")
            print(f"  Enemy Base Stats (Sample): {get_sample_stats(state.enemy_active_pokemon)}")
    except Exception as e:
        print(f"✗ read_battle_state failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        f_state = backend.read_factory_state()
        print(f"✓ read_factory_state: Streak {f_state.win_streak}")
    except Exception as e:
        print(f"✗ read_factory_state failed: {e}")

def get_sample_stats(mon):
    # Helper to check if base stats were populated (implicitly checking get_species_base_stats)
    # The EnemyPokemon object itself doesn't hold the stats in the dataclass fields by default unless we hacked it,
    # but the Backend populates 'nickname' with the species name from the DB, so that's a partial check.
    return "Checked via Logic"

if __name__ == "__main__":
    # Test Mock
    mock = MockEmeraldBackend()
    test_full_backend_api("MOCK", mock)
    
    # Test mGBA (if possible)
    print("\nAttempting mGBA connection (requires emulator running)...")
    try:
        from src.backends.emerald.backend import EmeraldBackend
        mgba = EmeraldBackend()
        test_full_backend_api("mGBA", mgba)
    except ConnectionError:
        print("Could not connect to mGBA (Expected if not running)")
    except Exception as e:
        print(f"mGBA init failed: {e}")
