#!/usr/bin/env python3
"""
Refactored Verification Script for Pokemon Battle Factory.

This script verifies the "Step -> Observe" architecture.
It allows manual stepping through the game and prints the FULL observed state 
as defined in `game_variables_mapo.md`.

Now includes Interactive Mode with Action Map visibility.
"""

import sys
import argparse
import logging
from pathlib import Path
from pprint import pprint

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.controller.orchestrator import GameOrchestrator
from src.core.dataclasses import BattleState, BattleOutcome
from src.core.enums import BattleOutcome
from src.config import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Verifier")

# --- ACTION MAP ---
# ID -> (Name, Description)
ACTION_MAP = {
    0: ("None", "Do nothing (wait)"),
    1: ("A", "Confirm / Select"),
    2: ("B", "Back / Cancel"),
    3: ("SELECT", "Select button"),
    4: ("START", "Start button"),
    5: ("RIGHT", "Move Cursor Right"),
    6: ("LEFT", "Move Cursor Left"),
    7: ("UP", "Move Cursor Up"),
    8: ("DOWN", "Move Cursor Down"),
}

VALID_ACTIONS_MSG = "\n".join([f"  {k}: {v[0]} - {v[1]}" for k, v in ACTION_MAP.items()])

def determine_context(state: BattleState) -> str:
    """Determine the current context (Battle, Swap, Draft, etc.) based on flags."""
    # Logic to guess context
    if state.battle_outcome == BattleOutcome.ONGOING:
        # Check if we have active mons with HP
        if state.active_pokemon and state.active_pokemon.current_hp > 0:
            return "BATTLE (Ongoing)"
    
    # Check for Swap/Rental context
    # Usually implied if not in battle but have rental data or in menu
    if state.battler_in_menu_id > 0: 
        return "MENU / SELECTION"
    
    return "UNKNOWN / TRANSITION"

def print_state(state: BattleState):
    """Print the full game state matching game_variables_mapo.md."""
    context = determine_context(state)
    print("\n" + "="*80)
    print(f"OBSERVED STATE (Turn {state.turn_count}) | CONTEXT: {context}")
    print("="*80)
    
    # 1. Global Flags
    print(f" Battle Outcome: {state.battle_outcome.name} ({state.battle_outcome.value})")
    print(f" Input Lock: {state.battler_in_menu_id} | Waiting: {state.is_waiting_for_input}")
    print(f" Cursors: Action={state.action_cursor}, Move={state.move_cursor}")
    
    # 2. Player Side
    print("-" * 80)
    print(" PLAYER SIDE")
    if state.player_side_timer:
        st = state.player_side_timer
        print(f" Flags: Refl={st.reflect_timer} Light={st.lightscreen_timer} Mist={st.mist_timer} Safe={st.safeguard_timer}")
    
    # Active Mon
    if state.active_pokemon:
        p = state.active_pokemon
        print(f" [ACTIVE] {p.nickname} (Lv{p.level}) {p.current_hp}/{p.hp} HP")
        moves_str = ", ".join([f"{m.move_id}" for m in p.moves])
        print(f"          Moves: [{moves_str}]")
        print(f"          Stats: Atk={p.attack} Def={p.defense} SpA={p.sp_attack} SpD={p.sp_defense} Spe={p.speed}")
        if state.player_disable_struct:
            ds = state.player_disable_struct
            print(f"          Disable: Move={ds.disable_move}({ds.disable_timer}) Encore={ds.encored_move}({ds.encore_timer}) Taunt={ds.taunt_timer}")
    else:
        print(" [ACTIVE] None")

    # Party
    print(" [PARTY]")
    if state.party:
        for i, mon in enumerate(state.party):
            status = "FNT" if mon.current_hp == 0 else "OK"
            print(f"   {i+1}. {mon.nickname} (Lv{mon.level}) {mon.current_hp}/{mon.hp} [{status}]")
    else:
        print("   (Empty)")

    # 3. Enemy Side
    print("-" * 80)
    print(" ENEMY SIDE")
    if state.enemy_side_timer:
        st = state.enemy_side_timer
        print(f" Flags: Refl={st.reflect_timer} Light={st.lightscreen_timer} Mist={st.mist_timer} Safe={st.safeguard_timer}")
        
    # Active Mon
    if state.enemy_active_pokemon:
        e = state.enemy_active_pokemon
        print(f" [ACTIVE] {e.nickname} (Species {e.species_id}) {e.hp_percentage:.1f}% HP")
        print(f"          Known Moves: {[m.move_id for m in e.revealed_moves]}")
    else:
        print(" [ACTIVE] None")
        
    # Enemy Party
    print(" [PARTY]")
    if state.enemy_party:
        for i, mon in enumerate(state.enemy_party):
            # For enemy party we might not know HP exactly if not active, or it implies known info
            print(f"   {i+1}. {mon.nickname} (Species {mon.species_id}) HP%: {mon.hp_percentage:.1f}%")
    else:
         print("   (Empty / Hidden)")

    print("=" * 80)
    print("Possible Actions:")
    print(VALID_ACTIONS_MSG)
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Step verification")
    parser.add_argument("--action", type=int, default=0, help="Initial action to inject")
    args = parser.parse_args()
    
    print("Initializing Orchestrator...")
    orchestrator = GameOrchestrator()
    
    try:
        orchestrator.connect()
        print("Connected.")
        
        # Initial Read
        state = orchestrator.reset()
        print_state(state)
        
        while True:
            # Interactive Loop
            try:
                cmd = input("\n[Step] Enter Action ID/Name (e.g. '1', 'A', 'up') or 'q': ").strip().upper()
                if cmd == 'Q' or cmd == 'QUIT':
                    break
                
                if cmd == 'HELP' or cmd == '?':
                    print("Available Actions:")
                    print(VALID_ACTIONS_MSG)
                    continue
                
                # Parse Action
                action_id = 0
                if cmd.isdigit():
                    action_id = int(cmd)
                else:
                    # Reverse lookup name
                    found = False
                    for k, v in ACTION_MAP.items():
                        if v[0].upper() == cmd:
                            action_id = k
                            found = True
                            break
                    if not found and cmd:
                         print(f"Unknown command: {cmd}")
                         continue
                
                if action_id not in ACTION_MAP:
                     print(f"Invalid Action ID: {action_id}")
                     continue
                     
                print(f"Executing Step: {ACTION_MAP[action_id][0]} ({action_id})...")
                state = orchestrator.step(action_id)
                print_state(state)
                
            except ValueError:
                print("Invalid input.")
            except Exception as e:
                logger.error(f"Error during step: {e}")
                import traceback
                traceback.print_exc()
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        orchestrator.cleanup()

if __name__ == "__main__":
    main()
