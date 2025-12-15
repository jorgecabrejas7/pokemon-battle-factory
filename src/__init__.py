"""
Pokemon Battle Factory RL System.

A hierarchical reinforcement learning system for playing the Battle Factory
facility in Pokemon Emerald. Uses a two-agent architecture:

- Drafter: Handles team selection and post-battle swaps (Transformer-based)
- Tactician: Makes turn-by-turn battle decisions (LSTM-based)

Architecture Overview:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    TrainingController                            │
    │  ┌──────────────────────────────────────────────────────────┐  │
    │  │                     State Machine                         │  │
    │  │    DRAFT → BATTLE → POST_BATTLE → (SWAP) → BATTLE...    │  │
    │  └──────────────────────────────────────────────────────────┘  │
    │                            ↓                                     │
    │  ┌────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
    │  │   Drafter      │    │   Tactician     │    │  Backend    │  │
    │  │   (obs→team)   │    │   (obs→action)  │    │  (mGBA)     │  │
    │  └────────────────┘    └─────────────────┘    └─────────────┘  │
    └─────────────────────────────────────────────────────────────────┘

Usage:
    from src.controller import TrainingController
    from src.agents import RandomDrafter, RandomTactician
    
    controller = TrainingController()
    controller.connect()
    controller.initialize_to_draft()
    
    drafter = RandomDrafter()
    tactician = RandomTactician()
    
    result = controller.run_episode(drafter, tactician)
    print(f"Win streak: {result.win_streak}")
"""

from __future__ import annotations

# Package version
__version__ = "0.1.0"

# Configuration
from .config import config, BattleFactoryConfig, Buttons

# Core enums and types
from .core.enums import (
    GamePhase,
    BattleOutcome,
    BattleAction,
    SwapAction,
    MoveCategory,
    StatusCondition,
    Weather,
    PokemonType,
)

# Exceptions
from .core.exceptions import (
    BattleFactoryError,
    ConnectionError,
    DisconnectedError,
    MemoryReadError,
    InvalidStateError,
    InvalidActionError,
)

# Controller architecture (primary interface)
from .controller import (
    TrainingController,
    BaseController,
    InputController,
    StateMachine,
    PhaseResult,
    TurnResult,
    EpisodeResult,
    RunStats,
    BattleStats,
)

# Agent interfaces
from .agents import (
    BaseDrafter,
    BaseTactician,
    DrafterProtocol,
    TacticianProtocol,
    RandomDrafter,
    RandomTactician,
    create_random_agents,
)

__all__ = [
    # Version
    "__version__",
    # Config
    "config",
    "BattleFactoryConfig",
    "Buttons",
    # Enums
    "GamePhase",
    "BattleOutcome",
    "BattleAction",
    "SwapAction",
    "MoveCategory",
    "StatusCondition",
    "Weather",
    "PokemonType",
    # Exceptions
    "BattleFactoryError",
    "ConnectionError",
    "DisconnectedError",
    "MemoryReadError",
    "InvalidStateError",
    "InvalidActionError",
    # Controller
    "TrainingController",
    "BaseController",
    "InputController",
    "StateMachine",
    "PhaseResult",
    "TurnResult",
    "EpisodeResult",
    "RunStats",
    "BattleStats",
    # Agents
    "BaseDrafter",
    "BaseTactician",
    "DrafterProtocol",
    "TacticianProtocol",
    "RandomDrafter",
    "RandomTactician",
    "create_random_agents",
]
