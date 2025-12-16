"""
Core Module - Data structures, enums, and protocols.

This module provides the fundamental types used throughout the
Battle Factory RL system.
"""

from __future__ import annotations

from .enums import (
    MoveCategory,
    StatusCondition,
    VolatileStatus,
    Weather,
    Terrain,
    BattleOutcome,
    GamePhase,
    ScreenType,
    FacilityType,
    BattleMode,
    LevelMode,
    PokemonType,
    BattleAction,
    SwapAction,
)

from .dataclasses import (
    Move,
    BasePokemon, 
    RentalPokemon, 
    PlayerPokemon, 
    EnemyPokemon, 
    BattleState, 
    FactoryState,
)

from .protocols import BattleBackend

from .exceptions import (
    BattleFactoryError,
    ConnectionError,
    DisconnectedError,
    CommandTimeoutError,
    MemoryError,
    MemoryReadError,
    MemoryWriteError,
    DecryptionError,
    StateError,
    InvalidStateError,
    StateTransitionError,
    PhaseTimeoutError,
    ActionError,
    InvalidActionError,
    ActionMaskedError,
    DataError,
    KnowledgeBaseError,
    EntityNotFoundError,
    NavigationError,
    NavigationTimeoutError,
    UnexpectedScreenError,
    AgentError,
    AgentNotReadyError,
)

from .knowledge_base import KnowledgeBase, kb, get_kb

__all__ = [
    # Enums
    "MoveCategory",
    "StatusCondition",
    "VolatileStatus",
    "Weather",
    "Terrain",
    "BattleOutcome",
    "GamePhase",
    "ScreenType",
    "FacilityType",
    "BattleMode",
    "LevelMode",
    "PokemonType",
    "BattleAction",
    "SwapAction",
    # Dataclasses
    "Move",
    "BasePokemon",
    "RentalPokemon",
    "PlayerPokemon",
    "EnemyPokemon",
    "BattleState",
    "FactoryState",
    # Protocols
    "BattleBackend",
    # Knowledge Base
    "KnowledgeBase",
    "kb",
    "get_kb",
    # Exceptions
    "BattleFactoryError",
    "ConnectionError",
    "DisconnectedError",
    "CommandTimeoutError",
    "MemoryError",
    "MemoryReadError",
    "MemoryWriteError",
    "DecryptionError",
    "StateError",
    "InvalidStateError",
    "StateTransitionError",
    "PhaseTimeoutError",
    "ActionError",
    "InvalidActionError",
    "ActionMaskedError",
    "DataError",
    "KnowledgeBaseError",
    "EntityNotFoundError",
    "NavigationError",
    "NavigationTimeoutError",
    "UnexpectedScreenError",
    "AgentError",
    "AgentNotReadyError",
]
