"""
Random Agent Implementations for Battle Factory.

These agents make random (but valid) decisions, useful for:
1. Testing the game loop end-to-end
2. Baseline performance comparison
3. Exploration during early training

Both agents implement the same interface as trained agents,
allowing seamless swapping in the BattleFactorySystem.
"""

import numpy as np
from typing import Any, Tuple, Optional
import logging

from .base import BaseDrafter, BaseTactician

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
        
        # During draft
        selections = drafter.select_team(rental_obs)  # Returns [2, 0, 5]
        
        # During swap  
        swap_action = drafter.decide_swap(swap_obs)  # Returns 0-3
        
        # Or use unified interface
        action = drafter(obs)  # System determines phase from obs shape
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
            seed: Random seed for reproducibility (None = random)
            swap_probability: Probability of swapping when offered (0.0-1.0)
            verbose: Whether to log decisions
        """
        self.rng = np.random.default_rng(seed)
        self.swap_probability = swap_probability
        self.verbose = verbose
        
        # Track decisions for analysis
        self.draft_history = []
        self.swap_history = []
        
    def __call__(self, obs: np.ndarray) -> np.ndarray:
        """
        Unified policy interface for both draft and swap.
        
        Determines phase based on observation structure:
        - Draft obs has 6 rental features + context (larger)
        - Swap obs has team + candidate + context (smaller)
        
        Args:
            obs: Observation array
            
        Returns:
            Action array appropriate for the phase
        """
        # Heuristic: Draft observations are larger (6 rentals)
        # Swap observations are smaller (3 team + 1 candidate)
        # Using 25 as threshold (draft has ~20 rental features + context)
        if len(obs) > 25:
            # Draft phase
            return self.select_team(obs)
        else:
            # Swap phase
            return np.array([self.decide_swap(obs)])
    
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        """
        Randomly select 3 Pokemon from 6 rental candidates.
        
        Args:
            rental_obs: Observation containing rental Pokemon features
            
        Returns:
            Array of 3 unique indices [0-5] in selection order
        """
        # Select 3 unique indices from [0, 1, 2, 3, 4, 5]
        selections = self.rng.choice(6, size=3, replace=False)
        
        if self.verbose:
            logger.info(f"[RandomDrafter] Draft selections: {selections}")
            
        self.draft_history.append(selections.copy())
        return selections
    
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        """
        Randomly decide whether to swap a team member.
        
        With probability `swap_probability`, chooses to swap.
        When swapping, randomly picks which slot to replace.
        
        Args:
            swap_obs: Observation of team + swap candidate
            
        Returns:
            0 = keep team, 1-3 = swap slot N
        """
        # Decide whether to swap at all
        if self.rng.random() < self.swap_probability:
            # Choose which slot to swap (1, 2, or 3)
            swap_slot = self.rng.integers(1, 4)  # [1, 2, 3]
            
            if self.verbose:
                logger.info(f"[RandomDrafter] Swapping slot {swap_slot}")
        else:
            swap_slot = 0  # Keep team
            
            if self.verbose:
                logger.info("[RandomDrafter] Keeping team (no swap)")
                
        self.swap_history.append(swap_slot)
        return swap_slot
    
    def reset(self) -> None:
        """Reset history for a new run."""
        self.draft_history.clear()
        self.swap_history.clear()
        
    def get_stats(self) -> dict:
        """Get statistics about decisions made."""
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
    - Actions 4-5: Switch to Pokemon 1-2 on bench
    
    Respects the action mask to only choose valid actions
    (e.g., won't select a move with 0 PP or switch to fainted Pokemon).
    
    Usage:
        tactician = RandomTactician(seed=42)
        
        # Reset at battle start
        hidden = tactician.reset()
        
        # Each turn
        action, hidden = tactician(obs, hidden, action_mask)
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
            seed: Random seed for reproducibility (None = random)
            move_bias: Probability weight towards moves vs switches (0.0-1.0)
                       Higher = prefer moves, lower = more switches
            verbose: Whether to log decisions
        """
        self.rng = np.random.default_rng(seed)
        self.move_bias = move_bias
        self.verbose = verbose
        
        # Track decisions for analysis
        self.action_history = []
        self.turn_count = 0
        
    def __call__(
        self,
        obs: np.ndarray,
        hidden_state: Any,
        action_mask: np.ndarray,
    ) -> Tuple[int, Any]:
        """
        Main policy interface - delegates to select_action.
        
        Args:
            obs: Battle observation
            hidden_state: Previous hidden state (unused for random)
            action_mask: Valid action mask [6]
            
        Returns:
            (action, new_hidden_state)
        """
        return self.select_action(obs, hidden_state, action_mask)
    
    def select_action(
        self,
        obs: np.ndarray,
        hidden_state: Any,
        action_mask: np.ndarray,
    ) -> Tuple[int, Any]:
        """
        Select a random valid battle action.
        
        Uses action mask to filter invalid actions.
        Optionally biases towards moves over switches.
        
        Args:
            obs: Battle observation array
            hidden_state: LSTM hidden state (unused - random agent)
            action_mask: Binary mask [6] of valid actions
            
        Returns:
            Tuple of (action, hidden_state):
                - action: Valid action index 0-5
                - hidden_state: Unchanged (no recurrence in random)
        """
        # Ensure mask is valid
        if action_mask is None or len(action_mask) != 6:
            action_mask = np.ones(6)
        
        # Get valid actions
        valid_actions = np.where(action_mask > 0)[0]
        
        if len(valid_actions) == 0:
            # Fallback: if no valid actions (shouldn't happen), pick move 1
            logger.warning("[RandomTactician] No valid actions! Defaulting to 0")
            action = 0
        else:
            # Optionally bias towards moves (0-3) vs switches (4-5)
            if self.move_bias > 0:
                # Separate moves and switches
                valid_moves = [a for a in valid_actions if a < 4]
                valid_switches = [a for a in valid_actions if a >= 4]
                
                # Decide category first, then pick within
                if valid_moves and valid_switches:
                    if self.rng.random() < self.move_bias:
                        action = self.rng.choice(valid_moves)
                    else:
                        action = self.rng.choice(valid_switches)
                elif valid_moves:
                    action = self.rng.choice(valid_moves)
                else:
                    action = self.rng.choice(valid_switches)
            else:
                # Uniform random over valid actions
                action = self.rng.choice(valid_actions)
        
        action = int(action)
        self.turn_count += 1
        self.action_history.append(action)
        
        if self.verbose:
            action_names = ["Move1", "Move2", "Move3", "Move4", "Switch1", "Switch2"]
            logger.info(f"[RandomTactician] Turn {self.turn_count}: {action_names[action]} "
                       f"(mask={action_mask.tolist()})")
        
        # Hidden state unchanged for random agent
        return action, hidden_state
    
    def get_initial_hidden_state(self) -> Any:
        """
        Get initial hidden state.
        
        For random agent, this is None since we don't use recurrence.
        Trained agents would return zero-initialized LSTM states.
        
        Returns:
            None (random agent has no hidden state)
        """
        return None
    
    def reset(self) -> Any:
        """
        Reset for a new battle.
        
        Returns:
            Initial hidden state (None for random)
        """
        self.turn_count = 0
        # Note: Don't clear action_history here - keep across battles
        # for full run statistics
        return self.get_initial_hidden_state()
    
    def reset_run(self) -> None:
        """Reset all history for a completely new run."""
        self.turn_count = 0
        self.action_history.clear()
        
    def get_stats(self) -> dict:
        """Get statistics about actions taken."""
        if not self.action_history:
            return {"total_actions": 0}
            
        actions = np.array(self.action_history)
        moves = np.sum(actions < 4)
        switches = np.sum(actions >= 4)
        
        # Count each action type
        action_counts = {i: np.sum(actions == i) for i in range(6)}
        
        return {
            "total_actions": len(actions),
            "total_moves": int(moves),
            "total_switches": int(switches),
            "move_rate": float(moves / len(actions)),
            "action_distribution": action_counts,
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_random_agents(
    seed: Optional[int] = None,
    verbose: bool = False,
) -> Tuple[RandomDrafter, RandomTactician]:
    """
    Create a pair of random agents for testing.
    
    Args:
        seed: Base random seed (drafter=seed, tactician=seed+1)
        verbose: Whether agents should log decisions
        
    Returns:
        (RandomDrafter, RandomTactician) tuple
    """
    drafter_seed = seed if seed is not None else None
    tactician_seed = seed + 1 if seed is not None else None
    
    drafter = RandomDrafter(seed=drafter_seed, verbose=verbose)
    tactician = RandomTactician(seed=tactician_seed, verbose=verbose)
    
    return drafter, tactician

