#!/usr/bin/env python3
"""
Battle Factory Runner - Execute game loop with pluggable agents.

This script provides multiple ways to run the Battle Factory:
1. Full automatic episodes with random/trained agents
2. Interactive mode with step-by-step control
3. Phase-level stepping (draft, battle, swap)
4. Turn-level stepping (individual battle turns)

Prerequisites:
1. mGBA running with Pokemon Emerald ROM loaded
2. connector.lua script loaded in mGBA (Tools -> Scripting -> Load)
3. Game at appropriate starting point (title screen or in-game)

Usage:
    # Run automatic episode with random agents
    python scripts/run_random.py --episodes 1
    
    # Interactive mode with full control
    python scripts/run_random.py --interactive
    
    # Step-by-step debugging
    python scripts/run_random.py --step-mode
    
    # Test connection only
    python scripts/run_random.py --test-connection
"""

import sys
import os
import argparse
import logging
import time
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.game_controller import GameController, GameState, PhaseResult, TurnResult
from src.agents import (
    RandomDrafter, RandomTactician, create_random_agents,
    InteractiveDrafter, InteractiveTactician, create_interactive_agents,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BattleFactoryRunner")


# =============================================================================
# Agent Wrappers
# =============================================================================

def wrap_drafter_for_controller(drafter):
    """
    Wrap a drafter agent to match GameController's expected signature.
    
    Controller expects: (obs, state) -> action
    Our agents expect: (obs) -> action
    """
    def wrapped(obs, state):
        return drafter(obs)
    return wrapped


def wrap_tactician_for_controller(tactician):
    """
    Wrap a tactician agent to match GameController's expected signature.
    
    Controller expects: (obs, state, mask) -> action
    Our agents expect: (obs, hidden, mask) -> (action, hidden)
    """
    hidden_state = [None]  # Mutable container for hidden state
    
    def wrapped(obs, state, mask):
        action, new_hidden = tactician(obs, hidden_state[0], mask)
        hidden_state[0] = new_hidden
        return action
    return wrapped


# =============================================================================
# Automatic Episode Runner
# =============================================================================

def run_automatic_episodes(
    controller: GameController,
    drafter,
    tactician,
    num_episodes: int = 1,
    initialize: bool = True,
) -> list:
    """
    Run automatic episodes with the given agents.
    
    Args:
        controller: GameController instance
        drafter: Drafter agent
        tactician: Tactician agent  
        num_episodes: Number of episodes to run
        initialize: Whether to auto-initialize to draft screen
        
    Returns:
        List of EpisodeResult objects
    """
    results = []
    
    # Wrap agents for controller interface
    drafter_fn = wrap_drafter_for_controller(drafter)
    tactician_fn = wrap_tactician_for_controller(tactician)
    
    for i in range(num_episodes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Episode {i + 1}/{num_episodes}")
        logger.info(f"{'='*60}")
        
        # Initialize if needed
        if initialize and controller.state != GameState.DRAFT_SCREEN:
            logger.info("Initializing to draft screen...")
            if not controller.initialize_to_draft():
                logger.error("Failed to initialize")
                continue
        
        # Run episode
        result = controller.run_episode(drafter_fn, tactician_fn)
        results.append(result)
        
        # Log result
        logger.info(f"\nEpisode {i + 1} Result:")
        logger.info(f"  Success: {result.success}")
        logger.info(f"  Win Streak: {result.win_streak}")
        logger.info(f"  Battles Won: {result.battles_won}")
        logger.info(f"  Total Turns: {result.total_turns}")
        logger.info(f"  Duration: {result.duration_seconds:.1f}s")
        
        if result.error:
            logger.error(f"  Error: {result.error}")
        
        # Brief pause between episodes
        if i < num_episodes - 1:
            time.sleep(1.0)
    
    # Summary
    if len(results) > 1:
        successful = [r for r in results if r.success]
        if successful:
            avg_streak = sum(r.win_streak for r in successful) / len(successful)
            max_streak = max(r.win_streak for r in successful)
            logger.info(f"\n{'='*60}")
            logger.info("SUMMARY")
            logger.info(f"{'='*60}")
            logger.info(f"Episodes: {len(results)}, Successful: {len(successful)}")
            logger.info(f"Average Streak: {avg_streak:.1f}")
            logger.info(f"Max Streak: {max_streak}")
    
    return results


# =============================================================================
# Interactive Mode
# =============================================================================

def run_interactive_mode(controller: GameController):
    """
    Run in fully interactive mode with command prompt.
    
    Provides commands for:
    - Initialization (step-by-step or full)
    - Phase-level stepping
    - Turn-level stepping
    - State inspection
    """
    print("\n" + "="*60)
    print("BATTLE FACTORY - Interactive Mode")
    print("="*60)
    print("\nInitialization Commands:")
    print("  init          - Full init: title -> draft (all 3 steps)")
    print("  step1         - Step 1: Load title screen (A x2)")
    print("  step2         - Step 2: Talk to NPC (B x3)")
    print("  step3         - Step 3: Init Battle Factory (A5, Down, A4, Wait, A, B10)")
    print("  detect        - Detect current game state")
    print("")
    print("Phase Commands:")
    print("  draft [r/i]   - Run draft phase (r=random, i=interactive)")
    print("  battle [r/i]  - Run full battle (r=random, i=interactive)")
    print("  turn [0-5]    - Execute single battle turn")
    print("  swap [r/i]    - Run swap phase")
    print("")
    print("State Commands:")
    print("  state         - Show current state")
    print("  obs           - Show current observation")
    print("  valid         - Show valid actions")
    print("")
    print("Button Commands:")
    print("  a/b/up/down/left/right/start - Press button")
    print("  wait [frames] - Wait N frames")
    print("")
    print("Episode Commands:")
    print("  run [n]       - Run N episodes with random agents")
    print("  q             - Quit")
    print("")
    
    # Create agents for interactive use
    random_drafter, random_tactician = create_random_agents(verbose=True)
    interactive_drafter, interactive_tactician = create_interactive_agents()
    
    while True:
        try:
            # Show current state in prompt
            state_name = controller.state.name if controller.is_connected else "DISCONNECTED"
            cmd = input(f"[{state_name}]> ").strip().lower()
            
            if not cmd:
                continue
            
            parts = cmd.split()
            action = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            # === Quit ===
            if action == 'q':
                break
            
            # === Initialization Steps ===
            elif action == 'init':
                print("Full initialization to draft screen...")
                success = controller.initialize_to_draft()
                print(f"Result: {'Success' if success else 'Failed'}")
            
            elif action == 'step1':
                print("Step 1: Loading title screen (A x2)...")
                from src.navigation import NavigationSequence
                nav = NavigationSequence(controller)
                nav.load_title_screen()
                print("✓ Step 1 complete")
            
            elif action == 'step2':
                print("Step 2: Talk to NPC (B x3)...")
                from src.navigation import NavigationSequence
                nav = NavigationSequence(controller)
                nav.talk_to_npc()
                print("✓ Step 2 complete")
            
            elif action == 'step3':
                print("Step 3: Init Battle Factory (A5, Down, A4, Wait, A, B10)...")
                from src.navigation import NavigationSequence
                nav = NavigationSequence(controller)
                nav.init_battle_factory()
                controller._state = GameState.DRAFT_SCREEN
                print("✓ Step 3 complete - should be at draft screen")
            
            elif action == 'detect':
                state = controller._detect_current_state()
                print(f"Detected state: {state.name}")
            
            # === Phase Steps ===
            elif action == 'draft':
                agent = interactive_drafter if 'i' in args else random_drafter
                drafter_fn = wrap_drafter_for_controller(agent)
                result = controller.step_draft(drafter_fn)
                print(f"Draft result: {result.success}, next: {result.next_state.name}")
                if result.data:
                    print(f"  Data: {result.data}")
            
            elif action == 'battle':
                agent = interactive_tactician if 'i' in args else random_tactician
                tactician_fn = wrap_tactician_for_controller(agent)
                result = controller.step_battle(tactician_fn)
                print(f"Battle result: {result.success}, next: {result.next_state.name}")
                if result.data:
                    print(f"  Data: {result.data}")
            
            elif action == 'swap':
                agent = interactive_drafter if 'i' in args else random_drafter
                drafter_fn = wrap_drafter_for_controller(agent)
                result = controller.step_swap(drafter_fn)
                print(f"Swap result: {result.success}, next: {result.next_state.name}")
            
            elif action == 'turn':
                if not args:
                    # Show options and prompt
                    mask = controller.get_valid_actions()
                    print("Valid actions:")
                    actions = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
                    for i, name in enumerate(actions):
                        valid = "✓" if mask[i] > 0 else "✗"
                        print(f"  [{i}] {name} {valid}")
                    action_num = int(input("Action: "))
                else:
                    action_num = int(args[0])
                
                result = controller.step_turn(action_num)
                print(f"Turn result: reward={result.reward:.2f}, ended={result.battle_ended}")
                if result.data:
                    print(f"  Data: {result.data}")
            
            # === State Inspection ===
            elif action == 'state':
                print(f"State: {controller.state.name}")
                print(f"Connected: {controller.is_connected}")
                print(f"Win Streak: {controller.win_streak}")
                print(f"Current Battle: {controller.current_battle}")
                print(f"Current Turn: {controller.current_turn}")
            
            elif action == 'obs':
                obs = controller.get_observation()
                print("Observation:")
                for key, value in obs.items():
                    print(f"  {key}: {value}")
            
            elif action == 'valid':
                mask = controller.get_valid_actions()
                actions = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
                print("Valid actions:")
                for i, name in enumerate(actions):
                    valid = "✓" if mask[i] > 0 else "✗"
                    print(f"  [{i}] {name} {valid}")
            
            # === Button Presses ===
            elif action == 'a':
                controller.press_a()
                print("Pressed A")
            elif action == 'b':
                controller.press_b()
                print("Pressed B")
            elif action == 'up':
                controller.press_up()
                print("Pressed Up")
            elif action == 'down':
                controller.press_down()
                print("Pressed Down")
            elif action == 'left':
                controller.press_left()
                print("Pressed Left")
            elif action == 'right':
                controller.press_right()
                print("Pressed Right")
            elif action == 'start':
                controller.press_start()
                print("Pressed Start")
            elif action == 'wait':
                frames = int(args[0]) if args else 60
                controller.wait(frames)
                print(f"Waited {frames} frames")
            
            # === Full Episodes ===
            elif action == 'run':
                n = int(args[0]) if args else 1
                run_automatic_episodes(
                    controller,
                    random_drafter,
                    random_tactician,
                    num_episodes=n,
                    initialize=False,  # Already initialized
                )
            
            else:
                print(f"Unknown command: {action}")
                print("Type 'q' to quit")
        
        except KeyboardInterrupt:
            print("\nUse 'q' to quit")
        except Exception as e:
            logger.error(f"Error: {e}")
            import traceback
            traceback.print_exc()


# =============================================================================
# Step Mode (Phase-by-phase with confirmations)
# =============================================================================

def run_step_mode(controller: GameController):
    """
    Run with step-by-step confirmation at each phase.
    
    Useful for debugging and understanding the game flow.
    """
    print("\n" + "="*60)
    print("BATTLE FACTORY - Step-by-Step Mode")
    print("="*60)
    print("\nThis mode will walk through each phase with confirmations.")
    print("Press Enter to proceed at each step, or 'q' to quit.\n")
    
    random_drafter, random_tactician = create_random_agents(verbose=True)
    
    def confirm(prompt: str) -> bool:
        response = input(f"{prompt} [Enter/q]: ").strip().lower()
        return response != 'q'
    
    # Initialize
    if not confirm("Ready to initialize to draft screen?"):
        return
    
    print("\nInitializing...")
    if not controller.initialize_to_draft():
        print("Failed to initialize!")
        return
    print("✓ At draft screen")
    
    # Draft
    if not confirm("\nReady to run draft phase (random)?"):
        return
    
    drafter_fn = wrap_drafter_for_controller(random_drafter)
    result = controller.step_draft(drafter_fn)
    print(f"Draft complete: {result.data}")
    
    # Battle loop
    battle_num = 0
    while controller.state != GameState.RUN_COMPLETE:
        battle_num += 1
        
        if not confirm(f"\nReady for battle {battle_num}?"):
            break
        
        tactician_fn = wrap_tactician_for_controller(random_tactician)
        result = controller.step_battle(tactician_fn)
        print(f"Battle complete: {result.data}")
        
        # Swap if applicable
        if controller.state == GameState.SWAP_SCREEN:
            if not confirm("\nSwap screen - ready to make swap decision?"):
                break
            
            result = controller.step_swap(drafter_fn)
            print(f"Swap complete: {result.data}")
    
    print(f"\n{'='*60}")
    print(f"Run complete! Final streak: {controller.win_streak}")
    print(f"{'='*60}")


# =============================================================================
# Connection Test
# =============================================================================

def test_connection(controller: GameController) -> bool:
    """
    Test connection to emulator.
    """
    print("Testing connection to emulator...")
    
    try:
        # Basic commands
        tests = [
            ("PING", "PONG"),
            ("GET_FRAME", None),
        ]
        
        for cmd, expected in tests:
            response = controller.backend._send_command(cmd)
            if expected and response != expected:
                print(f"  {cmd}: FAIL (got '{response}', expected '{expected}')")
                return False
            print(f"  {cmd}: {response} ✓")
        
        # Memory commands
        print("\nTesting memory commands...")
        
        waiting = controller.backend._send_command("IS_WAITING_INPUT")
        print(f"  IS_WAITING_INPUT: {waiting}")
        
        outcome = controller.backend._send_command("GET_BATTLE_OUTCOME")
        print(f"  GET_BATTLE_OUTCOME: {outcome}")
        
        # Try reading rental mons
        rentals = controller.backend.memory.read_rental_mons()
        print(f"  Rental mons found: {len(rentals)}")
        
        # Try reading battle state
        battle_mons = controller.backend.memory.read_battle_mons()
        print(f"  Battle mons found: {len(battle_mons)}")
        
        print("\n✓ Connection test passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Connection test failed: {e}")
        return False


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Battle Factory Runner - Run game loop with pluggable agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--episodes", "-n",
        type=int,
        default=1,
        help="Number of episodes to run (default: 1)",
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for agents",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode with command prompt",
    )
    parser.add_argument(
        "--step-mode",
        action="store_true",
        help="Run with step-by-step confirmation",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Only test connection, don't run episodes",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Emulator host (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7777,
        help="Emulator port (default: 7777)",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Skip auto-initialization (assume already at draft)",
    )
    
    args = parser.parse_args()
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create controller
    controller = GameController(verbose=args.verbose)
    
    # Connect
    if not controller.connect(args.host, args.port):
        print("\nFailed to connect to emulator!")
        print("Make sure:")
        print("  1. mGBA is running with Pokemon Emerald loaded")
        print("  2. connector.lua is loaded (Tools -> Scripting -> Load)")
        print("  3. The game is NOT paused")
        sys.exit(1)
    
    try:
        # Test connection mode
        if args.test_connection:
            success = test_connection(controller)
            sys.exit(0 if success else 1)
        
        # Interactive mode
        if args.interactive:
            run_interactive_mode(controller)
        
        # Step mode
        elif args.step_mode:
            run_step_mode(controller)
        
        # Automatic episodes
        else:
            # Create agents
            drafter, tactician = create_random_agents(
                seed=args.seed,
                verbose=args.verbose,
            )
            
            run_automatic_episodes(
                controller,
                drafter,
                tactician,
                num_episodes=args.episodes,
                initialize=not args.no_init,
            )
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
