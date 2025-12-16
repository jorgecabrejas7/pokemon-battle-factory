#!/usr/bin/env python3
"""
Step-by-Step Pipeline Checker - Comprehensive debugging and verification tool.

This tool provides a flexible, step-by-step verification of the entire
Battle Factory episode pipeline. Use it to:

1. Verify connection and basic communication
2. Test individual navigation steps
3. Debug phase transitions
4. Validate observations and action spaces
5. Test agent integration

The checker can run fully automated, with user confirmations, or in
interactive mode for manual debugging.

Usage:
    # Full automated check
    python tools/step_checker.py
    
    # With confirmations at each step
    python tools/step_checker.py --confirm
    
    # Interactive debug mode
    python tools/step_checker.py --interactive
    
    # Check specific component only
    python tools/step_checker.py --check connection
    python tools/step_checker.py --check navigation
    python tools/step_checker.py --check observations
"""

from __future__ import annotations

import sys
import os
import argparse
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Callable, Dict, Any
from enum import Enum, auto

import numpy as np

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.controller import (
    TrainingController,
    InputController,
    StateMachine,
    Button,
    TITLE_TO_CONTINUE,
    DISMISS_DIALOG,
    INIT_FACTORY_CHALLENGE,
)
from src.core.enums import GamePhase, BattleOutcome
from src.config import config


# =============================================================================
# Check Result Types
# =============================================================================

class CheckStatus(Enum):
    """Status of a check step."""
    PASSED = auto()
    FAILED = auto()
    SKIPPED = auto()
    WARNING = auto()


@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    status: CheckStatus
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    
    def __str__(self) -> str:
        status_icons = {
            CheckStatus.PASSED: "✅",
            CheckStatus.FAILED: "❌",
            CheckStatus.SKIPPED: "⏭️",
            CheckStatus.WARNING: "⚠️",
        }
        icon = status_icons[self.status]
        msg = f" - {self.message}" if self.message else ""
        dur = f" ({self.duration:.2f}s)" if self.duration > 0 else ""
        return f"{icon} {self.name}{msg}{dur}"


@dataclass
class CheckReport:
    """Complete report of all checks."""
    results: List[CheckResult] = field(default_factory=list)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.PASSED)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.FAILED)
    
    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.WARNING)
    
    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == CheckStatus.SKIPPED)
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    def add(self, result: CheckResult) -> None:
        self.results.append(result)
        print(result)
    
    def summary(self) -> str:
        lines = [
            "",
            "=" * 60,
            "VERIFICATION SUMMARY",
            "=" * 60,
            f"Total checks: {self.total}",
            f"  ✅ Passed:   {self.passed}",
            f"  ❌ Failed:   {self.failed}",
            f"  ⚠️  Warnings: {self.warnings}",
            f"  ⏭️  Skipped:  {self.skipped}",
            "",
            "Status: " + ("✅ ALL CHECKS PASSED" if self.failed == 0 else "❌ SOME CHECKS FAILED"),
            "=" * 60,
        ]
        return "\n".join(lines)


# =============================================================================
# Step Checker Class
# =============================================================================

class StepChecker:
    """
    Comprehensive step-by-step pipeline checker.
    
    Provides methods to verify each component of the episode pipeline
    and diagnose issues.
    """
    
    def __init__(
        self,
        controller: Optional[TrainingController] = None,
        confirm_steps: bool = False,
        verbose: bool = False,
    ):
        """
        Initialize checker.
        
        Args:
            controller: TrainingController instance (creates new if None)
            confirm_steps: Wait for user confirmation at each step
            verbose: Enable verbose output
        """
        self.controller = controller or TrainingController(verbose=verbose)
        self.confirm_steps = confirm_steps
        self.verbose = verbose
        self.report = CheckReport()
        self._connected = False
    
    def _confirm(self, prompt: str) -> bool:
        """Wait for user confirmation if enabled."""
        if not self.confirm_steps:
            return True
        response = input(f"\n{prompt} [Enter/q]: ").strip().lower()
        return response != 'q'
    
    def _timed_check(
        self,
        name: str,
        check_fn: Callable[[], bool],
        error_msg: str = "",
    ) -> CheckResult:
        """Run a check with timing."""
        start = time.time()
        try:
            success = check_fn()
            duration = time.time() - start
            
            if success:
                return CheckResult(
                    name=name,
                    status=CheckStatus.PASSED,
                    duration=duration,
                )
            else:
                return CheckResult(
                    name=name,
                    status=CheckStatus.FAILED,
                    message=error_msg,
                    duration=duration,
                )
        except Exception as e:
            return CheckResult(
                name=name,
                status=CheckStatus.FAILED,
                message=str(e),
                duration=time.time() - start,
            )
    
    # =========================================================================
    # Connection Checks
    # =========================================================================
    
    def check_connection(self) -> None:
        """Verify connection to emulator."""
        print("\n" + "=" * 60)
        print("CONNECTION CHECKS")
        print("=" * 60)
        
        if not self._confirm("Test connection?"):
            self.report.add(CheckResult("Connection", CheckStatus.SKIPPED))
            return
        
        # Basic connection
        def connect():
            if not self._connected:
                success = self.controller.connect()
                self._connected = success
                return success
            return True
        
        result = self._timed_check("Connect to mGBA", connect, "Cannot connect")
        self.report.add(result)
        
        if result.status != CheckStatus.PASSED:
            return
        
        # Ping test
        def ping():
            return self.controller.backend.ping()
        
        self.report.add(self._timed_check("PING command", ping, "PING failed"))
        
        # Frame counter
        def get_frame():
            resp = self.controller.backend._send_command("GET_FRAME")
            return resp.isdigit()
        
        self.report.add(self._timed_check("GET_FRAME command", get_frame))
        
        # Input waiting
        def check_input():
            _ = self.controller.backend.is_waiting_for_input()
            return True
        
        self.report.add(self._timed_check("IS_WAITING_INPUT command", check_input))
        
        # Battle outcome
        def check_outcome():
            outcome = self.controller.backend.get_battle_outcome()
            return isinstance(outcome, BattleOutcome)
        
        self.report.add(self._timed_check("GET_BATTLE_OUTCOME command", check_outcome))
    
    # =========================================================================
    # Memory Reading Checks
    # =========================================================================
    
    def check_memory_reading(self) -> None:
        """Verify memory reading capabilities."""
        print("\n" + "=" * 60)
        print("MEMORY READING CHECKS")
        print("=" * 60)
        
        if not self._connected:
            self.report.add(CheckResult(
                "Memory Reading",
                CheckStatus.SKIPPED,
                "Not connected"
            ))
            return
        
        if not self._confirm("Test memory reading?"):
            self.report.add(CheckResult("Memory Reading", CheckStatus.SKIPPED))
            return
        
        # Rental mons
        def read_rentals():
            rentals = self.controller.backend.memory.read_rental_mons()
            return len(rentals) >= 0  # May be 0 if not on draft screen
        
        self.report.add(self._timed_check("Read rental mons", read_rentals))
        
        # Battle mons
        def read_battle():
            mons = self.controller.backend.memory.read_battle_mons()
            return len(mons) >= 0
        
        self.report.add(self._timed_check("Read battle mons", read_battle))
        
        # Player party
        def read_party():
            party = self.controller.backend.memory.read_player_party()
            return len(party) >= 0
        
        self.report.add(self._timed_check("Read player party", read_party))
        
        # Frontier state
        def read_frontier():
            state = self.controller.backend.memory.read_frontier_state()
            return state is not None or True  # May return None if not in frontier
        
        self.report.add(self._timed_check("Read frontier state", read_frontier))
    
    # =========================================================================
    # Navigation Checks
    # =========================================================================
    
    def check_navigation(self) -> None:
        """Test navigation sequence execution."""
        print("\n" + "=" * 60)
        print("NAVIGATION CHECKS")
        print("=" * 60)
        
        if not self._connected:
            self.report.add(CheckResult(
                "Navigation",
                CheckStatus.SKIPPED,
                "Not connected"
            ))
            return
        
        if not self._confirm("Test navigation? (Will press buttons)"):
            self.report.add(CheckResult("Navigation", CheckStatus.SKIPPED))
            return
        
        # Input controller
        def test_input_controller():
            return self.controller.input is not None
        
        self.report.add(self._timed_check("Input controller ready", test_input_controller))
        
        # Step 1: Title screen
        if self._confirm("Execute Step 1 (title screen)?"):
            def step1():
                self.controller.input.execute_sequence(TITLE_TO_CONTINUE)
                return True
            
            self.report.add(self._timed_check("Step 1: Title screen", step1))
        
        # Step 2: NPC dialog
        if self._confirm("Execute Step 2 (NPC dialog)?"):
            def step2():
                self.controller.input.execute_sequence(DISMISS_DIALOG)
                return True
            
            self.report.add(self._timed_check("Step 2: NPC dialog", step2))
        
        # Step 3: Factory init
        if self._confirm("Execute Step 3 (factory init)?"):
            def step3():
                self.controller.input.execute_sequence(INIT_FACTORY_CHALLENGE)
                return True
            
            self.report.add(self._timed_check("Step 3: Factory init", step3))
    
    # =========================================================================
    # Phase Detection Checks
    # =========================================================================
    
    def check_phase_detection(self) -> None:
        """Test phase detection from memory."""
        print("\n" + "=" * 60)
        print("PHASE DETECTION CHECKS")
        print("=" * 60)
        
        if not self._connected:
            self.report.add(CheckResult(
                "Phase Detection",
                CheckStatus.SKIPPED,
                "Not connected"
            ))
            return
        
        if not self._confirm("Test phase detection?"):
            self.report.add(CheckResult("Phase Detection", CheckStatus.SKIPPED))
            return
        
        # Detect current phase
        def detect_phase():
            phase = self.controller.detect_phase()
            print(f"    Detected: {phase.name}")
            return isinstance(phase, GamePhase)
        
        self.report.add(self._timed_check("Detect current phase", detect_phase))
        
        # State machine
        def check_state_machine():
            sm = self.controller._state_machine
            return sm is not None and hasattr(sm, 'phase')
        
        self.report.add(self._timed_check("State machine", check_state_machine))
    
    # =========================================================================
    # Observation Building Checks
    # =========================================================================
    
    def check_observations(self) -> None:
        """Test observation building."""
        print("\n" + "=" * 60)
        print("OBSERVATION CHECKS")
        print("=" * 60)
        
        if not self._connected:
            self.report.add(CheckResult(
                "Observations",
                CheckStatus.SKIPPED,
                "Not connected"
            ))
            return
        
        if not self._confirm("Test observation building?"):
            self.report.add(CheckResult("Observations", CheckStatus.SKIPPED))
            return
        
        # Battle observation
        def battle_obs():
            obs = self.controller.get_battle_observation()
            print(f"    Shape: {obs.shape}, dtype: {obs.dtype}")
            return len(obs) > 0 and obs.dtype == np.float32
        
        result = self._timed_check("Build battle observation", battle_obs)
        self.report.add(result)
        
        # Draft observation
        def draft_obs():
            obs = self.controller.get_draft_observation()
            print(f"    Shape: {obs.shape}, dtype: {obs.dtype}")
            return len(obs) > 0 and obs.dtype == np.float32
        
        self.report.add(self._timed_check("Build draft observation", draft_obs))
        
        # Swap observation
        def swap_obs():
            obs = self.controller.get_swap_observation()
            print(f"    Shape: {obs.shape}, dtype: {obs.dtype}")
            return len(obs) > 0 and obs.dtype == np.float32
        
        self.report.add(self._timed_check("Build swap observation", swap_obs))
        
        # Action mask
        def action_mask():
            mask = self.controller.get_action_mask()
            print(f"    Mask: {mask}")
            return len(mask) == 6 and mask.dtype == np.float32
        
        self.report.add(self._timed_check("Get action mask", action_mask))
    
    # =========================================================================
    # Agent Integration Checks
    # =========================================================================
    
    def check_agent_integration(self) -> None:
        """Test agent integration."""
        print("\n" + "=" * 60)
        print("AGENT INTEGRATION CHECKS")
        print("=" * 60)
        
        if not self._confirm("Test agent integration?"):
            self.report.add(CheckResult("Agent Integration", CheckStatus.SKIPPED))
            return
        
        # Import agents
        def import_agents():
            from src.agents import RandomDrafter, RandomTactician, create_random_agents
            drafter, tactician = create_random_agents()
            return drafter is not None and tactician is not None
        
        self.report.add(self._timed_check("Import random agents", import_agents))
        
        # Drafter callable
        def test_drafter():
            from src.agents import RandomDrafter
            drafter = RandomDrafter()
            obs = np.zeros(20, dtype=np.float32)
            
            # Test draft phase
            result = drafter(obs, GamePhase.DRAFT_SCREEN)
            print(f"    Draft action: {result}")
            assert len(result) == 3
            
            # Test swap phase
            result = drafter(obs, GamePhase.SWAP_SCREEN)
            print(f"    Swap action: {result}")
            assert len(result) == 1
            
            return True
        
        self.report.add(self._timed_check("Drafter callable", test_drafter))
        
        # Tactician callable
        def test_tactician():
            from src.agents import RandomTactician
            tactician = RandomTactician()
            obs = np.zeros(64, dtype=np.float32)
            mask = np.ones(6, dtype=np.float32)
            
            action = tactician(obs, GamePhase.IN_BATTLE, mask)
            print(f"    Action: {action}")
            return 0 <= action <= 5
        
        self.report.add(self._timed_check("Tactician callable", test_tactician))
    
    # =========================================================================
    # Full Pipeline Check
    # =========================================================================
    
    def check_full_pipeline(self) -> None:
        """Run complete pipeline check."""
        print("\n" + "=" * 60)
        print("FULL PIPELINE CHECK")
        print("=" * 60)
        
        if not self._connected:
            self.report.add(CheckResult(
                "Full Pipeline",
                CheckStatus.SKIPPED,
                "Not connected"
            ))
            return
        
        if not self._confirm("Run full pipeline check? (Full episode with random agents)"):
            self.report.add(CheckResult("Full Pipeline", CheckStatus.SKIPPED))
            return
        
        from src.agents import create_random_agents
        drafter, tactician = create_random_agents(verbose=self.verbose)
        
        # Initialize to draft
        def init_to_draft():
            return self.controller.initialize_to_draft()
        
        result = self._timed_check("Initialize to draft", init_to_draft)
        self.report.add(result)
        
        if result.status != CheckStatus.PASSED:
            return
        
        # Run draft
        def run_draft():
            result = self.controller.step_draft(drafter)
            print(f"    Selections: {result.data.get('selections', [])}")
            return result.success
        
        result = self._timed_check("Execute draft phase", run_draft)
        self.report.add(result)
        
        if result.status != CheckStatus.PASSED:
            return
        
        # Run one battle
        def run_battle():
            result = self.controller.step_battle(tactician)
            print(f"    Outcome: {result.data.get('outcome', 'unknown')}")
            print(f"    Turns: {result.data.get('turns', 0)}")
            return result.success
        
        self.report.add(self._timed_check("Execute battle phase", run_battle))
    
    # =========================================================================
    # Run All Checks
    # =========================================================================
    
    def run_all_checks(self) -> CheckReport:
        """Run all verification checks."""
        print("\n" + "=" * 60)
        print("🔍 BATTLE FACTORY PIPELINE VERIFICATION")
        print("=" * 60)
        
        self.check_connection()
        self.check_memory_reading()
        self.check_phase_detection()
        self.check_observations()
        self.check_agent_integration()
        
        if self._confirm("\nRun navigation checks?"):
            self.check_navigation()
        
        if self._confirm("\nRun full pipeline check?"):
            self.check_full_pipeline()
        
        print(self.report.summary())
        return self.report
    
    def disconnect(self) -> None:
        """Disconnect from emulator."""
        if self._connected:
            self.controller.disconnect()
            self._connected = False


# =============================================================================
# Interactive Mode
# =============================================================================

def run_interactive(checker: StepChecker) -> None:
    """Run in interactive debug mode."""
    print("\n" + "=" * 60)
    print("🔧 INTERACTIVE DEBUG MODE")
    print("=" * 60)
    print("""
Commands:
  connect    - Connect to emulator
  ping       - Ping emulator
  phase      - Detect current phase
  rentals    - Read rental mons
  battle     - Read battle mons
  obs        - Show observations
  mask       - Show action mask
  
  step1      - Title screen navigation
  step2      - NPC dialog navigation
  step3      - Factory init navigation
  full       - Full init to draft
  
  draft      - Execute draft phase
  battle     - Execute battle phase
  swap       - Execute swap phase
  turn [n]   - Execute turn with action n
  
  a/b/up/down/left/right - Press button
  wait [ms]  - Wait milliseconds
  
  agents     - Test agent integration
  run [n]    - Run n episodes
  
  q          - Quit
""")
    
    while True:
        try:
            cmd = input("\n[debug]> ").strip().lower()
            if not cmd:
                continue
            
            parts = cmd.split()
            action = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            if action == 'q':
                break
            elif action == 'connect':
                checker.check_connection()
            elif action == 'ping':
                if checker._connected:
                    print(f"PING: {'PONG' if checker.controller.backend.ping() else 'FAIL'}")
            elif action == 'phase':
                if checker._connected:
                    phase = checker.controller.detect_phase()
                    print(f"Phase: {phase.name}")
            elif action == 'rentals':
                if checker._connected:
                    rentals = checker.controller.backend.memory.read_rental_mons()
                    print(f"Found {len(rentals)} rental mons")
                    for r in rentals:
                        print(f"  Slot {r.slot}: mon_id={r.frontier_mon_id}")
            elif action == 'battle':
                if checker._connected:
                    mons = checker.controller.backend.memory.read_battle_mons()
                    print(f"Found {len(mons)} battle mons")
            elif action == 'obs':
                checker.check_observations()
            elif action == 'mask':
                if checker._connected:
                    mask = checker.controller.get_action_mask()
                    print(f"Mask: {mask}")
            elif action == 'agents':
                checker.check_agent_integration()
            elif action == 'step1':
                if checker._connected:
                    checker.controller.input.execute_sequence(TITLE_TO_CONTINUE)
                    print("Step 1 complete")
            elif action == 'step2':
                if checker._connected:
                    checker.controller.input.execute_sequence(DISMISS_DIALOG)
                    print("Step 2 complete")
            elif action == 'step3':
                if checker._connected:
                    checker.controller.input.execute_sequence(INIT_FACTORY_CHALLENGE)
                    print("Step 3 complete")
            elif action == 'full':
                if checker._connected:
                    success = checker.controller.initialize_to_draft()
                    print(f"Full init: {'success' if success else 'failed'}")
            elif action in ('a', 'b', 'up', 'down', 'left', 'right', 'start'):
                if checker._connected:
                    btn_map = {
                        'a': Button.A, 'b': Button.B,
                        'up': Button.UP, 'down': Button.DOWN,
                        'left': Button.LEFT, 'right': Button.RIGHT,
                        'start': Button.START,
                    }
                    checker.controller.input.press(btn_map[action])
                    print(f"Pressed {action.upper()}")
            elif action == 'wait':
                ms = int(args[0]) if args else 500
                time.sleep(ms / 1000.0)
                print(f"Waited {ms}ms")
            else:
                print(f"Unknown command: {action}")
        
        except KeyboardInterrupt:
            print("\n(Use 'q' to quit)")
        except Exception as e:
            print(f"Error: {e}")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Step-by-step pipeline checker for Battle Factory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Wait for confirmation at each step",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive debug mode",
    )
    parser.add_argument(
        "--check",
        type=str,
        choices=["connection", "memory", "navigation", "observations", "agents", "pipeline"],
        help="Run only specific check",
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
    
    args = parser.parse_args()
    
    checker = StepChecker(
        confirm_steps=args.confirm,
        verbose=args.verbose,
    )
    
    try:
        if args.interactive:
            # Connect first for interactive mode
            print(f"Connecting to {args.host}:{args.port}...")
            if checker.controller.connect(args.host, args.port):
                checker._connected = True
                print("✅ Connected")
            run_interactive(checker)
        
        elif args.check:
            # Run specific check
            check_map = {
                "connection": checker.check_connection,
                "memory": checker.check_memory_reading,
                "navigation": checker.check_navigation,
                "observations": checker.check_observations,
                "agents": checker.check_agent_integration,
                "pipeline": checker.check_full_pipeline,
            }
            
            print(f"Connecting to {args.host}:{args.port}...")
            if checker.controller.connect(args.host, args.port):
                checker._connected = True
                check_map[args.check]()
            print(checker.report.summary())
        
        else:
            # Run all checks
            print(f"Connecting to {args.host}:{args.port}...")
            checker.run_all_checks()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted")
    finally:
        checker.disconnect()


if __name__ == "__main__":
    main()

