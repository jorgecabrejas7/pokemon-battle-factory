import time
import os
import sys
import logging

# Ensure project root is in sys.path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.client import MgbaClient
from src.memory import MemoryReader
from src.constants import ADDR_PLAYER_PARTY, ADDR_ENEMY_PARTY


# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_separator(char='-', length=60):
    print(char * length)

def main():
    client = MgbaClient()
    
    logger.info("Connecting to mGBA...")
    try:
        client.connect()
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        return

    memory = MemoryReader(client)

    try:
        while True:
            # 1. Capture Snapshot (Bulk Read)
            start_time = time.time()
            snapshot = memory.read_snapshot()
            req_time = (time.time() - start_time) * 1000

            clear_screen()
            print(f"=== POKEMON EMERALD BATTLE FACTORY OBSERVER ===")
            print(f"Fetch Time: {req_time:.2f}ms | Timestamp: {snapshot.timestamp:.2f}")
            
            outcome_str = {0: "Ongoing", 1: "Won", 2: "Lost", 3: "Draw", 4: "Ran"}.get(snapshot.outcome, f"Unknown({snapshot.outcome})")
            input_wait_str = "YES" if snapshot.input_wait else "NO"
            
            print(f"Outcome: {outcome_str:<15} Wait Input: {input_wait_str:<5} RNG: {snapshot.rng_seed:08X}")
            print(f"Phase:   {snapshot.phase:<15}")
            print(f"Last Move (Player): {snapshot.last_move_player}")
            print(f"Last Move (Enemy):  {snapshot.last_move_enemy}")
            print_separator('=')

            # Show Rental Candidates
            if snapshot.phase in ["RENTAL", "SWAP"] and snapshot.rental_candidates:
                print(f"RENTAL CANDIDATES / SWAP OPTIONS ({len(snapshot.rental_candidates)})")
                for r in snapshot.rental_candidates:
                    print(f" [{r.slot}] {r.species_name:<15} IVs: {r.ivs:<3} PID: {r.personality:X}")
                print_separator()

            # Active Battle
            if snapshot.active_battlers:
                print(f"ACTIVE BATTLERS ({len(snapshot.active_battlers)})")
                for mon in snapshot.active_battlers:
                    side = "PLAYER" if mon.slot % 2 == 0 else "ENEMY"
                    status_str = memory._get_status_string(mon.status)
                    print(f"[{side} SLOT {mon.slot}] {mon.species_name} (Lv.{mon.level})")
                    print(f"   HP: {mon.hp}/{mon.max_hp} ({mon.pct_hp*100:.0f}%) Status: {status_str}")
                    print(f"   Moves: {', '.join(mon.moves)}")
                    pp_str = ", ".join([f"{pp}" for pp in mon.pp])
                    print(f"   PP:    {pp_str}")
                    print_separator()

            # Player Party
            print("PLAYER PARTY (BENCH)")
            for i, mon in enumerate(snapshot.player_party):
                status_str = memory._get_status_string(mon.status)
                print(f" {i+1}. {mon.nickname} ({mon.species_name}) Lv.{mon.level}")
                print(f"     HP: {mon.hp}/{mon.max_hp} | Item: {mon.item_name} | Status: {status_str}")
                print(f"     Moves: {', '.join(mon.moves)}")
            print_separator()

            # Enemy Party
            print("ENEMY PARTY (For Swapping)")
            for i, mon in enumerate(snapshot.enemy_party):
                print(f" {i+1}. {mon.species_name} Lv.{mon.level} Item: {mon.item_name}")
                print(f"     HP: {mon.hp}/{mon.max_hp} | Moves: {', '.join(mon.moves)}")

            print_separator('=')
            print("Press Ctrl+C to exit.")
            # time.sleep(0.5) # Reduced sleep to test performance

    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
