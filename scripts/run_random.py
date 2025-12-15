#!/usr/bin/env python3
"""
Battle Factory Runner - Execute game loop with pluggable agents.

This script provides multiple ways to run the Battle Factory:
1. Full automatic episodes with random/trained agents
2. Interactive mode with step-by-step control
3. Phase-level stepping (draft, battle, swap)
4. Turn-level stepping (individual battle turns)

Uses the new modular controller architecture for consistent behavior.

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

from __future__ import annotations

import sys
import os
import argparse
import logging
import time
from pathlib import Path
from typing import Optional, Callable, List

import numpy as np

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.controller import (
    TrainingController,
    PhaseResult,
    TurnResult,
    EpisodeResult,
    Button,
    TITLE_TO_CONTINUE,
    DISMISS_DIALOG,
    INIT_FACTORY_CHALLENGE,
)
from src.core.enums import GamePhase, BattleOutcome
from src.config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BattleFactoryRunner")


# =============================================================================
# Agent Implementations
# =============================================================================

class RandomDrafter:
    """Random drafter that selects Pokemon randomly."""
    
    def __init__(self, seed: Optional[int] = None, verbose: bool = False):
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        """Select action based on phase."""
        if phase == GamePhase.DRAFT_SCREEN:
            # Select 3 unique Pokemon from 6
            choices = self.rng.choice(6, size=3, replace=False)
            if self.verbose:
                print(f"  [Drafter] Selecting indices: {list(choices)}")
            return choices
        elif phase == GamePhase.SWAP_SCREEN:
            # 30% chance to swap, preferring not to
            action = self.rng.choice([0, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.1])
            if self.verbose:
                action_str = "keep team" if action == 0 else f"swap slot {action}"
                print(f"  [Drafter] Swap decision: {action_str}")
            return np.array([action])
        return np.array([0])


class RandomTactician:
    """Random tactician that selects valid moves randomly."""
    
    def __init__(self, seed: Optional[int] = None, verbose: bool = False):
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
    
    def __call__(
        self,
        obs: np.ndarray,
        phase: GamePhase,
        mask: np.ndarray
    ) -> int:
        """Select random valid action."""
        valid_actions = np.where(mask > 0)[0]
        if len(valid_actions) == 0:
            action = 0  # Default to first move
        else:
            action = int(self.rng.choice(valid_actions))
        
        if self.verbose:
            action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
            print(f"  [Tactician] Action: {action_names[action]}")
        
        return action


class InteractiveDrafter:
    """Interactive drafter that prompts user for input."""
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        if phase == GamePhase.DRAFT_SCREEN:
            print("\n=== DRAFT SELECTION ===")
            print("Select 3 Pokemon (indices 0-5)")
            selections = []
            for i in range(3):
                while True:
                    try:
                        idx = int(input(f"  Pokemon {i+1}: "))
                        if 0 <= idx <= 5 and idx not in selections:
                            selections.append(idx)
                            break
                        print("  Invalid or duplicate selection")
                    except ValueError:
                        print("  Enter a number 0-5")
            return np.array(selections)
        
        elif phase == GamePhase.SWAP_SCREEN:
            print("\n=== SWAP DECISION ===")
            print("0: Keep team, 1-3: Swap slot")
            while True:
                try:
                    action = int(input("  Decision: "))
                    if 0 <= action <= 3:
                        return np.array([action])
                    print("  Invalid choice")
                except ValueError:
                    print("  Enter a number 0-3")
        
        return np.array([0])


class InteractiveTactician:
    """Interactive tactician that prompts user for input."""
    
    def __call__(
        self,
        obs: np.ndarray,
        phase: GamePhase,
        mask: np.ndarray
    ) -> int:
        print("\n=== BATTLE TURN ===")
        action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
        
        print("Valid actions:")
        for i, name in enumerate(action_names):
            valid = "✓" if mask[i] > 0 else "✗"
            print(f"  [{i}] {name} {valid}")
        
        while True:
            try:
                action = int(input("  Action: "))
                if 0 <= action <= 5 and mask[action] > 0:
                    return action
                print("  Invalid or masked action")
            except ValueError:
                print("  Enter a number 0-5")


def create_random_agents(
    seed: Optional[int] = None,
    verbose: bool = False
) -> tuple[RandomDrafter, RandomTactician]:
    """Create random agent pair."""
    return RandomDrafter(seed, verbose), RandomTactician(seed, verbose)


def create_interactive_agents() -> tuple[InteractiveDrafter, InteractiveTactician]:
    """Create interactive agent pair."""
    return InteractiveDrafter(), InteractiveTactician()


# =============================================================================
# Episode Execution
# =============================================================================

def run_automatic_episodes(
    controller: TrainingController,
    drafter: Callable,
    tactician: Callable,
    num_episodes: int = 1,
    initialize: bool = True,
) -> List[EpisodeResult]:
    """
    Run automatic episodes with the given agents.
    
    Args:
        controller: TrainingController instance
        drafter: Drafter agent callable
        tactician: Tactician agent callable
        num_episodes: Number of episodes to run
        initialize: Whether to auto-initialize to draft screen
        
    Returns:
        List of EpisodeResult objects
    """
    results = []
    
    for i in range(num_episodes):
        logger.info(f"\n{'='*60}")
        logger.info(f"Episode {i + 1}/{num_episodes}")
        logger.info(f"{'='*60}")
        
        # Initialize if needed
        if initialize and controller.phase != GamePhase.DRAFT_SCREEN:
            logger.info("Initializing to draft screen...")
            if not controller.initialize_to_draft():
                logger.error("Failed to initialize")
                continue
        
        # Run episode
        result = controller.run_episode(drafter, tactician)
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

def run_interactive_mode(controller: TrainingController):
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
            phase_name = controller.phase.name if controller.is_connected else "DISCONNECTED"
            cmd = input(f"[{phase_name}]> ").strip().lower()
            
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
                controller.input.execute_sequence(TITLE_TO_CONTINUE)
                print("✓ Step 1 complete")
            
            elif action == 'step2':
                print("Step 2: Talk to NPC (B x3)...")
                controller.input.execute_sequence(DISMISS_DIALOG)
                print("✓ Step 2 complete")
            
            elif action == 'step3':
                print("Step 3: Init Battle Factory (A5, Down, A4, Wait, A, B10)...")
                controller.input.execute_sequence(INIT_FACTORY_CHALLENGE)
                controller.transition_to(GamePhase.DRAFT_SCREEN, force=True)
                print("✓ Step 3 complete - should be at draft screen")
            
            elif action == 'detect':
                phase = controller.detect_phase()
                print(f"Detected phase: {phase.name}")
                controller.transition_to(phase, force=True)
            
            # === Phase Steps ===
            elif action == 'draft':
                agent = interactive_drafter if 'i' in args else random_drafter
                result = controller.step_draft(agent)
                print(f"Draft result: {result.success}, next: {result.next_phase.name}")
                if result.data:
                    print(f"  Data: {result.data}")
            
            elif action == 'battle':
                agent = interactive_tactician if 'i' in args else random_tactician
                result = controller.step_battle(agent)
                print(f"Battle result: {result.success}, next: {result.next_phase.name}")
                if result.data:
                    print(f"  Data: {result.data}")
            
            elif action == 'swap':
                agent = interactive_drafter if 'i' in args else random_drafter
                result = controller.step_swap(agent)
                print(f"Swap result: {result.success}, next: {result.next_phase.name}")
            
            elif action == 'turn':
                if not args:
                    # Show options and prompt
                    mask = controller.get_action_mask()
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
                print(f"Phase: {controller.phase.name}")
                print(f"Connected: {controller.is_connected}")
                print(f"Win Streak: {controller.run_stats.win_streak}")
                print(f"Current Battle: {controller.run_stats.current_battle}")
                print(f"Total Turns: {controller.run_stats.total_turns}")
            
            elif action == 'obs':
                phase = controller.phase
                if phase == GamePhase.DRAFT_SCREEN:
                    obs = controller.get_draft_observation()
                    print(f"Draft observation ({len(obs)} dims): {obs[:10]}...")
                elif phase.is_battle_phase:
                    obs = controller.get_battle_observation()
                    print(f"Battle observation ({len(obs)} dims): {obs[:10]}...")
                else:
                    print(f"No observation available in phase: {phase.name}")
            
            elif action == 'valid':
                mask = controller.get_action_mask()
                actions = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
                print("Valid actions:")
                for i, name in enumerate(actions):
                    valid = "✓" if mask[i] > 0 else "✗"
                    print(f"  [{i}] {name} {valid}")
            
            # === Button Presses ===
            elif action == 'a':
                controller.input.press_a()
                print("Pressed A")
            elif action == 'b':
                controller.input.press_b()
                print("Pressed B")
            elif action == 'up':
                controller.input.press_up()
                print("Pressed Up")
            elif action == 'down':
                controller.input.press_down()
                print("Pressed Down")
            elif action == 'left':
                controller.input.press_left()
                print("Pressed Left")
            elif action == 'right':
                controller.input.press_right()
                print("Pressed Right")
            elif action == 'start':
                controller.input.press_start()
                print("Pressed Start")
            elif action == 'wait':
                frames = int(args[0]) if args else 60
                controller.input.wait_frames(frames)
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

def run_step_mode(controller: TrainingController):
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
    
    result = controller.step_draft(random_drafter)
    print(f"Draft complete: {result.data}")
    
    # Battle loop
    battle_num = 0
    while controller.phase != GamePhase.RUN_COMPLETE:
        battle_num += 1
        
        if not confirm(f"\nReady for battle {battle_num}?"):
            break
        
        result = controller.step_battle(random_tactician)
        print(f"Battle complete: {result.data}")
        
        # Swap if applicable
        if controller.phase == GamePhase.SWAP_SCREEN:
            if not confirm("\nSwap screen - ready to make swap decision?"):
                break
            
            result = controller.step_swap(random_drafter)
            print(f"Swap complete: {result.data}")
    
    print(f"\n{'='*60}")
    print(f"Run complete! Final streak: {controller.run_stats.win_streak}")
    print(f"{'='*60}")


# =============================================================================
# Connection Test
# =============================================================================

def test_connection(controller: TrainingController) -> bool:
    """
    Test connection to emulator.
    """
    print("Testing connection to emulator...")
    
    try:
        backend = controller.backend
        
        # Basic commands
        tests = [
            ("PING", "PONG"),
            ("GET_FRAME", None),
        ]
        
        for cmd, expected in tests:
            response = backend._send_command(cmd)
            if expected and response != expected:
                print(f"  {cmd}: FAIL (got '{response}', expected '{expected}')")
                return False
            print(f"  {cmd}: {response} ✓")
        
        # Memory commands
        print("\nTesting memory commands...")
        
        waiting = backend.is_waiting_for_input()
        print(f"  IS_WAITING_INPUT: {waiting}")
        
        outcome = backend.get_battle_outcome()
        print(f"  GET_BATTLE_OUTCOME: {outcome.name}")
        
        # Try reading rental mons
        rentals = backend.memory.read_rental_mons()
        print(f"  Rental mons found: {len(rentals)}")
        
        # Try reading battle state
        battle_mons = backend.memory.read_battle_mons()
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
        default=config.network.host,
        help=f"Emulator host (default: {config.network.host})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.network.port,
        help=f"Emulator port (default: {config.network.port})",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Skip auto-initialization (assume already at draft)",
    )
    parser.add_argument(
        "--speed",
        type=str,
        choices=["normal", "fast", "turbo", "instant", "zero"],
        default="zero",
        help="Input timing mode: normal, fast, turbo, instant, or zero (default: zero). 'zero' = instant press/release, fastest.",
    )
    parser.add_argument(
        "--hold-time",
        type=float,
        default=None,
        help="Custom button hold time in seconds (e.g., 0.01 for very fast)",
    )
    parser.add_argument(
        "--wait-time",
        type=float,
        default=None,
        help="Custom wait time after buttons in seconds (e.g., 0.02 for very fast)",
    )
    
    args = parser.parse_args()
    
    # Apply speed mode
    if args.speed != "normal":
        config.timing.set_speed_mode(args.speed)
        print(f"⚡ Speed mode: {args.speed}")
    
    # Apply custom timing if specified
    if args.hold_time is not None or args.wait_time is not None:
        config.timing.set_custom_timing(
            button_hold=args.hold_time,
            wait_short=args.wait_time,
        )
        print(f"⚡ Custom timing: hold={args.hold_time or config.timing.button_hold_time}s, wait={args.wait_time or config.timing.wait_short}s")
    
    # Set log level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create controller
    controller = TrainingController(verbose=args.verbose)
    
    # Connect
    print(f"\nConnecting to emulator at {args.host}:{args.port}...")
    if not controller.connect(args.host, args.port):
        print("\nFailed to connect to emulator!")
        print("Make sure:")
        print("  1. mGBA is running with Pokemon Emerald loaded")
        print("  2. connector.lua is loaded (Tools -> Scripting -> Load)")
        print("  3. The game is NOT paused")
        sys.exit(1)
    
    print("✓ Connected")
    
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
