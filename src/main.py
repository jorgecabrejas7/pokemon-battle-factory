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
            clear_screen()
            state = memory.get_game_state()
            print("=== POKEMON EMERALD BATTLE FACTORY OBSERVER ===")
            print(f"Outcome: {state['outcome']:<15} Wait Input: {state['input_wait']:<5} RNG: {state['rng']:08X}")
            print(f"Phase:   {state['phase']:<15}")
            print(f"Last Move (Player): {state['last_move_player']}")
            print(f"Last Move (Enemy):  {state['last_move_enemy']}")
            print_separator('=')

            # Show Rental Candidates if in Rental/Menu phase
            if state['phase'] == "RENTAL/MENU":
                rentals = memory.read_rental_mons()
                if rentals:
                    print(f"RENTAL CANDIDATES / SWAP OPTIONS ({len(rentals)})")
                    for r in rentals:
                        print(f" [{r.slot}] {r.species_name:<15} IVs: {r.ivs:<3} PID: {r.personality:X}")
                    print_separator()

            # Active Battle (Only if in battle or just to be safe)
            battle_mons = memory.read_battle_mons()
            if battle_mons:
                print(f"ACTIVE BATTLERS ({len(battle_mons)})")
                
                for mon in battle_mons:
                    side = "PLAYER" if mon.slot % 2 == 0 else "ENEMY"
                    status_str = memory._get_status_string(mon.status)
                    print(f"[{side} SLOT {mon.slot}] {mon.species_name} (Lv.{mon.level})")
                    print(f"   HP: {mon.hp}/{mon.max_hp}  Status: {status_str}")
                    print(f"   Moves: {', '.join(mon.moves)}")
                    # For PP, zip with moves
                    pp_str = ", ".join([f"{pp}" for pp in mon.pp])
                    print(f"   PP:    {pp_str}")
                    print_separator()

            # Player Party
            print("PLAYER PARTY (BENCH)")
            party = memory.read_party(ADDR_PLAYER_PARTY)
            for i, mon in enumerate(party):
                status_str = memory._get_status_string(mon.status)
                print(f" {i+1}. {mon.nickname} ({mon.species_name}) Lv.{mon.level}")
                print(f"     HP: {mon.hp}/{mon.max_hp} | Item: {mon.item_name} | Status: {status_str}")
                print(f"     Moves: {', '.join(mon.moves)}")
            print_separator()

            # Enemy Party (Cheating :D)
            print("ENEMY PARTY (For Swapping)")
            enemy_party = memory.read_party(ADDR_ENEMY_PARTY)
            for i, mon in enumerate(enemy_party):
                print(f" {i+1}. {mon.species_name} Lv.{mon.level} Item: {mon.item_name}")
                print(f"     HP: {mon.hp}/{mon.max_hp} | Moves: {', '.join(mon.moves)}")

            print_separator('=')
            print("Press Ctrl+C to exit.")
            time.sleep(0.5)

    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
