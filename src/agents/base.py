"""
Base Agent Interfaces for Battle Factory RL System.

Defines abstract base classes that all agent implementations must follow.
This ensures consistency between random, heuristic, and trained agents,
allowing seamless swapping during development and testing.

The interfaces match the signatures expected by BattleFactorySystem:
- Drafter: Called during draft and swap phases
- Tactician: Called during battle for turn-by-turn decisions
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional
import numpy as np


class BaseDrafter(ABC):
    """
    Abstract base class for Drafter agents.
    
    The Drafter handles two key decisions in Battle Factory:
    1. Initial draft: Select 3 Pokemon from 6 rental candidates
    2. Post-battle swap: Decide whether to swap a team member
    
    The interface uses a unified __call__ method that the system
    invokes for both draft and swap phases. The agent must determine
    the appropriate action based on the observation structure.
    """
    
    @abstractmethod
    def __call__(self, obs: np.ndarray) -> np.ndarray:
        """
        Main policy interface called by BattleFactorySystem.
        
        Args:
            obs: Observation array containing:
                - For draft: 6 rental Pokemon features + context
                - For swap: Current team + swap candidate + context
                
        Returns:
            Action array:
                - For draft: np.ndarray of shape (3,) with indices [0-5]
                  representing which 3 Pokemon to select
                - For swap: np.ndarray of shape (1,) with value [0-3]
                  where 0=keep team, 1-3=swap slot N with candidate
        """
        pass
    
    @abstractmethod
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        """
        Select 3 Pokemon from 6 rental candidates.
        
        Args:
            rental_obs: Observation of 6 rental Pokemon features
            
        Returns:
            Array of 3 unique indices [0-5] representing selections
        """
        pass
    
    @abstractmethod
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        """
        Decide whether to swap a team member after winning.
        
        Args:
            swap_obs: Observation of current team + swap candidate
            
        Returns:
            Swap action:
                0 = Keep current team (no swap)
                1 = Swap slot 1 with candidate
                2 = Swap slot 2 with candidate
                3 = Swap slot 3 with candidate
        """
        pass
    
    def reset(self) -> None:
        """
        Reset any internal state for a new run.
        
        Override if the drafter maintains state across decisions.
        """
        pass


class BaseTactician(ABC):
    """
    Abstract base class for Tactician agents.
    
    The Tactician makes turn-by-turn battle decisions:
    - Select moves (actions 0-3)
    - Switch Pokemon (actions 4-5)
    
    Uses recurrent architecture (LSTM) to remember battle history,
    so the interface includes hidden state management.
    """
    
    @abstractmethod
    def __call__(
        self, 
        obs: np.ndarray, 
        hidden_state: Any,
        action_mask: np.ndarray,
    ) -> Tuple[int, Any]:
        """
        Main policy interface called by BattleFactorySystem.
        
        Args:
            obs: Battle observation array containing:
                - Player active Pokemon features
                - Enemy active Pokemon features  
                - Battle context (weather, turn, streak)
            hidden_state: LSTM hidden state from previous step
                (None on first turn of battle)
            action_mask: Binary mask of shape (6,) indicating valid actions
                [Move1, Move2, Move3, Move4, Switch1, Switch2]
                1.0 = valid, 0.0 = invalid
                
        Returns:
            Tuple of (action, new_hidden_state):
                - action: Integer 0-5 representing the chosen action
                - new_hidden_state: Updated LSTM hidden state
        """
        pass
    
    @abstractmethod
    def select_action(
        self,
        obs: np.ndarray,
        hidden_state: Any,
        action_mask: np.ndarray,
    ) -> Tuple[int, Any]:
        """
        Select a battle action given the current state.
        
        This is the core decision method. The __call__ method
        typically just delegates to this.
        
        Args:
            obs: Battle observation array
            hidden_state: LSTM hidden state
            action_mask: Valid action mask
            
        Returns:
            Tuple of (action, new_hidden_state)
        """
        pass
    
    @abstractmethod
    def get_initial_hidden_state(self) -> Any:
        """
        Get the initial hidden state for a new battle.
        
        Returns:
            Initial LSTM hidden state (typically zeros)
        """
        pass
    
    def reset(self) -> Any:
        """
        Reset for a new battle and return initial hidden state.
        
        Returns:
            Initial hidden state for the new battle
        """
        return self.get_initial_hidden_state()


class AgentConfig:
    """
    Configuration container for agent hyperparameters.
    
    Provides a unified way to configure both random and trained agents.
    """
    
    def __init__(
        self,
        # Tactician config
        lstm_hidden_size: int = 256,
        lstm_num_layers: int = 2,
        
        # Drafter config  
        transformer_heads: int = 4,
        transformer_layers: int = 2,
        
        # Shared config
        embed_dim: int = 128,
        
        # Random agent config
        random_seed: Optional[int] = None,
        exploration_epsilon: float = 0.0,
    ):
        self.lstm_hidden_size = lstm_hidden_size
        self.lstm_num_layers = lstm_num_layers
        self.transformer_heads = transformer_heads
        self.transformer_layers = transformer_layers
        self.embed_dim = embed_dim
        self.random_seed = random_seed
        self.exploration_epsilon = exploration_epsilon

