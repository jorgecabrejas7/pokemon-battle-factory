"""
Controller Package - Layered game control architecture.

This package provides a modular, layered controller architecture for
Battle Factory gameplay and training:

- InputController: Low-level button input handling
- StateMachine: Game phase management and validation
- BaseController: Common functionality (memory, observations, rewards)
- TrainingController: Step-based interface for RL training

Usage:
    from src.controller import TrainingController, InputController
    
    controller = TrainingController()
    controller.connect()
    controller.initialize_to_draft()
    
    # Phase-level stepping
    controller.step_draft(drafter_agent)
    while not controller.is_run_complete:
        controller.step_battle(tactician_agent)
"""

from .input import (
    InputController,
    Button,
    ButtonPress,
    ButtonSequence,
    TITLE_TO_CONTINUE,
    DISMISS_DIALOG,
    INIT_FACTORY_CHALLENGE,
)

from .state_machine import (
    StateMachine,
    PhaseTransition,
    detect_phase_from_memory,
)

from .base import (
    BaseController,
    RunStats,
    BattleStats,
)

from .training import (
    TrainingController,
    PhaseResult,
    TurnResult,
    EpisodeResult,
    DrafterAgent,
    TacticianAgent,
)


__all__ = [
    # Input
    "InputController",
    "Button",
    "ButtonPress",
    "ButtonSequence",
    "TITLE_TO_CONTINUE",
    "DISMISS_DIALOG",
    "INIT_FACTORY_CHALLENGE",
    # State Machine
    "StateMachine",
    "PhaseTransition",
    "detect_phase_from_memory",
    # Base Controller
    "BaseController",
    "RunStats",
    "BattleStats",
    # Training Controller
    "TrainingController",
    "PhaseResult",
    "TurnResult",
    "EpisodeResult",
    "DrafterAgent",
    "TacticianAgent",
]
