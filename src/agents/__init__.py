"""
Agents Package for Battle Factory RL System.

This package contains all agent implementations:
- Base abstract classes defining the agent interface
- Random agents for testing and baseline
- Interactive agents for manual play and debugging
- Trained agents (Drafter and Tactician) for actual gameplay

All agents implement the same interface so they can be
swapped seamlessly in the game loop.
"""

from .base import BaseDrafter, BaseTactician, AgentConfig
from .random_agents import RandomDrafter, RandomTactician, create_random_agents
from .interactive import (
    InteractiveDrafter, 
    InteractiveTactician, 
    create_interactive_agents,
    AssistedDrafter,
)

__all__ = [
    # Base
    "BaseDrafter",
    "BaseTactician",
    "AgentConfig",
    # Random
    "RandomDrafter",
    "RandomTactician",
    "create_random_agents",
    # Interactive
    "InteractiveDrafter",
    "InteractiveTactician",
    "create_interactive_agents",
    "AssistedDrafter",
]

