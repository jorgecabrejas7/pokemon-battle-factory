import time
import os
import sys
import logging

"""
Pokémon Battle Factory (Emerald) - Enriched Observer

This is the main entry point for the Battle Factory AI/tooling system.
It connects to a running mGBA instance via socket (using the `connector.lua` script),
continuously reads the game state from memory, and displays a rich dashboard of information
including:
- Current Game Phase (Rental, Swap, Battle)
- Active Battle Status (HP, Moves, Stat Changes)
- Party Information
- Rental Selection Candidates

Usage:
    python3 src/main.py
"""

# Ensure project root is in sys.path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.client import MgbaClient
from src.memory import MemoryReader
from src.constants import ADDR_PLAYER_PARTY, ADDR_ENEMY_PARTY


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_screen() -> None:
    """Clears the terminal screen for a fresh dashboard update."""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_separator(char: str = '-', length: int = 60) -> None:
    """Prints a visual separator line."""
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
            print(f"=== POKEMON BATTLE FACTORY: ENRICHED OBSERVER ===")
            print(f"Fetch Time: {req_time:.2f}ms | Timestamp: {snapshot.timestamp:.2f}")
            
            outcome_map = {0: "Ongoing", 1: "Won", 2: "Lost", 3: "Draw", 4: "Ran"}
            print(f"Outcome: {outcome_map.get(snapshot.outcome, f'Unknown({snapshot.outcome})')}         Wait Input: {'YES' if snapshot.input_wait else 'NO'}   RNG: {snapshot.rng_seed:X}")
            print(f"Phase:   {snapshot.phase.ljust(15)} Weather: {snapshot.weather}")
            print(f"Last Move (Player): {snapshot.last_move_player.ljust(15)}")
            print(f"Last Move (Enemy):  {snapshot.last_move_enemy.ljust(35)}")
            print_separator('=')


            # Show Rental Candidates
            if snapshot.phase in ["RENTAL", "SWAP"] and snapshot.rental_candidates:
                print(f"RENTAL CANDIDATES / SWAP OPTIONS ({len(snapshot.rental_candidates)})")
                for r in snapshot.rental_candidates:
                    print(f" [{r.slot}] {r.species_name:<15} IVs: {r.ivs:<3} PID: {r.personality:X} Nature: {r.nature}")
                    if r.species_info:
                        bs = r.species_info.base_stats
                        print(f"      Base: H:{bs['hp']} A:{bs['atk']} D:{bs['def']} SA:{bs['spa']} SD:{bs['spd']} S:{bs['spe']}")
                    if r.item:
                        print(f"      Item: {r.item.name:<15} | {r.item.hold_effect} (Param: {r.item.hold_effect_param})")
                    if r.moves:
                        print(f"      Moves:")
                        for m in r.moves:
                            print(f"       - {m.name:<15} {m.type} {m.split} Pwr:{m.power:<3} Acc:{m.accuracy:<3} PP:{m.pp:<2} {m.effect}")
                print_separator()

            # Active Battle
            if snapshot.active_battlers:
                print(f"ACTIVE BATTLERS ({len(snapshot.active_battlers)})")
                for mon in snapshot.active_battlers:
                    side = "PLAYER" if mon.slot % 2 == 0 else "ENEMY"
                    status_str = memory._get_status_string(mon.status)
                    print(f"[{side} SLOT {mon.slot}] {mon.species_name} (Lv.{mon.level}) Nature: {mon.nature}")
                    print(f"   HP: {mon.hp}/{mon.max_hp} ({mon.pct_hp*100:.0f}%) Status: {status_str}")
                    
                    if mon.real_stats:
                        print(f"   Stats: Atk {mon.real_stats.get('atk')} | Def {mon.real_stats.get('def')} | "
                              f"SpA {mon.real_stats.get('spa')} | SpD {mon.real_stats.get('spd')} | Spe {mon.real_stats.get('spe')}")
                    if mon.species_info:
                        bs = mon.species_info.base_stats
                        print(f"   Base:  H:{bs['hp']} A:{bs['atk']} D:{bs['def']} SA:{bs['spa']} SD:{bs['spd']} S:{bs['spe']}")
                    
                    print(f"   Moves:")
                    for i, move in enumerate(mon.moves):
                        pp_val = mon.pp[i] if i < len(mon.pp) else 0
                        flags = ",".join(move.flags) if move.flags else "-"
                        print(f"     - {move.name:<15} {move.type[:3].upper()}/{move.split[:4]} Pwr:{move.power:<3} Acc:{move.accuracy:<3}% PP:{pp_val:<2}/{move.pp:<2}")
                        print(f"       Effect: {move.effect} | Target: {move.target} | Pri: {move.priority} | Flags: {flags}")
                    print_separator()

            # Player Party
            print("PLAYER PARTY (BENCH)")
            for i, mon in enumerate(snapshot.player_party):
                status_str = memory._get_status_string(mon.status)
                item_str = f"{mon.item.name}" if mon.item else "None"
                print(f" {i+1}. {mon.nickname} ({mon.species_name}) Lv.{mon.level} Nature: {mon.nature}")
                print(f"     HP: {mon.hp}/{mon.max_hp} | Item: {item_str} | Status: {status_str}")
                if mon.item and mon.item.hold_effect != "None":
                     print(f"     Item Effect: {mon.item.hold_effect} (Param: {mon.item.hold_effect_param})")
                
                if mon.real_stats:
                    print(f"     Stats: A:{mon.real_stats.get('atk')} D:{mon.real_stats.get('def')} SA:{mon.real_stats.get('spa')} SD:{mon.real_stats.get('spd')} S:{mon.real_stats.get('spe')}")
                if mon.species_info:
                    bs = mon.species_info.base_stats
                    print(f"     Base:  H:{bs['hp']} A:{bs['atk']} D:{bs['def']} SA:{bs['spa']} SD:{bs['spd']} S:{bs['spe']}")

                print(f"     Moves:")
                for i, move in enumerate(mon.moves):
                     pp_cur = mon.pp[i]
                     print(f"       - {move.name:<12} {move.type[:3]}/{move.split[:4]} P:{move.power} A:{move.accuracy} PP:{pp_cur}/{move.pp}")

            print_separator()

            # Enemy Party
            print("ENEMY PARTY (For Swapping)")
            for i, mon in enumerate(snapshot.enemy_party):
                item_str = f"{mon.item.name}" if mon.item else "None"
                print(f" {i+1}. {mon.species_name} Lv.{mon.level} Item: {item_str}")
                if mon.item and mon.item.hold_effect != "None":
                     print(f"     Item Effect: {mon.item.hold_effect}")
                print(f"     HP: {mon.hp}/{mon.max_hp}")
                
                if mon.real_stats:
                     print(f"     Stats: A:{mon.real_stats.get('atk')} D:{mon.real_stats.get('def')} SA:{mon.real_stats.get('spa')} SD:{mon.real_stats.get('spd')} S:{mon.real_stats.get('spe')}")
                # Enemy nature? Derived from PID if we had it. Party mon hash PID.
                print(f"     Nature: {mon.nature}")
                if mon.species_info:
                    bs = mon.species_info.base_stats
                    print(f"     Base:  H:{bs['hp']} A:{bs['atk']} D:{bs['def']} SA:{bs['spa']} SD:{bs['spd']} S:{bs['spe']}")
                
                moves_str = ", ".join([f"{m.name}({m.type[:3]})" for m in mon.moves])
                print(f"     Moves: {moves_str}")

            print_separator('=')
            print("Press Ctrl+C to exit.")
            # time.sleep(0.5) 

    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
