"""
Agents Package - RL agent implementations.

Provides various agent implementations for Battle Factory:
- Random agents for testing and baselines
- Interactive agents for manual play
- (Future) Trained agents loaded from checkpoints
"""

from __future__ import annotations

from .base import (
    BaseDrafter,
    BaseTactician,
    DrafterProtocol,
    TacticianProtocol,
    AgentConfig,
)

from .random_agents import (
    RandomDrafter,
    RandomTactician,
    create_random_agents,
)

from .interactive import (
    InteractiveDrafter,
    InteractiveTactician,
    create_interactive_agents,
)

__all__ = [
    # Base classes and protocols
    "BaseDrafter",
    "BaseTactician",
    "DrafterProtocol",
    "TacticianProtocol",
    "AgentConfig",
    # Random agents
    "RandomDrafter",
    "RandomTactician",
    "create_random_agents",
    # Interactive agents
    "InteractiveDrafter",
    "InteractiveTactician",
    "create_interactive_agents",
]
