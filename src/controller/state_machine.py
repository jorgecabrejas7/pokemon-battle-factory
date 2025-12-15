"""
State Machine - Game phase management and transitions.

This module provides the StateMachine class that manages game phase
transitions and validates state changes.

Usage:
    sm = StateMachine()
    sm.transition_to(GamePhase.DRAFT_SCREEN)
    
    if sm.can_transition_to(GamePhase.IN_BATTLE):
        sm.transition_to(GamePhase.IN_BATTLE)
"""

from __future__ import annotations

import logging
from typing import Set, Optional, Callable, Dict
from dataclasses import dataclass, field

from ..core.enums import GamePhase
from ..core.exceptions import InvalidStateError, StateTransitionError

logger = logging.getLogger(__name__)


@dataclass
class PhaseTransition:
    """Definition of a valid state transition."""
    from_phase: GamePhase
    to_phase: GamePhase
    condition: Optional[Callable[[], bool]] = None
    description: str = ""


class StateMachine:
    """
    Game phase state machine.
    
    Manages transitions between GamePhase states, validating that
    transitions follow the expected game flow.
    
    State Flow:
        UNINITIALIZED -> TITLE_SCREEN -> OVERWORLD -> FACTORY_LOBBY
        -> CHALLENGE_SETUP -> DRAFT_SCREEN -> BATTLE_READY -> IN_BATTLE
        -> BATTLE_END -> (SWAP_SCREEN | BATTLE_READY | RUN_COMPLETE)
    
    Attributes:
        phase: Current game phase
        history: List of previous phases (for debugging)
    """
    
    # Valid transitions as (from_phase, to_phases) pairs
    VALID_TRANSITIONS: Dict[GamePhase, Set[GamePhase]] = {
        GamePhase.UNINITIALIZED: {
            GamePhase.TITLE_SCREEN,
            GamePhase.OVERWORLD,
            GamePhase.FACTORY_LOBBY,
            GamePhase.DRAFT_SCREEN,
            GamePhase.ERROR,
        },
        GamePhase.TITLE_SCREEN: {
            GamePhase.OVERWORLD,
            GamePhase.FACTORY_LOBBY,
            GamePhase.ERROR,
        },
        GamePhase.OVERWORLD: {
            GamePhase.FACTORY_LOBBY,
            GamePhase.TITLE_SCREEN,
            GamePhase.ERROR,
        },
        GamePhase.FACTORY_LOBBY: {
            GamePhase.CHALLENGE_SETUP,
            GamePhase.DRAFT_SCREEN,
            GamePhase.OVERWORLD,
            GamePhase.ERROR,
        },
        GamePhase.CHALLENGE_SETUP: {
            GamePhase.DRAFT_SCREEN,
            GamePhase.FACTORY_LOBBY,
            GamePhase.ERROR,
        },
        GamePhase.DRAFT_SCREEN: {
            GamePhase.BATTLE_READY,
            GamePhase.PRE_BATTLE,
            GamePhase.ERROR,
        },
        GamePhase.BATTLE_READY: {
            GamePhase.PRE_BATTLE,
            GamePhase.IN_BATTLE,
            GamePhase.ERROR,
        },
        GamePhase.PRE_BATTLE: {
            GamePhase.IN_BATTLE,
            GamePhase.BATTLE_ANIMATING,
            GamePhase.ERROR,
        },
        GamePhase.IN_BATTLE: {
            GamePhase.BATTLE_ANIMATING,
            GamePhase.BATTLE_END,
            GamePhase.POST_BATTLE,
            GamePhase.ERROR,
        },
        GamePhase.BATTLE_ANIMATING: {
            GamePhase.IN_BATTLE,
            GamePhase.BATTLE_END,
            GamePhase.POST_BATTLE,
            GamePhase.ERROR,
        },
        GamePhase.BATTLE_END: {
            GamePhase.POST_BATTLE,
            GamePhase.SWAP_SCREEN,
            GamePhase.BATTLE_READY,
            GamePhase.RUN_COMPLETE,
            GamePhase.ERROR,
        },
        GamePhase.POST_BATTLE: {
            GamePhase.SWAP_SCREEN,
            GamePhase.BATTLE_READY,
            GamePhase.RUN_COMPLETE,
            GamePhase.ERROR,
        },
        GamePhase.SWAP_SCREEN: {
            GamePhase.BATTLE_READY,
            GamePhase.PRE_BATTLE,
            GamePhase.RUN_COMPLETE,
            GamePhase.ERROR,
        },
        GamePhase.RUN_COMPLETE: {
            GamePhase.UNINITIALIZED,
            GamePhase.DRAFT_SCREEN,
            GamePhase.TITLE_SCREEN,
            GamePhase.ERROR,
        },
        GamePhase.ERROR: {
            GamePhase.UNINITIALIZED,
            GamePhase.TITLE_SCREEN,
        },
    }
    
    def __init__(self, initial_phase: GamePhase = GamePhase.UNINITIALIZED):
        """
        Initialize state machine.
        
        Args:
            initial_phase: Starting phase
        """
        self._phase = initial_phase
        self._history: list[GamePhase] = [initial_phase]
        self._on_transition_callbacks: list[Callable[[GamePhase, GamePhase], None]] = []
    
    @property
    def phase(self) -> GamePhase:
        """Current game phase."""
        return self._phase
    
    @property
    def history(self) -> list[GamePhase]:
        """Phase transition history."""
        return self._history.copy()
    
    @property
    def previous_phase(self) -> Optional[GamePhase]:
        """Previous phase, if any."""
        return self._history[-2] if len(self._history) > 1 else None
    
    def can_transition_to(self, to_phase: GamePhase) -> bool:
        """
        Check if transition to target phase is valid.
        
        Args:
            to_phase: Target phase
            
        Returns:
            True if transition is valid
        """
        valid = self.VALID_TRANSITIONS.get(self._phase, set())
        return to_phase in valid
    
    def get_valid_transitions(self) -> Set[GamePhase]:
        """Get all valid transitions from current phase."""
        return self.VALID_TRANSITIONS.get(self._phase, set()).copy()
    
    def transition_to(self, to_phase: GamePhase, force: bool = False) -> None:
        """
        Transition to a new phase.
        
        Args:
            to_phase: Target phase
            force: Skip validation (use with caution)
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not force and not self.can_transition_to(to_phase):
            raise StateTransitionError(
                from_state=self._phase.name,
                to_state=to_phase.name,
                message=f"Invalid transition from {self._phase.name} to {to_phase.name}. "
                        f"Valid: {[p.name for p in self.get_valid_transitions()]}"
            )
        
        old_phase = self._phase
        self._phase = to_phase
        self._history.append(to_phase)
        
        # Limit history size
        if len(self._history) > 100:
            self._history = self._history[-50:]
        
        logger.debug(f"Phase transition: {old_phase.name} -> {to_phase.name}")
        
        # Call registered callbacks
        for callback in self._on_transition_callbacks:
            try:
                callback(old_phase, to_phase)
            except Exception as e:
                logger.error(f"Transition callback error: {e}")
    
    def on_transition(self, callback: Callable[[GamePhase, GamePhase], None]) -> None:
        """
        Register a callback for phase transitions.
        
        Args:
            callback: Function taking (from_phase, to_phase)
        """
        self._on_transition_callbacks.append(callback)
    
    def reset(self, to_phase: GamePhase = GamePhase.UNINITIALIZED) -> None:
        """
        Reset state machine.
        
        Args:
            to_phase: Phase to reset to
        """
        self._phase = to_phase
        self._history = [to_phase]
    
    def assert_phase(self, *expected_phases: GamePhase, operation: str = "operation") -> None:
        """
        Assert current phase is one of expected.
        
        Args:
            expected_phases: Valid phases for operation
            operation: Name of operation (for error message)
            
        Raises:
            InvalidStateError: If not in expected phase
        """
        if self._phase not in expected_phases:
            raise InvalidStateError(
                current_state=self._phase.name,
                expected_states=[p.name for p in expected_phases],
                operation=operation,
            )
    
    def __repr__(self) -> str:
        return f"StateMachine(phase={self._phase.name})"


# =============================================================================
# Phase Detection Helpers
# =============================================================================

def detect_phase_from_memory(backend) -> GamePhase:
    """
    Detect current game phase from memory state.
    
    Args:
        backend: EmeraldBackend instance
        
    Returns:
        Detected GamePhase
    """
    if not backend.memory:
        return GamePhase.UNINITIALIZED
    
    # Check if in battle
    try:
        battle_mons = backend.memory.read_battle_mons()
        if len(battle_mons) >= 2 and battle_mons[0].species_id > 0:
            outcome = backend.get_battle_outcome()
            if outcome.value == 0:  # ONGOING
                if backend.is_waiting_for_input():
                    return GamePhase.IN_BATTLE
                else:
                    return GamePhase.BATTLE_ANIMATING
            else:
                return GamePhase.BATTLE_END
    except Exception as e:
        logger.debug(f"Error reading battle state: {e}")
    
    # Check for rental mons (draft screen)
    try:
        rentals = backend.memory.read_rental_mons()
        if len(rentals) > 0:
            return GamePhase.DRAFT_SCREEN
    except Exception as e:
        logger.debug(f"Error reading rentals: {e}")
    
    # Default to overworld
    return GamePhase.OVERWORLD

