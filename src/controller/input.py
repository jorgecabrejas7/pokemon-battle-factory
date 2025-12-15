"""
Input Controller - Low-level button input handling.

This module provides a unified interface for sending button inputs
to the emulator, shared by all controller implementations.

Usage:
    input_ctrl = InputController(backend)
    input_ctrl.press_a()
    input_ctrl.press_direction('down', count=3)
    input_ctrl.execute_sequence([Button.A, Button.DOWN, Button.A])
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, TYPE_CHECKING

from ..config import config, Buttons

if TYPE_CHECKING:
    from ..backends.emerald.backend import EmeraldBackend

logger = logging.getLogger(__name__)


class Button(Enum):
    """Button input types."""
    A = auto()
    B = auto()
    START = auto()
    SELECT = auto()
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    L = auto()
    R = auto()
    WAIT = auto()  # Special: just wait, no input
    
    @property
    def mask(self) -> int:
        """Get the bitmask for this button."""
        masks = {
            Button.A: Buttons.A,
            Button.B: Buttons.B,
            Button.START: Buttons.START,
            Button.SELECT: Buttons.SELECT,
            Button.UP: Buttons.UP,
            Button.DOWN: Buttons.DOWN,
            Button.LEFT: Buttons.LEFT,
            Button.RIGHT: Buttons.RIGHT,
            Button.L: Buttons.L,
            Button.R: Buttons.R,
        }
        return masks.get(self, 0)
    
    @property
    def name_pretty(self) -> str:
        """Get pretty name for display."""
        names = {
            Button.A: "A",
            Button.B: "B",
            Button.START: "START",
            Button.SELECT: "SELECT",
            Button.UP: "↑",
            Button.DOWN: "↓",
            Button.LEFT: "←",
            Button.RIGHT: "→",
            Button.L: "L",
            Button.R: "R",
            Button.WAIT: "WAIT",
        }
        return names.get(self, str(self))


@dataclass
class ButtonPress:
    """Single button press specification."""
    button: Button
    hold_time: float = 0.08      # How long to hold
    wait_after: float = 0.25     # Wait after release
    description: str = ""
    
    @classmethod
    def quick(cls, button: Button, desc: str = "") -> ButtonPress:
        """Create a quick button press with short timings."""
        return cls(button, hold_time=0.05, wait_after=0.15, description=desc)


@dataclass
class ButtonSequence:
    """Sequence of button presses."""
    presses: List[ButtonPress]
    name: str = ""
    
    def __iter__(self):
        return iter(self.presses)
    
    def __len__(self):
        return len(self.presses)
    
    @classmethod
    def from_buttons(
        cls, 
        buttons: List[Button], 
        wait: float = 0.25,
        name: str = ""
    ) -> ButtonSequence:
        """Create sequence from list of buttons with uniform timing."""
        return cls(
            presses=[ButtonPress(b, wait_after=wait) for b in buttons],
            name=name
        )


class InputController:
    """
    Low-level button input controller.
    
    Provides methods for:
    - Single button presses
    - Button sequences
    - Directional navigation
    - Menu navigation
    
    Uses real-time sleep for timing (game runs continuously).
    """
    
    def __init__(self, backend: EmeraldBackend, verbose: bool = False):
        """
        Initialize input controller.
        
        Args:
            backend: Emulator backend for sending commands
            verbose: Whether to log button presses
        """
        self.backend = backend
        self.verbose = verbose
        self._timing = config.timing
    
    # =========================================================================
    # Core Button Methods
    # =========================================================================
    
    def press(
        self, 
        button: Button, 
        hold_time: float | None = None,
        wait_after: float | None = None,
        silent: bool = False,
    ) -> None:
        """
        Press and release a button.
        
        Args:
            button: Button to press
            hold_time: How long to hold (default from config)
            wait_after: How long to wait after (default from config)
            silent: Suppress logging
        """
        if button == Button.WAIT:
            time.sleep(wait_after or self._timing.wait_short)
            return
        
        hold = hold_time or self._timing.button_hold_time
        wait = wait_after or self._timing.wait_short
        
        if self.verbose and not silent:
            logger.debug(f"Press {button.name_pretty}")
        
        # Send button press
        self.backend._send_command(f"SET_INPUT {button.mask}")
        time.sleep(hold)
        
        # Release
        self.backend._send_command("SET_INPUT 0")
        
        # Wait after
        if wait > 0:
            time.sleep(wait)
    
    def press_button(self, bp: ButtonPress, silent: bool = False) -> None:
        """Execute a ButtonPress specification."""
        self.press(
            bp.button, 
            hold_time=bp.hold_time,
            wait_after=bp.wait_after,
            silent=silent
        )
    
    def execute_sequence(
        self, 
        sequence: ButtonSequence | List[Button],
        silent: bool = False
    ) -> None:
        """
        Execute a sequence of button presses.
        
        Args:
            sequence: ButtonSequence or list of Buttons
            silent: Suppress logging
        """
        if isinstance(sequence, list):
            sequence = ButtonSequence.from_buttons(sequence)
        
        if self.verbose and not silent and sequence.name:
            logger.info(f"Executing: {sequence.name}")
        
        for bp in sequence:
            self.press_button(bp, silent=silent)
    
    # =========================================================================
    # Convenience Button Methods
    # =========================================================================
    
    def press_a(self, wait: float | None = None, silent: bool = False) -> None:
        """Press A button."""
        self.press(Button.A, wait_after=wait, silent=silent)
    
    def press_b(self, wait: float | None = None, silent: bool = False) -> None:
        """Press B button."""
        self.press(Button.B, wait_after=wait, silent=silent)
    
    def press_start(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Start button."""
        self.press(Button.START, wait_after=wait, silent=silent)
    
    def press_select(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Select button."""
        self.press(Button.SELECT, wait_after=wait, silent=silent)
    
    def press_up(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Up on D-pad."""
        self.press(Button.UP, wait_after=wait, silent=silent)
    
    def press_down(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Down on D-pad."""
        self.press(Button.DOWN, wait_after=wait, silent=silent)
    
    def press_left(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Left on D-pad."""
        self.press(Button.LEFT, wait_after=wait, silent=silent)
    
    def press_right(self, wait: float | None = None, silent: bool = False) -> None:
        """Press Right on D-pad."""
        self.press(Button.RIGHT, wait_after=wait, silent=silent)
    
    # =========================================================================
    # Navigation Helpers
    # =========================================================================
    
    def press_direction(
        self, 
        direction: str, 
        count: int = 1,
        wait: float | None = None,
        silent: bool = False,
    ) -> None:
        """
        Press a directional button N times.
        
        Args:
            direction: 'up', 'down', 'left', or 'right'
            count: Number of times to press
            wait: Wait after each press
            silent: Suppress logging
        """
        button_map = {
            'up': Button.UP,
            'down': Button.DOWN,
            'left': Button.LEFT,
            'right': Button.RIGHT,
        }
        
        button = button_map.get(direction.lower())
        if not button:
            logger.warning(f"Unknown direction: {direction}")
            return
        
        for _ in range(count):
            self.press(button, wait_after=wait, silent=silent)
    
    def navigate_menu(
        self, 
        target: int, 
        current: int = 0, 
        vertical: bool = True,
        silent: bool = False,
    ) -> None:
        """
        Navigate a menu to target index.
        
        Args:
            target: Target menu index
            current: Current menu index (default 0)
            vertical: Use up/down (True) or left/right (False)
            silent: Suppress logging
        """
        diff = target - current
        if diff == 0:
            return
        
        if vertical:
            direction = 'down' if diff > 0 else 'up'
        else:
            direction = 'right' if diff > 0 else 'left'
        
        self.press_direction(direction, count=abs(diff), silent=silent)
    
    def hold_button(
        self, 
        button: Button, 
        duration: float,
        silent: bool = False,
    ) -> None:
        """
        Hold a button for a duration (for walking).
        
        Args:
            button: Button to hold
            duration: How long to hold in seconds
            silent: Suppress logging
        """
        if self.verbose and not silent:
            logger.debug(f"Hold {button.name_pretty} for {duration}s")
        
        self.backend._send_command(f"SET_INPUT {button.mask}")
        time.sleep(duration)
        self.backend._send_command("SET_INPUT 0")
    
    # =========================================================================
    # Wait Methods
    # =========================================================================
    
    def wait(self, seconds: float) -> None:
        """Wait for N seconds."""
        time.sleep(seconds)
    
    def wait_frames(self, frames: int) -> None:
        """Wait for approximately N frames (at 60fps)."""
        time.sleep(frames / self._timing.fps)
    
    def wait_short(self) -> None:
        """Short wait (~15 frames)."""
        time.sleep(self._timing.wait_short)
    
    def wait_medium(self) -> None:
        """Medium wait (~30 frames)."""
        time.sleep(self._timing.wait_medium)
    
    def wait_long(self) -> None:
        """Long wait (~60 frames)."""
        time.sleep(self._timing.wait_long)


# =============================================================================
# Pre-defined Button Sequences
# =============================================================================

# Title screen navigation
TITLE_TO_CONTINUE = ButtonSequence(
    name="Title to Continue",
    presses=[
        ButtonPress(Button.B, wait_after=0.1, description="Clear any popup"),
        ButtonPress(Button.B, wait_after=0.1, description="Clear any popup"),
        ButtonPress(Button.B, wait_after=0.1, description="Clear any popup"),
        ButtonPress(Button.A, wait_after=0.5, description="Load save"),
        ButtonPress(Button.A, wait_after=0.5, description="Confirm"),
    ]
)

# NPC dialog dismissal
DISMISS_DIALOG = ButtonSequence(
    name="Dismiss Dialog",
    presses=[
        ButtonPress(Button.B, wait_after=0.5, description="Dialog 1"),
        ButtonPress(Button.B, wait_after=0.5, description="Dialog 2"),
        ButtonPress(Button.B, wait_after=0.3, description="Dialog 3"),
    ]
)

# Battle Factory initialization
INIT_FACTORY_CHALLENGE = ButtonSequence(
    name="Init Factory Challenge",
    presses=[
        # Press A 5 times
        ButtonPress(Button.A, wait_after=0.5, description="Init 1"),
        ButtonPress(Button.A, wait_after=0.5, description="Init 2"),
        ButtonPress(Button.A, wait_after=0.5, description="Init 3"),
        ButtonPress(Button.A, wait_after=0.5, description="Init 4"),
        ButtonPress(Button.A, wait_after=0.5, description="Init 5"),
        # Select level mode
        ButtonPress(Button.DOWN, wait_after=0.25, description="Select Lv50"),
        # Confirm selections
        ButtonPress(Button.A, wait_after=0.5, description="Confirm 1"),
        ButtonPress(Button.A, wait_after=0.5, description="Confirm 2"),
        ButtonPress(Button.A, wait_after=0.5, description="Confirm 3"),
        ButtonPress(Button.A, wait_after=0.5, description="Confirm 4"),
        # Wait for transition
        ButtonPress(Button.WAIT, wait_after=1.5, description="Transition"),
        # Continue
        ButtonPress(Button.A, wait_after=0.5, description="Continue"),
        # Skip dialogs
        *[ButtonPress(Button.B, wait_after=0.3, description=f"Skip {i+1}") 
          for i in range(10)],
    ]
)

