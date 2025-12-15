#!/usr/bin/env python3
"""
Battle Factory Episode Runner - Flexible episode pipeline with new architecture.

This script provides a comprehensive, step-by-step episode runner that uses
the new modular controller architecture. It supports:

1. Full automatic episodes (random/trained agents)
2. Interactive debugging mode with step control
3. Phase-level stepping (draft → battle → swap)
4. Turn-level stepping (individual actions)
5. State inspection and memory debugging
6. Rich terminal output

Prerequisites:
1. mGBA running with Pokemon Emerald ROM loaded
2. connector.lua script loaded (Tools -> Scripting -> Load)
3. Game at save file/title screen

Usage:
    # Full automatic episode with random agents
    python scripts/run_episode.py
    
    # Interactive step-by-step mode
    python scripts/run_episode.py --interactive
    
    # Debug mode (verbose + step-by-step)
    python scripts/run_episode.py --debug
    
    # Multiple episodes with stats
    python scripts/run_episode.py -n 10 --stats
    
    # Connection test only
    python scripts/run_episode.py --test
"""

from __future__ import annotations

import sys
import os
import argparse
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum, auto

import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.controller import (
    TrainingController,
    PhaseResult,
    TurnResult,
    EpisodeResult,
    Button,
)
from src.core.enums import GamePhase, BattleOutcome
from src.config import config


# =============================================================================
# Logging Setup
# =============================================================================

def setup_logging(verbose: bool = False, debug: bool = False) -> logging.Logger:
    """Configure logging with rich output."""
    level = logging.DEBUG if debug else (logging.INFO if verbose else logging.WARNING)
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S',
    )
    
    return logging.getLogger("EpisodeRunner")


# =============================================================================
# Agent Factories
# =============================================================================

class RandomDrafter:
    """Simple random drafter agent."""
    
    def __init__(self, seed: Optional[int] = None, verbose: bool = False):
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        if phase == GamePhase.DRAFT_SCREEN:
            # Select 3 random Pokemon from 6
            choices = self.rng.choice(6, size=3, replace=False)
            if self.verbose:
                print(f"  🎲 Random draft: selecting indices {list(choices)}")
            return choices
        elif phase == GamePhase.SWAP_SCREEN:
            # 30% chance to swap
            action = self.rng.choice([0, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.1])
            if self.verbose:
                swap_str = "keep team" if action == 0 else f"swap slot {action}"
                print(f"  🎲 Random swap: {swap_str}")
            return np.array([action])
        return np.array([0])


class RandomTactician:
    """Simple random tactician agent with action masking."""
    
    def __init__(self, seed: Optional[int] = None, verbose: bool = False):
        self.rng = np.random.default_rng(seed)
        self.verbose = verbose
    
    def __call__(
        self, 
        obs: np.ndarray, 
        phase: GamePhase, 
        mask: np.ndarray
    ) -> int:
        valid_actions = np.where(mask > 0)[0]
        if len(valid_actions) == 0:
            return 0
        
        action = int(self.rng.choice(valid_actions))
        
        if self.verbose:
            action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
            print(f"  🎲 Random action: {action_names[action]}")
        
        return action


def create_random_agents(
    seed: Optional[int] = None, 
    verbose: bool = False
) -> tuple[RandomDrafter, RandomTactician]:
    """Create random agent pair."""
    return RandomDrafter(seed, verbose), RandomTactician(seed, verbose)


# =============================================================================
# Statistics Tracker
# =============================================================================

@dataclass
class RunStatistics:
    """Aggregate statistics across multiple episodes."""
    episodes_run: int = 0
    episodes_success: int = 0
    total_battles_won: int = 0
    total_battles_lost: int = 0
    total_turns: int = 0
    total_duration: float = 0.0
    win_streaks: List[int] = field(default_factory=list)
    
    def add_episode(self, result: EpisodeResult) -> None:
        """Record an episode result."""
        self.episodes_run += 1
        if result.success:
            self.episodes_success += 1
        self.total_battles_won += result.battles_won
        self.total_battles_lost += result.battles_lost
        self.total_turns += result.total_turns
        self.total_duration += result.duration_seconds
        self.win_streaks.append(result.win_streak)
    
    def summary(self) -> str:
        """Generate summary string."""
        if self.episodes_run == 0:
            return "No episodes run"
        
        avg_streak = sum(self.win_streaks) / len(self.win_streaks)
        max_streak = max(self.win_streaks) if self.win_streaks else 0
        avg_duration = self.total_duration / self.episodes_run
        
        lines = [
            "=" * 60,
            "EPISODE STATISTICS",
            "=" * 60,
            f"Episodes: {self.episodes_run} (success: {self.episodes_success})",
            f"Win Streaks: avg={avg_streak:.1f}, max={max_streak}, all={self.win_streaks}",
            f"Battles: {self.total_battles_won} won, {self.total_battles_lost} lost",
            f"Total Turns: {self.total_turns}",
            f"Duration: {self.total_duration:.1f}s total, {avg_duration:.1f}s/episode",
            "=" * 60,
        ]
        return "\n".join(lines)


# =============================================================================
# Episode Runner Class
# =============================================================================

class EpisodeRunner:
    """
    Flexible episode runner with multiple execution modes.
    
    Supports:
    - Full automatic episodes
    - Step-by-step interactive mode
    - Phase-level debugging
    - Turn-level inspection
    """
    
    def __init__(
        self,
        controller: Optional[TrainingController] = None,
        verbose: bool = False,
        debug: bool = False,
    ):
        """
        Initialize episode runner.
        
        Args:
            controller: TrainingController instance (creates new if None)
            verbose: Enable verbose output
            debug: Enable debug mode (extra verbose + step confirmations)
        """
        self.controller = controller or TrainingController(verbose=verbose)
        self.verbose = verbose
        self.debug = debug
        self.logger = logging.getLogger("EpisodeRunner")
        self.stats = RunStatistics()
    
    # =========================================================================
    # Connection
    # =========================================================================
    
    def connect(self, host: str = None, port: int = None) -> bool:
        """Connect to emulator."""
        host = host or config.network.host
        port = port or config.network.port
        
        print(f"\n🔌 Connecting to mGBA at {host}:{port}...")
        
        if not self.controller.connect(host, port):
            print("❌ Connection failed!")
            print("   Make sure:")
            print("   1. mGBA is running with Pokemon Emerald loaded")
            print("   2. connector.lua is loaded (Tools -> Scripting -> Load)")
            print("   3. The game is NOT paused")
            return False
        
        print("✅ Connected successfully")
        return True
    
    def disconnect(self) -> None:
        """Disconnect from emulator."""
        self.controller.disconnect()
        print("🔌 Disconnected")
    
    def test_connection(self) -> bool:
        """Test connection with basic commands."""
        print("\n🧪 Testing connection...")
        
        try:
            backend = self.controller.backend
            
            # Ping test
            if not backend.ping():
                print("  ❌ PING failed")
                return False
            print("  ✅ PING: PONG")
            
            # Frame count
            response = backend._send_command("GET_FRAME")
            print(f"  ✅ Frame count: {response}")
            
            # Input waiting
            waiting = backend.is_waiting_for_input()
            print(f"  ✅ Waiting for input: {waiting}")
            
            # Battle outcome
            outcome = backend.get_battle_outcome()
            print(f"  ✅ Battle outcome: {outcome.name}")
            
            # Rental mons
            rentals = backend.memory.read_rental_mons()
            print(f"  ✅ Rental mons: {len(rentals)} found")
            
            # Battle mons
            battle_mons = backend.memory.read_battle_mons()
            print(f"  ✅ Battle mons: {len(battle_mons)} found")
            
            print("\n✅ All connection tests passed!")
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            return False
    
    # =========================================================================
    # Automatic Episode Execution
    # =========================================================================
    
    def run_episode(
        self,
        drafter: Optional[Callable] = None,
        tactician: Optional[Callable] = None,
        initialize: bool = True,
    ) -> EpisodeResult:
        """
        Run a complete episode automatically.
        
        Args:
            drafter: Drafter agent callable
            tactician: Tactician agent callable
            initialize: Whether to navigate to draft screen first
            
        Returns:
            EpisodeResult with statistics
        """
        print("\n" + "=" * 60)
        print("🎮 STARTING EPISODE")
        print("=" * 60)
        
        # Initialize if needed
        if initialize:
            print("\n📍 Initializing to draft screen...")
            if not self.controller.initialize_to_draft():
                return EpisodeResult(
                    success=False,
                    win_streak=0,
                    battles_won=0,
                    battles_lost=0,
                    total_turns=0,
                    duration_seconds=0,
                    error="Failed to initialize"
                )
        
        # Run the episode using controller
        result = self.controller.run_episode(drafter, tactician)
        
        # Record stats
        self.stats.add_episode(result)
        
        # Print result
        print(f"\n{'=' * 60}")
        print(f"📊 EPISODE COMPLETE")
        print(f"   Win Streak: {result.win_streak}")
        print(f"   Battles: {result.battles_won} won, {result.battles_lost} lost")
        print(f"   Total Turns: {result.total_turns}")
        print(f"   Duration: {result.duration_seconds:.1f}s")
        if result.error:
            print(f"   ⚠️  Error: {result.error}")
        print(f"{'=' * 60}")
        
        return result
    
    def run_multiple_episodes(
        self,
        num_episodes: int,
        drafter: Optional[Callable] = None,
        tactician: Optional[Callable] = None,
        initialize: bool = True,
        delay_between: float = 1.0,
    ) -> List[EpisodeResult]:
        """
        Run multiple episodes and collect statistics.
        
        Args:
            num_episodes: Number of episodes to run
            drafter: Drafter agent
            tactician: Tactician agent
            initialize: Whether to initialize each episode
            delay_between: Delay between episodes in seconds
            
        Returns:
            List of EpisodeResults
        """
        results = []
        
        for i in range(num_episodes):
            print(f"\n{'#' * 60}")
            print(f"# Episode {i + 1} / {num_episodes}")
            print(f"{'#' * 60}")
            
            result = self.run_episode(drafter, tactician, initialize)
            results.append(result)
            
            if i < num_episodes - 1:
                print(f"\n⏳ Waiting {delay_between}s before next episode...")
                time.sleep(delay_between)
        
        # Print summary
        print(f"\n{self.stats.summary()}")
        
        return results
    
    # =========================================================================
    # Interactive Mode
    # =========================================================================
    
    def run_interactive(self) -> None:
        """
        Run in interactive mode with command prompt.
        
        Provides full control over the game with commands for:
        - Initialization steps
        - Phase execution
        - Turn execution
        - State inspection
        - Button presses
        """
        print("\n" + "=" * 60)
        print("🎮 BATTLE FACTORY - Interactive Mode")
        print("=" * 60)
        
        self._print_help()
        
        # Create default agents
        drafter, tactician = create_random_agents(verbose=True)
        
        while True:
            try:
                # Show state in prompt
                phase_name = self.controller.phase.name
                streak = self.controller.run_stats.win_streak
                prompt = f"[{phase_name}|streak={streak}]> "
                
                cmd = input(prompt).strip().lower()
                if not cmd:
                    continue
                
                parts = cmd.split()
                action = parts[0]
                args = parts[1:] if len(parts) > 1 else []
                
                # Process command
                if action in ('q', 'quit', 'exit'):
                    break
                elif action == 'help':
                    self._print_help()
                elif action == 'init':
                    self._cmd_init()
                elif action == 'step1':
                    self._cmd_step1()
                elif action == 'step2':
                    self._cmd_step2()
                elif action == 'step3':
                    self._cmd_step3()
                elif action == 'detect':
                    self._cmd_detect()
                elif action == 'draft':
                    self._cmd_draft(drafter, 'i' in args)
                elif action == 'battle':
                    self._cmd_battle(tactician, 'i' in args)
                elif action == 'turn':
                    self._cmd_turn(args)
                elif action == 'swap':
                    self._cmd_swap(drafter, 'i' in args)
                elif action == 'run':
                    n = int(args[0]) if args else 1
                    self.run_multiple_episodes(n, drafter, tactician, initialize=False)
                elif action == 'state':
                    self._cmd_state()
                elif action == 'obs':
                    self._cmd_obs()
                elif action == 'valid':
                    self._cmd_valid()
                elif action in ('a', 'b', 'up', 'down', 'left', 'right', 'start'):
                    self._cmd_button(action)
                elif action == 'wait':
                    frames = int(args[0]) if args else 60
                    self._cmd_wait(frames)
                elif action == 'test':
                    self.test_connection()
                else:
                    print(f"Unknown command: {action}. Type 'help' for commands.")
            
            except KeyboardInterrupt:
                print("\n(Use 'q' to quit)")
            except Exception as e:
                print(f"Error: {e}")
                import traceback
                traceback.print_exc()
    
    def _print_help(self) -> None:
        """Print interactive mode help."""
        print("""
📋 COMMANDS:

Initialization:
  init          - Full init: title → draft
  step1         - Load save (A x2)
  step2         - Dismiss NPC dialog (B x3)
  step3         - Start challenge (menu navigation)
  detect        - Detect current game state

Phase Execution:
  draft [i]     - Run draft (i=interactive)
  battle [i]    - Run full battle (i=interactive)
  swap [i]      - Run swap phase (i=interactive)
  turn [0-5]    - Execute single turn action

Episode:
  run [n]       - Run N episodes with random agents

Inspection:
  state         - Show current state
  obs           - Show current observation
  valid         - Show valid actions

Buttons:
  a/b/up/down/left/right/start - Press button
  wait [frames] - Wait N frames (~60fps)

Other:
  test          - Test connection
  help          - Show this help
  q             - Quit
""")
    
    def _cmd_init(self) -> None:
        """Full initialization."""
        print("📍 Initializing to draft screen...")
        success = self.controller.initialize_to_draft()
        print(f"{'✅ Success' if success else '❌ Failed'}")
    
    def _cmd_step1(self) -> None:
        """Step 1: Load title screen."""
        print("📍 Step 1: Loading save...")
        from src.controller.input import TITLE_TO_CONTINUE
        self.controller.input.execute_sequence(TITLE_TO_CONTINUE)
        print("✅ Done")
    
    def _cmd_step2(self) -> None:
        """Step 2: Talk to NPC."""
        print("📍 Step 2: Dismissing NPC dialog...")
        from src.controller.input import DISMISS_DIALOG
        self.controller.input.execute_sequence(DISMISS_DIALOG)
        print("✅ Done")
    
    def _cmd_step3(self) -> None:
        """Step 3: Init Battle Factory."""
        print("📍 Step 3: Initializing challenge...")
        from src.controller.input import INIT_FACTORY_CHALLENGE
        self.controller.input.execute_sequence(INIT_FACTORY_CHALLENGE)
        self.controller.transition_to(GamePhase.DRAFT_SCREEN, force=True)
        print("✅ Done - should be at draft screen")
    
    def _cmd_detect(self) -> None:
        """Detect current state."""
        phase = self.controller.detect_phase()
        print(f"🔍 Detected phase: {phase.name}")
        self.controller.transition_to(phase, force=True)
    
    def _cmd_draft(self, drafter: Callable, interactive: bool = False) -> None:
        """Execute draft phase."""
        if interactive:
            print("Interactive draft not implemented - using random")
        result = self.controller.step_draft(drafter)
        print(f"Draft: {'✅ Success' if result.success else '❌ Failed'}")
        if result.data:
            print(f"  Data: {result.data}")
        print(f"  Next phase: {result.next_phase.name}")
    
    def _cmd_battle(self, tactician: Callable, interactive: bool = False) -> None:
        """Execute battle phase."""
        if interactive:
            print("Interactive battle not implemented - using random")
        result = self.controller.step_battle(tactician)
        print(f"Battle: {'✅ Success' if result.success else '❌ Failed'}")
        if result.data:
            print(f"  Outcome: {result.data.get('outcome', 'unknown')}")
            print(f"  Turns: {result.data.get('turns', 0)}")
            print(f"  Reward: {result.data.get('total_reward', 0):.2f}")
        print(f"  Next phase: {result.next_phase.name}")
    
    def _cmd_turn(self, args: List[str]) -> None:
        """Execute single turn."""
        if not args:
            # Show options
            mask = self.controller.get_action_mask()
            print("Valid actions:")
            action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
            for i, name in enumerate(action_names):
                valid = "✅" if mask[i] > 0 else "❌"
                print(f"  [{i}] {name} {valid}")
            try:
                action = int(input("Action: "))
            except ValueError:
                print("Invalid action")
                return
        else:
            action = int(args[0])
        
        result = self.controller.step_turn(action)
        print(f"Turn: {'✅' if result.success else '❌'}")
        print(f"  Action: {result.action}, Reward: {result.reward:.2f}")
        print(f"  Battle ended: {result.battle_ended}")
        if result.data:
            print(f"  Damage dealt: {result.data.get('damage_dealt', 0):.1f}%")
            print(f"  Damage taken: {result.data.get('damage_taken', 0)}")
    
    def _cmd_swap(self, drafter: Callable, interactive: bool = False) -> None:
        """Execute swap phase."""
        if interactive:
            print("Interactive swap not implemented - using random")
        result = self.controller.step_swap(drafter)
        print(f"Swap: {'✅ Success' if result.success else '❌ Failed'}")
        if result.data:
            print(f"  Swapped: {result.data.get('swapped', False)}")
        print(f"  Next phase: {result.next_phase.name}")
    
    def _cmd_state(self) -> None:
        """Show current state."""
        ctrl = self.controller
        print(f"Phase: {ctrl.phase.name}")
        print(f"Connected: {ctrl.is_connected}")
        print(f"Win Streak: {ctrl.run_stats.win_streak}")
        print(f"Current Battle: {ctrl.run_stats.current_battle}")
        print(f"Battles Won: {ctrl.run_stats.battles_won}")
        print(f"Battles Lost: {ctrl.run_stats.battles_lost}")
        print(f"Total Turns: {ctrl.run_stats.total_turns}")
    
    def _cmd_obs(self) -> None:
        """Show current observation."""
        phase = self.controller.phase
        
        if phase == GamePhase.DRAFT_SCREEN:
            obs = self.controller.get_draft_observation()
            print(f"Draft observation ({len(obs)} dims):")
            print(f"  {obs[:10]}...")
        elif phase.is_battle_phase:
            obs = self.controller.get_battle_observation()
            print(f"Battle observation ({len(obs)} dims):")
            print(f"  {obs[:10]}...")
        elif phase == GamePhase.SWAP_SCREEN:
            obs = self.controller.get_swap_observation()
            print(f"Swap observation ({len(obs)} dims):")
            print(f"  {obs[:10]}...")
        else:
            print(f"No observation available in phase: {phase.name}")
    
    def _cmd_valid(self) -> None:
        """Show valid actions."""
        mask = self.controller.get_action_mask()
        action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
        print("Valid actions:")
        for i, name in enumerate(action_names):
            valid = "✅" if mask[i] > 0 else "❌"
            print(f"  [{i}] {name} {valid}")
    
    def _cmd_button(self, button: str) -> None:
        """Press a button."""
        button_map = {
            'a': Button.A,
            'b': Button.B,
            'up': Button.UP,
            'down': Button.DOWN,
            'left': Button.LEFT,
            'right': Button.RIGHT,
            'start': Button.START,
        }
        btn = button_map.get(button)
        if btn:
            self.controller.input.press(btn)
            print(f"🎮 Pressed {button.upper()}")
    
    def _cmd_wait(self, frames: int) -> None:
        """Wait for frames."""
        self.controller.input.wait_frames(frames)
        print(f"⏳ Waited {frames} frames")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Battle Factory Episode Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "-n", "--episodes",
        type=int,
        default=1,
        help="Number of episodes to run (default: 1)",
    )
    parser.add_argument(
        "-s", "--seed",
        type=int,
        default=None,
        help="Random seed for agents",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "-i", "--interactive",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (very verbose)",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Only test connection",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show detailed statistics after run",
    )
    parser.add_argument(
        "--no-init",
        action="store_true",
        help="Skip initialization (assume already at draft)",
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
        "--speed",
        type=str,
        choices=["normal", "fast", "turbo", "instant", "zero"],
        default="normal",
        help="Input timing mode: normal, fast, turbo, instant, or zero (default: normal). 'zero' = instant press/release, fastest.",
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
    
    # Setup logging
    logger = setup_logging(args.verbose, args.debug)
    
    # Create runner
    runner = EpisodeRunner(verbose=args.verbose, debug=args.debug)
    
    # Connect
    if not runner.connect(args.host, args.port):
        sys.exit(1)
    
    try:
        # Test mode
        if args.test:
            success = runner.test_connection()
            sys.exit(0 if success else 1)
        
        # Interactive mode
        if args.interactive:
            runner.run_interactive()
        
        # Automatic mode
        else:
            drafter, tactician = create_random_agents(
                seed=args.seed,
                verbose=args.verbose,
            )
            
            if args.episodes > 1:
                runner.run_multiple_episodes(
                    args.episodes,
                    drafter,
                    tactician,
                    initialize=not args.no_init,
                )
            else:
                runner.run_episode(
                    drafter,
                    tactician,
                    initialize=not args.no_init,
                )
            
            if args.stats:
                print(f"\n{runner.stats.summary()}")
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        runner.disconnect()


if __name__ == "__main__":
    main()

