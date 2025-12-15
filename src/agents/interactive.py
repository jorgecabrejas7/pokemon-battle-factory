"""
Interactive Agents for Battle Factory.

These agents prompt the user for decisions, useful for:
1. Manual testing and debugging
2. Human-in-the-loop gameplay
3. Data collection for imitation learning

Both agents implement the standardized interface expected by TrainingController.
"""

from __future__ import annotations

import numpy as np
from typing import Any, Tuple, Optional
import logging

from .base import BaseDrafter, BaseTactician
from ..core.enums import GamePhase

logger = logging.getLogger(__name__)


# =============================================================================
# Action Names for Display
# =============================================================================

BATTLE_ACTION_NAMES = [
    "Move 1",
    "Move 2", 
    "Move 3",
    "Move 4",
    "Switch to Pokemon 2",
    "Switch to Pokemon 3",
]

SWAP_ACTION_NAMES = [
    "Keep current team",
    "Swap slot 1",
    "Swap slot 2",
    "Swap slot 3",
]


# =============================================================================
# Interactive Drafter
# =============================================================================

class InteractiveDrafter(BaseDrafter):
    """
    Interactive drafter that prompts user for decisions.
    
    During draft: Shows rental Pokemon and asks which 3 to select.
    During swap: Shows team and candidate, asks whether to swap.
    
    Usage:
        drafter = InteractiveDrafter()
        action = drafter(obs, GamePhase.DRAFT_SCREEN)
    """
    
    def __init__(self, show_obs: bool = True):
        """
        Initialize interactive drafter.
        
        Args:
            show_obs: Whether to display observation details
        """
        self.show_obs = show_obs
    
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
            # Fallback: use observation size
            if len(obs) > 25:
                return self.select_team(obs)
            else:
                return np.array([self.decide_swap(obs)])
    
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        """
        Prompt user to select 3 Pokemon from 6 rentals.
        """
        print("\n" + "="*50)
        print("DRAFT PHASE - Select 3 Pokemon")
        print("="*50)
        
        if self.show_obs:
            print("\nRental Pokemon (normalized features):")
            for i in range(6):
                base = i * 3
                if base + 2 < len(rental_obs):
                    mon_id = rental_obs[base] * 900
                    ivs = rental_obs[base + 1] * 31
                    ability = rental_obs[base + 2] * 2
                    print(f"  [{i}] ID: {mon_id:.0f}, IVs: {ivs:.0f}, Ability: {ability:.0f}")
                else:
                    print(f"  [{i}] (no data)")
        
        print("\nEnter 3 Pokemon indices (0-5), separated by spaces:")
        
        while True:
            try:
                user_input = input("> ").strip()
                
                # Parse input
                selections = [int(x) for x in user_input.split()]
                
                # Validate
                if len(selections) != 3:
                    print("Please enter exactly 3 numbers.")
                    continue
                
                if not all(0 <= s <= 5 for s in selections):
                    print("Numbers must be 0-5.")
                    continue
                
                if len(set(selections)) != 3:
                    print("Please select 3 different Pokemon.")
                    continue
                
                print(f"Selected: {selections}")
                return np.array(selections)
                
            except ValueError:
                print("Invalid input. Enter 3 numbers like: 0 2 4")
            except KeyboardInterrupt:
                print("\nUsing random selection...")
                return np.random.choice(6, size=3, replace=False)
    
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        """
        Prompt user for swap decision.
        """
        print("\n" + "="*50)
        print("SWAP PHASE - Trade Pokemon?")
        print("="*50)
        
        print("\nOptions:")
        for i, name in enumerate(SWAP_ACTION_NAMES):
            print(f"  [{i}] {name}")
        
        print("\nEnter choice (0-3):")
        
        while True:
            try:
                user_input = input("> ").strip()
                choice = int(user_input)
                
                if 0 <= choice <= 3:
                    print(f"Selected: {SWAP_ACTION_NAMES[choice]}")
                    return choice
                else:
                    print("Please enter 0-3.")
                    
            except ValueError:
                print("Invalid input. Enter a number 0-3.")
            except KeyboardInterrupt:
                print("\nKeeping team (no swap)...")
                return 0
    
    def reset(self):
        """No state to reset."""
        pass


# =============================================================================
# Interactive Tactician
# =============================================================================

class InteractiveTactician(BaseTactician):
    """
    Interactive tactician that prompts user for battle decisions.
    
    Shows current battle state, valid actions, and prompts for choice.
    
    Usage:
        tactician = InteractiveTactician()
        action = tactician(obs, GamePhase.IN_BATTLE, mask)
    """
    
    def __init__(self, show_obs: bool = True, show_mask: bool = True):
        """
        Initialize interactive tactician.
        
        Args:
            show_obs: Whether to display observation details
            show_mask: Whether to highlight invalid actions
        """
        self.show_obs = show_obs
        self.show_mask = show_mask
        self.turn_count = 0
    
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
        Prompt user for battle action.
        """
        self.turn_count += 1
        
        print("\n" + "-"*50)
        print(f"BATTLE - Turn {self.turn_count}")
        print("-"*50)
        
        if self.show_obs and len(obs) >= 15:
            # Parse observation vector
            print("\nPlayer Pokemon:")
            print(f"  Species ID: {obs[0] * 400:.0f}")
            print(f"  HP: {obs[1] * 100:.0f}%")
            print(f"  Atk/Def/SpA/SpD/Spe: {obs[2]*255:.0f}/{obs[3]*255:.0f}/"
                  f"{obs[4]*255:.0f}/{obs[5]*255:.0f}/{obs[6]*255:.0f}")
            
            print("\nEnemy Pokemon:")
            print(f"  Species ID: {obs[12] * 400:.0f}")
            print(f"  HP: {obs[13] * 100:.0f}%")
        
        # Show actions
        print("\nActions:")
        valid_actions = []
        for i, name in enumerate(BATTLE_ACTION_NAMES):
            if action_mask is not None and len(action_mask) > i:
                is_valid = action_mask[i] > 0
            else:
                is_valid = True
            
            if is_valid:
                valid_actions.append(i)
                print(f"  [{i}] {name}")
            elif self.show_mask:
                print(f"  [{i}] {name} (invalid)")
        
        print(f"\nEnter action (valid: {valid_actions}):")
        
        while True:
            try:
                user_input = input("> ").strip()
                action = int(user_input)
                
                if action in valid_actions:
                    print(f"Selected: {BATTLE_ACTION_NAMES[action]}")
                    return action
                else:
                    print(f"Invalid action. Choose from: {valid_actions}")
                    
            except ValueError:
                print("Invalid input. Enter a number.")
            except KeyboardInterrupt:
                print("\nUsing random valid action...")
                return int(np.random.choice(valid_actions)) if valid_actions else 0
    
    def get_initial_hidden_state(self) -> Any:
        """No hidden state for interactive."""
        return None
    
    def reset(self) -> None:
        """Reset turn counter."""
        self.turn_count = 0


# =============================================================================
# Factory Functions
# =============================================================================

def create_interactive_agents(
    show_obs: bool = True,
) -> Tuple[InteractiveDrafter, InteractiveTactician]:
    """
    Create a pair of interactive agents.
    
    Args:
        show_obs: Whether to display observations
        
    Returns:
        (InteractiveDrafter, InteractiveTactician) tuple
    """
    return (
        InteractiveDrafter(show_obs=show_obs),
        InteractiveTactician(show_obs=show_obs),
    )


# =============================================================================
# Hybrid Agents (Interactive with AI assistance)
# =============================================================================

class AssistedDrafter(BaseDrafter):
    """
    Drafter that shows AI suggestions but lets user override.
    
    Useful for training with human feedback.
    """
    
    def __init__(self, ai_drafter: BaseDrafter, auto_accept: bool = False):
        """
        Args:
            ai_drafter: AI agent to provide suggestions
            auto_accept: If True, accept AI suggestion on Enter
        """
        self.ai_drafter = ai_drafter
        self.auto_accept = auto_accept
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        if phase == GamePhase.DRAFT_SCREEN:
            return self.select_team(obs)
        else:
            return np.array([self.decide_swap(obs)])
    
    def select_team(self, rental_obs: np.ndarray) -> np.ndarray:
        # Get AI suggestion
        ai_selection = self.ai_drafter.select_team(rental_obs)
        
        print("\n" + "="*50)
        print("DRAFT PHASE - AI Assisted")
        print("="*50)
        print(f"\nAI suggests: {ai_selection}")
        
        if self.auto_accept:
            print("Press Enter to accept, or enter your own selection:")
        else:
            print("Enter your selection (or press Enter for AI):")
        
        user_input = input("> ").strip()
        
        if not user_input:
            print("Using AI suggestion")
            return ai_selection
        
        try:
            selections = [int(x) for x in user_input.split()]
            if len(selections) == 3 and all(0 <= s <= 5 for s in selections):
                return np.array(selections)
        except Exception:
            pass
        
        print("Invalid input, using AI suggestion")
        return ai_selection
    
    def decide_swap(self, swap_obs: np.ndarray) -> int:
        ai_swap = self.ai_drafter.decide_swap(swap_obs)
        
        print(f"\nAI suggests: {SWAP_ACTION_NAMES[ai_swap]}")
        print("Enter your choice (0-3) or press Enter for AI:")
        
        user_input = input("> ").strip()
        
        if not user_input:
            return ai_swap
        
        try:
            choice = int(user_input)
            if 0 <= choice <= 3:
                return choice
        except Exception:
            pass
        
        return ai_swap
    
    def reset(self):
        self.ai_drafter.reset()
