"""
Random Agent Implementations for Battle Factory.

These agents make random (but valid) decisions, useful for:
1. Testing the game loop end-to-end
2. Baseline performance comparison
3. Exploration during early training

Both agents implement the standardized interfaces expected by
TrainingController, allowing seamless swapping with trained agents.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Tuple, Optional, Dict
import logging

from .base import BaseDrafter, BaseTactician, AgentConfig
from ..core.enums import GamePhase

logger = logging.getLogger(__name__)


class RandomDrafter(BaseDrafter):
    """
    Random policy for draft and swap decisions.
    
    Draft Phase:
        Randomly selects 3 unique Pokemon from the 6 rental candidates.
        
    Swap Phase:
        Randomly decides whether to keep the team or swap one member.
        Has a configurable probability to prefer keeping the team.
    
    Usage:
        drafter = RandomDrafter(seed=42, swap_probability=0.3)
        
        # Called by controller
        action = drafter(obs, GamePhase.DRAFT_SCREEN)
    """
    
    def __init__(
        self,
        seed: Optional[int] = None,
        swap_probability: float = 0.3,
        verbose: bool = False,
    ):
        """
        Initialize RandomDrafter.
        
        Args:
            seed: Random seed for reproducibility
            swap_probability: Probability of swapping when offered (0-1)
            verbose: Log decisions
        """
        self.rng = np.random.default_rng(seed)
        self.swap_probability = swap_probability
        self.verbose = verbose
        
        # Decision history
        self.draft_history: list[np.ndarray] = []
        self.swap_history: list[int] = []
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        """
        Main policy interface.
        
        Args:
            obs: Observation array
            phase: Current game phase
            
        Returns:
            Action array for the phase
        """
        if phase == GamePhase.DRAFT_SCREEN:
            return self.select_team(obs)
        elif phase == GamePhase.SWAP_SCREEN:
            return np.array([self.decide_swap(obs)])
        else:
            # Fallback: use observation size heuristic
            if len(obs) > 15:
                return self.select_team(obs)
            else:
                return np.array([self.decide_swap(obs)])
    
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        """
        Randomly select 3 Pokemon from 6 rentals.
        
        Args:
            rental_obs: Rental Pokemon observation
            
        Returns:
            Array of 3 unique indices [0-5]
        """
        selections = self.rng.choice(6, size=3, replace=False)
        
        if self.verbose:
            logger.info(f"[RandomDrafter] Draft: {selections}")
        
        self.draft_history.append(selections.copy())
        return selections
    
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        """
        Randomly decide whether to swap.
        
        Args:
            swap_obs: Swap observation
            
        Returns:
            0=keep, 1-3=swap slot N
        """
        if self.rng.random() < self.swap_probability:
            swap_slot = int(self.rng.integers(1, 4))
            if self.verbose:
                logger.info(f"[RandomDrafter] Swap slot {swap_slot}")
        else:
            swap_slot = 0
            if self.verbose:
                logger.info("[RandomDrafter] Keep team")
        
        self.swap_history.append(swap_slot)
        return swap_slot
    
    def reset(self) -> None:
        """Reset history."""
        self.draft_history.clear()
        self.swap_history.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get decision statistics."""
        total_swaps = sum(1 for s in self.swap_history if s > 0)
        return {
            "total_drafts": len(self.draft_history),
            "total_swap_decisions": len(self.swap_history),
            "actual_swaps": total_swaps,
            "swap_rate": total_swaps / max(len(self.swap_history), 1),
        }


class RandomTactician(BaseTactician):
    """
    Random policy for battle actions with action masking.
    
    Randomly selects valid actions during battle:
    - Actions 0-3: Use move 1-4
    - Actions 4-5: Switch to bench Pokemon 1-2
    
    Respects action mask to only choose valid actions.
    
    Usage:
        tactician = RandomTactician(seed=42, move_bias=0.7)
        
        # Called by controller
        action = tactician(obs, GamePhase.IN_BATTLE, mask)
    """
    
    def __init__(
        self,
        seed: Optional[int] = None,
        move_bias: float = 0.7,
        verbose: bool = False,
    ):
        """
        Initialize RandomTactician.
        
        Args:
            seed: Random seed for reproducibility
            move_bias: Probability weight towards moves vs switches (0-1)
            verbose: Log decisions
        """
        self.rng = np.random.default_rng(seed)
        self.move_bias = move_bias
        self.verbose = verbose
        
        # Decision history
        self.action_history: list[int] = []
        self.turn_count = 0
        
        # Hidden state (None for random agent)
        self._hidden_state = None
    
    def __call__(
        self,
        obs: np.ndarray,
        phase: GamePhase,
        action_mask: np.ndarray,
    ) -> int:
        """
        Main policy interface.
        
        Args:
            obs: Battle observation
            phase: Current game phase
            action_mask: Valid action mask
            
        Returns:
            Action index 0-5
        """
        return self.select_action(obs, action_mask)
    
    def select_action(
        self,
        obs: np.ndarray,
        action_mask: np.ndarray,
    ) -> int:
        """
        Select a random valid action.
        
        Args:
            obs: Battle observation
            action_mask: Valid action mask [6]
            
        Returns:
            Action index 0-5
        """
        # Ensure valid mask
        if action_mask is None or len(action_mask) != 6:
            action_mask = np.ones(6)
        
        valid_actions = np.where(action_mask > 0)[0]
        
        if len(valid_actions) == 0:
            logger.warning("[RandomTactician] No valid actions, defaulting to 0")
            action = 0
        elif self.move_bias > 0:
            # Bias towards moves
            valid_moves = [a for a in valid_actions if a < 4]
            valid_switches = [a for a in valid_actions if a >= 4]
            
            if valid_moves and valid_switches:
                if self.rng.random() < self.move_bias:
                    action = int(self.rng.choice(valid_moves))
                else:
                    action = int(self.rng.choice(valid_switches))
            elif valid_moves:
                action = int(self.rng.choice(valid_moves))
            else:
                action = int(self.rng.choice(valid_switches))
        else:
            action = int(self.rng.choice(valid_actions))
        
        self.turn_count += 1
        self.action_history.append(action)
        
        if self.verbose:
            names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
            logger.info(f"[RandomTactician] Turn {self.turn_count}: {names[action]}")
        
        return action
    
    def get_initial_hidden_state(self) -> Any:
        """Return None (no hidden state for random)."""
        return None
    
    def reset(self) -> None:
        """Reset for new battle."""
        self.turn_count = 0
        self._hidden_state = None
    
    def reset_run(self) -> None:
        """Reset all state."""
        self.turn_count = 0
        self.action_history.clear()
        self._hidden_state = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get action statistics."""
        if not self.action_history:
            return {"total_actions": 0}
        
        actions = np.array(self.action_history)
        moves = int(np.sum(actions < 4))
        switches = int(np.sum(actions >= 4))
        
        return {
            "total_actions": len(actions),
            "total_moves": moves,
            "total_switches": switches,
            "move_rate": float(moves / len(actions)),
            "action_distribution": {i: int(np.sum(actions == i)) for i in range(6)},
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_random_agents(
    seed: Optional[int] = None,
    verbose: bool = False,
    swap_probability: float = 0.3,
    move_bias: float = 0.7,
) -> Tuple[RandomDrafter, RandomTactician]:
    """
    Create a pair of random agents.
    
    Args:
        seed: Base random seed (drafter=seed, tactician=seed+1)
        verbose: Log decisions
        swap_probability: Drafter swap probability
        move_bias: Tactician move vs switch bias
        
    Returns:
        (RandomDrafter, RandomTactician) tuple
    """
    drafter_seed = seed if seed is not None else None
    tactician_seed = seed + 1 if seed is not None else None
    
    drafter = RandomDrafter(
        seed=drafter_seed,
        swap_probability=swap_probability,
        verbose=verbose
    )
    tactician = RandomTactician(
        seed=tactician_seed,
        move_bias=move_bias,
        verbose=verbose
    )
    
    return drafter, tactician
