"""
Base Agent Interfaces for Battle Factory RL System.

Defines abstract base classes and protocols that all agent implementations
must follow, ensuring consistency between random, heuristic, and trained agents.

The interfaces match the signatures expected by TrainingController:
- Drafter: Called during draft and swap phases
- Tactician: Called during battle for turn-by-turn decisions
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional, Protocol, runtime_checkable
import numpy as np

from ..core.enums import GamePhase


# =============================================================================
# Protocol Definitions (for duck typing)
# =============================================================================

@runtime_checkable
class DrafterProtocol(Protocol):
    """
    Protocol for drafter agents.
    
    Drafters handle two key decisions:
    1. Initial draft: Select 3 Pokemon from 6 rentals
    2. Post-battle swap: Decide whether to swap a team member
    """
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        """
        Main policy interface.
        
        Args:
            obs: Observation array containing:
                - For draft: 6 rental Pokemon features + context
                - For swap: Current team + swap candidate + context
            phase: Current game phase (DRAFT_SCREEN or SWAP_SCREEN)
                
        Returns:
            Action array:
                - For draft: Shape (3,) with indices [0-5] for selections
                - For swap: Shape (1,) with value [0-3] for swap decision
        """
        ...


@runtime_checkable
class TacticianProtocol(Protocol):
    """
    Protocol for tactician agents.
    
    Tacticians make turn-by-turn battle decisions with recurrent state.
    """
    
    def __call__(
        self,
        obs: np.ndarray,
        phase: GamePhase,
        action_mask: np.ndarray,
    ) -> int:
        """
        Main policy interface.
        
        Args:
            obs: Battle observation array
            phase: Current game phase (IN_BATTLE)
            action_mask: Binary mask [6] of valid actions
            
        Returns:
            Action index 0-5 (Move 1-4, Switch 1-2)
        """
        ...


# =============================================================================
# Abstract Base Classes
# =============================================================================

class BaseDrafter(ABC):
    """
    Abstract base class for Drafter agents.
    
    The Drafter handles team selection and swap decisions. It uses a
    unified __call__ method that the controller invokes for both phases.
    
    Implementations should:
    - Handle both draft and swap observations
    - Return appropriate action shapes for each phase
    - Optionally track history for analysis
    """
    
    @abstractmethod
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        """
        Main policy interface called by controller.
        
        Args:
            obs: Phase-specific observation array
            phase: Current game phase
            
        Returns:
            Action array appropriate for the phase
        """
        pass
    
    @abstractmethod
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        """
        Select 3 Pokemon from 6 rental candidates.
        
        Args:
            rental_obs: Observation of 6 rental Pokemon features
            
        Returns:
            Array of 3 unique indices [0-5]
        """
        pass
    
    @abstractmethod
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        """
        Decide whether to swap a team member.
        
        Args:
            swap_obs: Observation of team + candidate
            
        Returns:
            0 = keep team, 1-3 = swap slot N
        """
        pass
    
    def reset(self) -> None:
        """Reset internal state for a new run."""
        pass


class BaseTactician(ABC):
    """
    Abstract base class for Tactician agents.
    
    The Tactician makes turn-by-turn battle decisions:
    - Actions 0-3: Use moves 1-4
    - Actions 4-5: Switch to bench Pokemon 1-2
    
    For recurrent agents (LSTM), hidden state is managed internally.
    """
    
    @abstractmethod
    def __call__(
        self, 
        obs: np.ndarray, 
        phase: GamePhase,
        action_mask: np.ndarray,
    ) -> int:
        """
        Main policy interface called by controller.
        
        Args:
            obs: Battle observation array
            phase: Current game phase
            action_mask: Binary mask of valid actions
                
        Returns:
            Action index 0-5
        """
        pass
    
    @abstractmethod
    def select_action(
        self,
        obs: np.ndarray,
        action_mask: np.ndarray,
    ) -> int:
        """
        Select a battle action.
        
        Args:
            obs: Battle observation
            action_mask: Valid action mask
            
        Returns:
            Action index 0-5
        """
        pass
    
    @abstractmethod
    def get_initial_hidden_state(self) -> Any:
        """Get initial hidden state for new battle."""
        pass
    
    def reset(self) -> None:
        """Reset for new battle."""
        pass
    
    def reset_run(self) -> None:
        """Reset for completely new run."""
        self.reset()


# =============================================================================
# Configuration
# =============================================================================

class AgentConfig:
    """
    Configuration for agent hyperparameters.
    
    Provides a unified way to configure both random and trained agents.
    """
    
    def __init__(
        self,
        # Tactician (LSTM) config
        lstm_hidden_size: int = 256,
        lstm_num_layers: int = 2,
        
        # Drafter (Transformer) config
        transformer_heads: int = 4,
        transformer_layers: int = 2,
        
        # Shared config
        embed_dim: int = 128,
        
        # Random agent config
        random_seed: Optional[int] = None,
        exploration_epsilon: float = 0.0,
        
        # Behavior config
        swap_probability: float = 0.3,
        move_bias: float = 0.7,
    ):
        self.lstm_hidden_size = lstm_hidden_size
        self.lstm_num_layers = lstm_num_layers
        self.transformer_heads = transformer_heads
        self.transformer_layers = transformer_layers
        self.embed_dim = embed_dim
        self.random_seed = random_seed
        self.exploration_epsilon = exploration_epsilon
        self.swap_probability = swap_probability
        self.move_bias = move_bias
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "lstm_hidden_size": self.lstm_hidden_size,
            "lstm_num_layers": self.lstm_num_layers,
            "transformer_heads": self.transformer_heads,
            "transformer_layers": self.transformer_layers,
            "embed_dim": self.embed_dim,
            "random_seed": self.random_seed,
            "exploration_epsilon": self.exploration_epsilon,
            "swap_probability": self.swap_probability,
            "move_bias": self.move_bias,
        }
