"""
Game Executor - Centralizes ALL game interactions with consistent state setup.

This module provides a GameExecutor class that handles all game phase interactions:
- Draft phase: Selecting Pokemon from rental pool
- Battle phase: Move selection and switches
- Swap phase: Choosing whether to swap team members

Each interaction has a setup method (e.g., set_up_move_choice) that ensures
consistent initial state, and an execute method that performs the action.

Usage:
    executor = GameExecutor(input_ctrl)
    
    # Draft phase
    executor.set_up_draft_phase()
    executor.execute_draft_selection([2, 4, 0])  # Select Pokemon at indices 2, 4, 0
    
    # Battle phase
    executor.set_up_move_choice()
    executor.execute_move(0)  # Use Move 1
    
    # Swap phase
    executor.set_up_swap_phase()
    executor.execute_swap_decision(0)  # Keep team (0) or swap slot (1-3)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, List

from .input import InputController, Button
from ..config import config

if TYPE_CHECKING:
    from ..backends.emerald.backend import EmeraldBackend

logger = logging.getLogger(__name__)


class GameExecutor:
    """
    Centralizes all game interactions with consistent state setup.
    
    This class is the single source of truth for how button presses map to
    game actions. Both TrainingController and run_random.py use this class
    to ensure identical behavior.
    
    Each phase has:
    - set_up_*: Ensures consistent initial state
    - execute_*: Performs the actual action
    
    Attributes:
        input: InputController for button presses
        backend: Optional backend for reading game state
        verbose: Enable detailed logging
    """
    
    def __init__(
        self,
        input_ctrl: InputController,
        backend: Optional[EmeraldBackend] = None,
        verbose: bool = False,
    ):
        """
        Initialize the game executor.
        
        Args:
            input_ctrl: InputController instance for sending button inputs
            backend: Optional EmeraldBackend for reading game state
            verbose: Enable verbose logging of actions
        """
        self.input = input_ctrl
        self.backend = backend
        self.verbose = verbose

    # =========================================================================
    # DRAFT PHASE
    # =========================================================================
    
    def set_up_draft_phase(self) -> None:
        """
        Ensure consistent state at start of draft selection.
        
        Assumes we're at the rental Pokemon display screen with cursor
        at position 0 (top-left Pokemon).
        """
        if self.verbose:
            logger.info("[GameExecutor] Setting up draft phase")
        
        # Press B to cancel any accidental selections
        self.input.press_b(wait=0.1)
        self.input.press_b(wait=0.1)
        
        # Brief wait for UI to stabilize
        self.input.wait(config.timing.wait_short)
    
    def execute_draft_selection(self, selections: List[int]) -> None:
        """
        Execute draft selection - choose 3 Pokemon from 6 rentals.
        
        Rental Pokemon are displayed in a 2x3 grid:
            [0] [1] [2]
            [3] [4] [5]
        
        Args:
            selections: List of 3 unique indices [0-5] in selection order
        """
        if len(selections) != 3:
            raise ValueError(f"Must select exactly 3 Pokemon, got {len(selections)}")
        
        if self.verbose:
            logger.info(f"[GameExecutor] Draft: selecting indices {selections}")
        
        current_pos = 0  # Start at position 0
        
        for selection in selections:
            # Navigate to target position
            self._navigate_rental_grid(current_pos, selection)
            
            # Select this Pokemon
            self.input.press_a(wait=config.timing.wait_short)
            
            # After selection, cursor moves (implementation-specific)
            # For now, assume we return to 0 or need to track position
            current_pos = selection
        
        # Confirm the team selection
        self.input.wait(config.timing.wait_medium)
        self.input.press_a(wait=config.timing.wait_medium)
    
    def _navigate_rental_grid(self, from_pos: int, to_pos: int) -> None:
        """
        Navigate within the 2x3 rental grid.
        
        Grid layout:
            [0] [1] [2]
            [3] [4] [5]
        
        Args:
            from_pos: Current position 0-5
            to_pos: Target position 0-5
        """
        from_row, from_col = from_pos // 3, from_pos % 3
        to_row, to_col = to_pos // 3, to_pos % 3
        
        # Vertical navigation
        row_diff = to_row - from_row
        if row_diff > 0:
            for _ in range(row_diff):
                self.input.press_down()
        elif row_diff < 0:
            for _ in range(-row_diff):
                self.input.press_up()
        
        # Horizontal navigation
        col_diff = to_col - from_col
        if col_diff > 0:
            for _ in range(col_diff):
                self.input.press_right()
        elif col_diff < 0:
            for _ in range(-col_diff):
                self.input.press_left()

    # =========================================================================
    # BATTLE PHASE - MOVE SELECTION
    # =========================================================================
    
    def set_up_move_choice(self) -> None:
        """
        Ensure consistent state before move selection.
        
        Resets to main battle menu (Fight/Bag/Pokemon/Run) by pressing B
        to cancel any open sub-menus.
        """
        if self.verbose:
            logger.info("[GameExecutor] Setting up move choice")
        
        # Press B to cancel any sub-menus
        self.input.press_b(wait=0.05)
        self.input.press_b(wait=0.05)
        self.input.press_left(hold=config.timing.wait_short)
        self.input.press_up(hold=config.timing.wait_short)
        
        # Wait for menu to stabilize
        self.input.wait(config.timing.wait_short)
    
    def execute_move(self, move_index: int) -> None:
        """
        Execute move selection (0-3).
        
        Move layout is a 2x2 grid:
            [0] [1]
            [2] [3]
        
        Args:
            move_index: Move index 0-3
        """
        if not 0 <= move_index <= 3:
            raise ValueError(f"Move index must be 0-3, got {move_index}")
        
        if self.verbose:
            logger.info(f"[GameExecutor] Executing Move {move_index + 1}")
        
        # Select Fight menu
        self.input.press_a(wait=config.timing.wait_short)
        
        # Navigate to move in 2x2 grid
        row = move_index // 2  # 0 or 1
        col = move_index % 2   # 0 or 1
        
        if row > 0:
            self.input.press_down()
        if col > 0:
            self.input.press_right()
        
        # Confirm move selection
        self.input.press_a(wait=config.timing.wait_short)

    # =========================================================================
    # BATTLE PHASE - SWITCH
    # =========================================================================
    
    def set_up_switch_choice(self) -> None:
        """
        Ensure consistent state before voluntary switch.
        
        Same as move choice - reset to main battle menu.
        """
        self.set_up_move_choice()
    
    def execute_switch(self, pokemon_index: int) -> None:
        """
        Execute voluntary switch (0-1 = bench Pokemon 1-2).
        
        Party layout (active is slot 0, already on field):
            Slot 0: Active (skip)
            Slot 1: Bench 1 (pokemon_index=0)
            Slot 2: Bench 2 (pokemon_index=1)
        
        Args:
            pokemon_index: Bench Pokemon index 0-1
        """
        if not 0 <= pokemon_index <= 1:
            raise ValueError(f"Pokemon index must be 0-1, got {pokemon_index}")
        
        if self.verbose:
            logger.info(f"[GameExecutor] Switching to bench {pokemon_index + 1}")
        
        # Navigate to Pokemon menu (down from Fight)
        self.input.press_down()
        self.input.press_a(wait=config.timing.wait_short)
        
        # Navigate to target Pokemon (skip active)
        for _ in range(pokemon_index + 1):
            self.input.press_down()
        
        # Select Pokemon and confirm Switch
        self.input.press_a(wait=config.timing.wait_short)
        self.input.press_a(wait=config.timing.wait_short)
    
    def execute_forced_switch(self, pokemon_index: int) -> None:
        """
        Execute forced switch (when active Pokemon faints).
        
        Unlike voluntary switches, the Pokemon menu is already open.
        
        Args:
            pokemon_index: Bench Pokemon index 0-1
        """
        if self.verbose:
            logger.info(f"[GameExecutor] Forced switch to bench {pokemon_index + 1}")
        
        # Navigate to target Pokemon
        for _ in range(pokemon_index + 1):
            self.input.press_down()
        
        # Confirm selection
        self.input.press_a(wait=config.timing.wait_short)
        self.input.press_a(wait=config.timing.wait_short)

    # =========================================================================
    # BATTLE PHASE - UNIFIED ACTION
    # =========================================================================
    
    def execute_battle_action(self, action: int) -> None:
        """
        Execute any battle action (move or switch) from action index.
        
        Args:
            action: Action index 0-5
                0-3: Move 1-4
                4-5: Switch to bench 1-2
        """
        if not 0 <= action <= 5:
            raise ValueError(f"Action must be 0-5, got {action}")
        
        if action < 4:
            self.set_up_move_choice()
            self.execute_move(action)
        else:
            self.set_up_switch_choice()
            self.execute_switch(action - 4)

    # =========================================================================
    # SWAP PHASE (Post-battle team swap)
    # =========================================================================
    
    def set_up_swap_phase(self) -> None:
        """
        Ensure consistent state at swap screen.
        
        Assumes we're at the swap decision screen after a battle.
        """
        if self.verbose:
            logger.info("[GameExecutor] Setting up swap phase")
        
        # Press B to ensure clean state
        self.input.press_b(wait=0.1)
        self.input.wait(config.timing.wait_short)
    
    def execute_swap_decision(self, decision: int) -> None:
        """
        Execute swap decision.
        
        Args:z
            decision: 0 = keep team, 1-3 = swap slot N with opponent's Pokemon
        """
        if not 0 <= decision <= 3:
            raise ValueError(f"Swap decision must be 0-3, got {decision}")
        
        if self.verbose:
            action_str = "keeping team" if decision == 0 else f"swapping slot {decision}"
            logger.info(f"[GameExecutor] Swap: {action_str}")
        
        if decision == 0:
            # Keep team - press B or navigate to "No" option
            self.input.press_b(wait=config.timing.wait_medium)
        else:
            # Navigate to swap slot (assumes vertical list)
            for _ in range(decision):
                self.input.press_down()
            
            self.input.press_a(wait=config.timing.wait_short)
            # Confirm swap
            self.input.press_a(wait=config.timing.wait_medium)

    # =========================================================================
    # UTILITY
    # =========================================================================
    
    @staticmethod
    def get_action_name(action: int) -> str:
        """
        Get human-readable name for a battle action.
        
        Args:
            action: Action index 0-5
            
        Returns:
            Human-readable action name
        """
        names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
        if 0 <= action < len(names):
            return names[action]
        return f"Unknown({action})"

    # =========================================================================
    # BATTLE STATE CHECKING
    # =========================================================================
    
    def check_battle_ended(self) -> bool:
        """
        Check if the current battle has ended.
        
        Returns:
            True if battle ended (win, loss, or draw), False if ongoing
        """
        if self.backend is None:
            raise RuntimeError("Backend required for battle state checking")
        
        from ..core.enums import BattleOutcome
        outcome = self.backend.get_battle_outcome()
        return outcome != BattleOutcome.ONGOING
    
    def get_battle_outcome(self) -> 'BattleOutcome':
        """
        Get the current battle outcome.
        
        Returns:
            BattleOutcome enum (WIN, LOSS, DRAW, ONGOING, RAN)
        """
        if self.backend is None:
            raise RuntimeError("Backend required for battle outcome checking")
        
        return self.backend.get_battle_outcome()
    
    def is_waiting_for_input(self) -> bool:
        """
        Check if game is waiting for player input.
        
        Returns:
            True if waiting for input
        """
        if self.backend is None:
            raise RuntimeError("Backend required for input checking")
        
        return self.backend.is_waiting_for_input()
    
    def wait_for_turn_result(self, timeout_seconds: float = 10.0) -> bool:
        """
        Wait for the turn animation to complete and game to be ready for next input.
        
        Args:
            timeout_seconds: Maximum time to wait
            
        Returns:
            True if ready for input, False if timeout or battle ended
        """
        import time
        
        if self.backend is None:
            raise RuntimeError("Backend required for waiting")
        
        start_time = time.time()
        poll_interval = 0.1
        
        while time.time() - start_time < timeout_seconds:
            # Check if battle ended
            if self.check_battle_ended():
                if self.verbose:
                    outcome = self.get_battle_outcome()
                    logger.info(f"[GameExecutor] Battle ended: {outcome.name}")
                return False
            
            # Check if waiting for input
            if self.is_waiting_for_input():
                if self.verbose:
                    logger.info("[GameExecutor] Ready for next input")
                return True
            
            time.sleep(poll_interval)
        
        logger.warning(f"[GameExecutor] Timeout waiting for turn result after {timeout_seconds}s")
        return False
    
    def execute_turn(self, action: int) -> dict:
        """
        Execute a complete battle turn: action + wait for result + check outcome.
        
        This is the main method agents should use during battle. It:
        1. Sets up consistent state
        2. Executes the action (move 0-3 or switch 4-5)
        3. Waits for animation to complete
        4. Checks battle outcome
        
        Args:
            action: Action index 0-5
                0-3: Move 1-4
                4-5: Switch to bench 1-2
                
        Returns:
            Dict with:
                - action: The action taken
                - action_name: Human-readable action name
                - battle_ended: True if battle is over
                - outcome: BattleOutcome if ended, else None
                - ready_for_input: True if waiting for next action
        """
        from ..core.enums import BattleOutcome
        
        if self.verbose:
            logger.info(f"[GameExecutor] Executing turn: {self.get_action_name(action)}")
        
        # Execute the action
        self.execute_battle_action(action)
        
        # Wait for result
        ready = self.wait_for_turn_result()
        
        # Check outcome
        outcome = self.get_battle_outcome() if self.backend else BattleOutcome.ONGOING
        battle_ended = outcome != BattleOutcome.ONGOING
        
        result = {
            "action": action,
            "action_name": self.get_action_name(action),
            "battle_ended": battle_ended,
            "outcome": outcome if battle_ended else None,
            "ready_for_input": ready and not battle_ended,
        }
        
        if self.verbose:
            if battle_ended:
                logger.info(f"[GameExecutor] Battle ended: {outcome.name}")
            else:
                logger.info(f"[GameExecutor] Turn complete, ready for next action")
        
        return result


    # =========================================================================
    # INITIALIZATION (Auto-Navigation)
    # =========================================================================
    
    def initialize_to_draft(self, from_title: bool = True) -> bool:
        """
        Auto-navigate from current position to the draft screen.
        
        This handles the full sequence:
        Title -> Continue -> Overworld -> Battle Factory -> Start Challenge -> Draft
        
        Args:
            from_title: If True, assumes starting from title screen
            
        Returns:
            True if successful
        """
        if self.verbose:
            logger.info("[GameExecutor] Initializing to draft screen...")
        
        try:
            # Import navigation locally to avoid circular top-level imports
            from ..navigation import NavigationSequence
            
            # NavigationSequence now accepts InputController
            nav = NavigationSequence(self.input)
            
            if from_title:
                if self.verbose:
                    logger.info("  Navigating title screen...")
                nav.navigate_title_screen()
                
                if self.verbose:
                    logger.info("  Navigating to Battle Factory...")
                nav.navigate_to_battle_factory()
                
                if self.verbose:
                    logger.info("  Starting challenge...")
                nav.start_factory_challenge()
            
            return True
            
        except Exception as e:
            logger.error(f"[GameExecutor] Initialization failed: {e}")
            return False
