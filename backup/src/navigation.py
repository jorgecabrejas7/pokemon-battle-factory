"""
Navigation Sequences for Pokemon Emerald Battle Factory.

This module provides button sequence macros for auto-navigating
through the game to reach the Battle Factory draft screen.

Navigation Flow:
1. Title Screen -> Press Start -> Continue
2. Overworld -> Walk to Battle Factory entrance
3. Factory Lobby -> Talk to attendant -> Start challenge
4. Challenge Setup -> Select Lv50 Singles -> Confirm
5. Draft Screen -> Ready for agent control

The sequences are designed to be robust with appropriate waits
for screen transitions and animations.
"""

import logging
from typing import TYPE_CHECKING, List, Tuple, Union, Protocol
from dataclasses import dataclass

from .controller.input import Button

if TYPE_CHECKING:
    from .game_controller import GameController
    from .controller.input import InputController

logger = logging.getLogger(__name__)


# =============================================================================
# Button Constants
# =============================================================================
# Button enum imported from .controller.input



@dataclass
class NavStep:
    """Single navigation step."""
    button: Button
    hold_time: float = 0.08       # How long to hold button (seconds)
    wait_after: float = 0.25     # Wait after release (seconds)
    description: str = ""


# =============================================================================
# Pre-defined Navigation Sequences (User-defined steps)
# =============================================================================

# Step 1: Load title screen - Press A twice
LOAD_TITLE_SCREEN: List[NavStep] = [
    NavStep(Button.B, wait_after=0.1, description="Press B to get to initial state"),
    NavStep(Button.B, wait_after=0.1, description="Press B to get to initial state"),
    NavStep(Button.B, wait_after=0.1, description="Press B to get to initial state"),
    NavStep(Button.A, wait_after=0.1, description="Press A (1/2) - Load save"),
    NavStep(Button.A, wait_after=0.1, description="Press A (2/2) - Confirm load"),
]

# Step 2: Talk to NPC - Press B 3 times
TALK_TO_NPC: List[NavStep] = [
    NavStep(Button.B, wait_after=0.5, description="Press B (1/3) - Dialog"),
    NavStep(Button.B, wait_after=0.5, description="Press B (2/3) - Dialog"),
    NavStep(Button.B, wait_after=0., description="Press B (3/3) - Dialog"),
]

# Step 3: Init Battle Factory challenge
# Press A 5 times, Press down arrow, Press A 4 times, Wait, Press A, Press B 10 times
INIT_BATTLE_FACTORY: List[NavStep] = [
    # Press A 5 times
    NavStep(Button.A, wait_after=0.5, description="Press A (1/5) - Init"),
    NavStep(Button.A, wait_after=0.5, description="Press A (2/5) - Init"),
    NavStep(Button.A, wait_after=0.5, description="Press A (3/5) - Init"),
    NavStep(Button.A, wait_after=0.5, description="Press A (4/5) - Init"),
    NavStep(Button.A, wait_after=0.5, description="Press A (5/5) - Init"),
    # Press down arrow (select option)
    NavStep(Button.DOWN, wait_after=0.25, description="Press Down - Select option"),
    # Press A 4 times
    NavStep(Button.A, wait_after=0.5, description="Press A (1/4) - Confirm"),
    NavStep(Button.A, wait_after=0.5, description="Press A (2/4) - Confirm"),
    NavStep(Button.A, wait_after=0.5, description="Press A (3/4) - Confirm"),
    NavStep(Button.A, wait_after=0.5, description="Press A (4/4) - Confirm"),
    # Wait a little bit
    NavStep(Button.WAIT, wait_after=1.5, description="Wait for transition"),
    # Press A once more
    NavStep(Button.A, wait_after=0.5, description="Press A - Continue"),
    # Press B 10 times (skip through dialogs/animations)
    NavStep(Button.B, wait_after=0.3, description="Press B (1/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (2/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (3/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (4/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (5/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (6/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (7/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (8/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (9/10) - Skip"),
    NavStep(Button.B, wait_after=0.3, description="Press B (10/10) - Skip"),
]

# Combined: Full initialization from title to draft screen
FULL_INIT_TO_DRAFT: List[NavStep] = (
    LOAD_TITLE_SCREEN + 
    TALK_TO_NPC + 
    INIT_BATTLE_FACTORY
)


# =============================================================================
# Navigation Executor
# =============================================================================

class NavigationSequence:
    """
    Executes navigation sequences on the game controller.
    
    Provides methods to navigate through different parts of the game
    to reach the Battle Factory draft screen.
    
    Usage:
        nav = NavigationSequence(controller)
        nav.navigate_title_screen()
        nav.navigate_to_battle_factory()
        nav.start_factory_challenge()
    """
    
    def __init__(self, controller: Union["GameController", "InputController"]):
        """
        Initialize with a game controller or input controller.
        
        Args:
            controller: Controller instance to send inputs to
        """
        self.controller = controller
        self.verbose = getattr(controller, 'verbose', False)
    
    def _execute_step(self, step: NavStep):
        """Execute a single navigation step."""
        import time
        
        # Always print the step description
        if self.verbose:
            print(f"  → {step.description}")
        
        if step.button == Button.WAIT:
            time.sleep(step.wait_after)
            return
        
        # Map button enum to controller method
        # Both GameController and InputController support these
        button_map = {
            Button.A: self.controller.press_a,
            Button.B: self.controller.press_b,
            Button.START: self.controller.press_start,
            Button.UP: self.controller.press_up,
            Button.DOWN: self.controller.press_down,
            Button.LEFT: self.controller.press_left,
            Button.RIGHT: self.controller.press_right,
        }
        
        press_fn = button_map.get(step.button)
        if press_fn:
            # For directional buttons with long holds, use special handling
            if step.hold_time > 0.2:
                self._hold_button(step.button, step.hold_time)
                time.sleep(step.wait_after)
            else:
                press_fn(wait=step.wait_after)
    
    def _hold_button(self, button: Button, hold_seconds: float):
        """Hold a button for a duration (for walking)."""
        import time
        
        # support both backend styles (direct or via input controller)
        backend = getattr(self.controller, 'backend', None)
        if not backend:
             logger.warning("No backend found for hold_button")
             return

        # Use the mask property from Button enum (defined in input.py)
        code = button.mask
        
        if code:
            backend._send_command(f"SET_INPUT {code}")
            time.sleep(hold_seconds)
            backend._send_command("SET_INPUT 0")
        else:
            logger.warning(f"Unknown button: {button}")
    
    def _execute_sequence(self, sequence: List[NavStep], name: str):
        """Execute a full navigation sequence."""
        logger.info(f"  Executing: {name}")
        for step in sequence:
            self._execute_step(step)
    
    def load_title_screen(self):
        """
        Step 1: Load save from title screen.
        
        Press A twice to load the save file.
        """
        logger.info("Step 1: Loading title screen...")
        self._execute_sequence(LOAD_TITLE_SCREEN, "Load Title Screen")
        logger.info("  ✓ Save loaded")
    
    def talk_to_npc(self):
        """
        Step 2: Talk to NPC / dismiss dialogs.
        
        Press B 3 times to get through dialog.
        """
        logger.info("Step 2: Talking to NPC...")
        self._execute_sequence(TALK_TO_NPC, "Talk to NPC")
        logger.info("  ✓ NPC dialog complete")
    
    def init_battle_factory(self):
        """
        Step 3: Initialize Battle Factory challenge.
        
        Press A 5 times, Down, A 4 times, wait, A, B 10 times.
        This navigates through the menus to start the challenge.
        """
        logger.info("Step 3: Initializing Battle Factory...")
        self._execute_sequence(INIT_BATTLE_FACTORY, "Init Battle Factory")
        logger.info("  ✓ Battle Factory initialized, at draft screen")
    
    def full_initialization(self) -> bool:
        """
        Complete initialization from title to draft screen.
        
        Executes all 3 steps:
        1. Load title screen (A x2)
        2. Talk to NPC (B x3)  
        3. Init Battle Factory (A x5, Down, A x4, Wait, A, B x10)
        
        Returns:
            True if successful
        """
        try:
            self.load_title_screen()
            self.talk_to_npc()
            self.init_battle_factory()
            return True
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    # Legacy method names for compatibility
    def navigate_title_screen(self):
        """Legacy: Use load_title_screen() instead."""
        self.load_title_screen()
    
    def navigate_to_battle_factory(self):
        """Legacy: Use talk_to_npc() instead."""
        self.talk_to_npc()
    
    def start_factory_challenge(self):
        """Legacy: Use init_battle_factory() instead."""
        self.init_battle_factory()


# =============================================================================
# Interactive Navigation Helpers
# =============================================================================

def wait_for_user(prompt: str = "Press Enter to continue..."):
    """Wait for user confirmation (for debugging)."""
    input(prompt)


def navigate_with_confirmation(controller: "GameController"):
    """
    Interactive navigation with user confirmation at each step.
    
    Useful for debugging and testing navigation sequences.
    """
    nav = NavigationSequence(controller)
    
    print("\n=== Interactive Navigation ===")
    print("This will navigate to the Battle Factory draft screen.")
    print("Press Enter after each step to continue.\n")
    
    wait_for_user("Ready to navigate title screen?")
    nav.navigate_title_screen()
    
    wait_for_user("Ready to walk to Battle Factory?")
    nav.navigate_to_battle_factory()
    
    wait_for_user("Ready to start challenge?")
    nav.start_factory_challenge()
    
    print("\n✓ Navigation complete! You should be at the draft screen.")


# =============================================================================
# Custom Navigation Builder
# =============================================================================

class NavigationBuilder:
    """
    Builder for creating custom navigation sequences.
    
    Usage:
        nav = NavigationBuilder(controller)
        nav.press_a().wait(30).press_down().press_a().execute()
    """
    
    def __init__(self, controller: "GameController"):
        self.controller = controller
        self.steps: List[NavStep] = []
    
    def press_a(self, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.A, wait_after=wait))
        return self
    
    def press_b(self, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.B, wait_after=wait))
        return self
    
    def press_start(self, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.START, wait_after=wait))
        return self
    
    def press_up(self, hold: int = 4, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.UP, hold_frames=hold, wait_after=wait))
        return self
    
    def press_down(self, hold: int = 4, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.DOWN, hold_frames=hold, wait_after=wait))
        return self
    
    def press_left(self, hold: int = 4, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.LEFT, hold_frames=hold, wait_after=wait))
        return self
    
    def press_right(self, hold: int = 4, wait: int = 15) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.RIGHT, hold_frames=hold, wait_after=wait))
        return self
    
    def wait(self, frames: int) -> "NavigationBuilder":
        self.steps.append(NavStep(Button.WAIT, wait_after=frames))
        return self
    
    def wait_seconds(self, seconds: float) -> "NavigationBuilder":
        frames = int(seconds * 60)
        return self.wait(frames)
    
    def execute(self):
        """Execute all accumulated steps."""
        executor = NavigationSequence(self.controller)
        for step in self.steps:
            executor._execute_step(step)
        self.steps.clear()
    
    def clear(self) -> "NavigationBuilder":
        """Clear accumulated steps."""
        self.steps.clear()
        return self

