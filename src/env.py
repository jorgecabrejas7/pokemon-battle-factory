"""
Gymnasium Environments for Battle Factory RL System.

Provides RLlib-compatible environments for:
1. TacticianEnv: Battle decisions (Move 1-4, Switch 1-2)
2. DrafterEnv: Team selection and swaps
3. BattleFactoryEnv: Unified hierarchical environment

Uses Gymnasium (not old gym) for RLlib 2.x compatibility.

All environments use the new modular controller architecture for
consistent behavior and proper state management.
"""

from __future__ import annotations

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Tuple, Dict, Any, Optional, List
import logging

from .backends.emerald.backend import EmeraldBackend
from .controller import TrainingController, PhaseResult, TurnResult
from .core.enums import GamePhase, BattleOutcome
from .core.dataclasses import BattleState, FactoryState
from .config import config

logger = logging.getLogger(__name__)


# =============================================================================
# Observation/Action Space Dimensions
# =============================================================================

# Battle observation features (for Tactician)
BATTLE_OBS_DIM = config.dimensions.battle_obs_dim
BATTLE_NUM_ACTIONS = config.dimensions.battle_num_actions  # Move 1-4, Switch 1-2

# Draft observation features (for Drafter)
DRAFT_OBS_DIM = config.dimensions.draft_obs_dim
DRAFT_NUM_CANDIDATES = config.dimensions.draft_num_candidates
DRAFT_TEAM_SIZE = config.dimensions.draft_team_size

# Swap observation features
SWAP_OBS_DIM = config.dimensions.swap_obs_dim
SWAP_NUM_ACTIONS = config.dimensions.swap_num_actions


# =============================================================================
# Tactician Environment
# =============================================================================

class TacticianEnv(gym.Env):
    """
    Environment for the Tactician (battle) agent.
    
    Handles turn-by-turn battle decisions with:
    - Action masking for invalid moves
    - LSTM-friendly observation format
    - Shaped rewards for damage/faints
    
    Compatible with RLlib's RecurrentPPO.
    
    Observation Space:
        Dict containing:
        - "obs": Battle state features [BATTLE_OBS_DIM]
        - "action_mask": Valid action mask [6]
    
    Action Space:
        Discrete(6): Move 1-4, Switch 1-2
    
    Rewards:
        - Per-turn: Damage dealt (+), damage taken (-)
        - Win: +10 * (1 + streak * 0.1)
        - Loss: -10 * (1 + streak * 0.2)
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config_dict = config_dict or {}
        
        # Backend/controller (can be injected for testing)
        backend = config_dict.get("backend")
        self.controller = config_dict.get("controller") or TrainingController(
            backend=backend,
            verbose=config_dict.get("verbose", False),
        )
        self._connected = False
        
        # Config
        self.max_turns = config_dict.get("max_turns", config.game.max_streak * 20)
        self.reward_scale = config_dict.get("reward_scale", 1.0)
        self.auto_connect = config_dict.get("auto_connect", True)
        
        # Action space: Move 1-4, Switch 1-2
        self.action_space = spaces.Discrete(BATTLE_NUM_ACTIONS)
        
        # Observation space: Dict with features and action mask
        self.observation_space = spaces.Dict({
            "obs": spaces.Box(
                low=-1.0, high=1.0,
                shape=(BATTLE_OBS_DIM,),
                dtype=np.float32
            ),
            "action_mask": spaces.Box(
                low=0.0, high=1.0,
                shape=(BATTLE_NUM_ACTIONS,),
                dtype=np.float32
            ),
        })
        
        # State tracking
        self.current_turn = 0
        self.episode_reward = 0.0
        self._last_obs = None
    
    def _ensure_connected(self) -> None:
        """Ensure controller is connected."""
        if not self._connected and self.auto_connect:
            try:
                self.controller.connect()
                self._connected = True
            except Exception as e:
                logger.warning(f"Auto-connect failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Build observation dict with action mask."""
        obs_vec = self.controller.get_battle_observation()
        
        # Pad/truncate to fixed size
        if len(obs_vec) < BATTLE_OBS_DIM:
            obs_vec = np.pad(obs_vec, (0, BATTLE_OBS_DIM - len(obs_vec)))
        else:
            obs_vec = obs_vec[:BATTLE_OBS_DIM]
        
        action_mask = self.controller.get_action_mask()
        
        return {
            "obs": obs_vec.astype(np.float32),
            "action_mask": action_mask.astype(np.float32),
        }
    
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Reset for a new battle."""
        super().reset(seed=seed)
        
        self._ensure_connected()
        self.controller.reset_battle()
        
        self.current_turn = 0
        self.episode_reward = 0.0
        
        # Wait for battle to start if needed
        if self.controller.phase == GamePhase.BATTLE_READY:
            self.controller.wait_for_battle_start()
        
        obs = self._get_observation()
        self._last_obs = obs
        
        info = {
            "turn": self.current_turn,
            "streak": self.controller.run_stats.win_streak,
            "phase": self.controller.phase.name,
        }
        
        return obs, info
    
    def step(
        self,
        action: int,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute battle action.
        
        Args:
            action: Action index (0-5)
            
        Returns:
            (obs, reward, terminated, truncated, info)
        """
        # Execute action using controller
        result = self.controller.step_turn(action)
        reward = result.reward * self.reward_scale
        
        self.current_turn += 1
        self.episode_reward += reward
        
        # Check truncation (max turns)
        truncated = self.current_turn >= self.max_turns
        terminated = result.battle_ended
        
        # Get new observation
        obs = self._get_observation()
        self._last_obs = obs
        
        info = {
            "turn": self.current_turn,
            "streak": self.controller.run_stats.win_streak,
            "episode_reward": self.episode_reward,
            "battle_outcome": result.outcome.name if result.outcome else "ONGOING",
            "action_taken": result.action,
            "damage_dealt": result.data.get("damage_dealt", 0),
            "damage_taken": result.data.get("damage_taken", 0),
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self) -> None:
        """Render current state."""
        if self._last_obs is not None:
            logger.info(
                f"Turn {self.current_turn} | "
                f"Streak {self.controller.run_stats.win_streak} | "
                f"Phase {self.controller.phase.name}"
            )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._connected:
            self.controller.disconnect()
            self._connected = False


# =============================================================================
# Drafter Environment
# =============================================================================

class DrafterEnv(gym.Env):
    """
    Environment for the Drafter (selection) agent.
    
    Handles:
    - Initial team selection (3 from 6)
    - Post-battle swaps
    
    Observation Space:
        Dict containing:
        - "obs": Rental/team features [DRAFT_OBS_DIM or SWAP_OBS_DIM]
        - "action_mask": Valid selection mask [6 or 4]
    
    Action Space:
        - Draft mode: MultiDiscrete([6, 6, 6]) for selecting 3 Pokemon
        - Swap mode: Discrete(4) for keep/swap decision
    
    Rewards:
        Delayed - based on subsequent battle outcomes
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config_dict = config_dict or {}
        
        # Backend/controller
        backend = config_dict.get("backend")
        self.controller = config_dict.get("controller") or TrainingController(
            backend=backend,
            verbose=config_dict.get("verbose", False),
        )
        self._connected = False
        
        # Mode: "draft" or "swap"
        self.mode = config_dict.get("mode", "draft")
        self.auto_connect = config_dict.get("auto_connect", True)
        
        # Action space depends on mode
        if self.mode == "draft":
            self.action_space = spaces.MultiDiscrete([6, 6, 6])
            obs_dim = DRAFT_OBS_DIM
            mask_size = 6
        else:
            self.action_space = spaces.Discrete(SWAP_NUM_ACTIONS)
            obs_dim = SWAP_OBS_DIM
            mask_size = SWAP_NUM_ACTIONS
        
        # Observation space
        self.observation_space = spaces.Dict({
            "obs": spaces.Box(
                low=-1.0, high=1.0,
                shape=(obs_dim,),
                dtype=np.float32,
            ),
            "action_mask": spaces.Box(
                low=0.0, high=1.0,
                shape=(mask_size,),
                dtype=np.float32,
            ),
        })
        
        self._last_obs = None
    
    def _ensure_connected(self) -> None:
        """Ensure controller is connected."""
        if not self._connected and self.auto_connect:
            try:
                self.controller.connect()
                self._connected = True
            except Exception as e:
                logger.warning(f"Auto-connect failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Get observation based on mode."""
        if self.mode == "draft":
            obs_vec = self.controller.get_draft_observation()
            obs_dim = DRAFT_OBS_DIM
            mask_size = 6
        else:
            obs_vec = self.controller.get_swap_observation()
            obs_dim = SWAP_OBS_DIM
            mask_size = SWAP_NUM_ACTIONS
        
        # Pad/truncate
        if len(obs_vec) < obs_dim:
            obs_vec = np.pad(obs_vec, (0, obs_dim - len(obs_vec)))
        else:
            obs_vec = obs_vec[:obs_dim]
        
        # Action mask (all valid for draft/swap)
        action_mask = np.ones(mask_size, dtype=np.float32)
        
        return {
            "obs": obs_vec.astype(np.float32),
            "action_mask": action_mask,
        }
    
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Reset for new draft/swap."""
        super().reset(seed=seed)
        
        self._ensure_connected()
        
        obs = self._get_observation()
        self._last_obs = obs
        
        info = {
            "mode": self.mode,
            "streak": self.controller.run_stats.win_streak,
            "phase": self.controller.phase.name,
        }
        
        return obs, info
    
    def step(
        self,
        action,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """Execute draft/swap action."""
        if self.mode == "draft":
            # Multi-discrete action for team selection
            action_array = np.array(action) if not isinstance(action, np.ndarray) else action
            
            # Create a simple drafter callable
            def drafter_fn(obs, phase):
                return action_array
            
            result = self.controller.step_draft(drafter_fn)
            reward = 0.0  # Drafter reward comes from battle outcomes
            
        else:
            # Discrete swap action
            def drafter_fn(obs, phase):
                return np.array([int(action)])
            
            result = self.controller.step_swap(drafter_fn)
            reward = 0.0
        
        obs = self._get_observation()
        self._last_obs = obs
        
        # Draft/swap is single step
        terminated = True
        truncated = False
        
        info = {
            "success": result.success,
            "streak": self.controller.run_stats.win_streak,
            "phase": self.controller.phase.name,
            "data": result.data,
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self) -> None:
        """Render current state."""
        logger.info(
            f"Mode: {self.mode} | "
            f"Streak: {self.controller.run_stats.win_streak} | "
            f"Phase: {self.controller.phase.name}"
        )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._connected:
            self.controller.disconnect()
            self._connected = False


# =============================================================================
# Unified Battle Factory Environment
# =============================================================================

class BattleFactoryEnv(gym.Env):
    """
    Unified hierarchical environment for Battle Factory.
    
    Manages the full game loop:
    1. Draft phase (Drafter agent)
    2. Battle phase (Tactician agent)
    3. Post-battle (outcome + potential swap)
    
    This environment handles the complete episode lifecycle and can be
    used with RLlib's multi-agent configuration.
    
    Observation Space:
        Dict containing:
        - "phase": Current game phase index
        - "battle_obs": Battle state features
        - "draft_obs": Draft/rental features
        - "action_mask": Valid action mask
        - "streak": Normalized win streak
    
    Action Space:
        Discrete(16):
        - 0-5: Battle actions (Move 1-4, Switch 1-2)
        - 6-11: Draft selections (select Pokemon 0-5)
        - 12-15: Swap actions (keep, swap 1-3)
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config_dict = config_dict or {}
        
        # Backend/controller
        backend = config_dict.get("backend")
        self.controller = config_dict.get("controller") or TrainingController(
            backend=backend,
            verbose=config_dict.get("verbose", False),
        )
        self._connected = False
        
        # Config
        self.max_battles = config_dict.get("max_battles", config.game.max_streak)
        self.max_turns_per_battle = config_dict.get(
            "max_turns_per_battle", 
            config.game.max_streak * 3
        )
        self.auto_connect = config_dict.get("auto_connect", True)
        self.auto_initialize = config_dict.get("auto_initialize", True)
        
        # Combined observation space
        self.observation_space = spaces.Dict({
            "phase": spaces.Discrete(len(GamePhase)),
            "battle_obs": spaces.Box(-1.0, 1.0, (BATTLE_OBS_DIM,), np.float32),
            "draft_obs": spaces.Box(-1.0, 1.0, (DRAFT_OBS_DIM,), np.float32),
            "action_mask": spaces.Box(0.0, 1.0, (BATTLE_NUM_ACTIONS,), np.float32),
            "streak": spaces.Box(0.0, 1.0, (1,), np.float32),
        })
        
        # Unified action space
        # 0-5: Battle, 6-11: Draft, 12-15: Swap
        self.action_space = spaces.Discrete(16)
        
        # State tracking
        self._episode_stats = {}
        self._current_turn = 0
        self._draft_selections = []
    
    def _ensure_connected(self) -> None:
        """Ensure controller is connected."""
        if not self._connected and self.auto_connect:
            try:
                self.controller.connect()
                self._connected = True
            except Exception as e:
                logger.warning(f"Auto-connect failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Get unified observation."""
        phase = self.controller.phase
        phase_idx = list(GamePhase).index(phase)
        
        # Get phase-specific observations
        if phase.is_battle_phase:
            battle_obs = self.controller.get_battle_observation()
            action_mask = self.controller.get_action_mask()
        else:
            battle_obs = np.zeros(BATTLE_OBS_DIM, dtype=np.float32)
            action_mask = np.zeros(BATTLE_NUM_ACTIONS, dtype=np.float32)
        
        if phase.is_draft_phase:
            draft_obs = self.controller.get_draft_observation()
        else:
            draft_obs = np.zeros(DRAFT_OBS_DIM, dtype=np.float32)
        
        # Pad observations
        if len(battle_obs) < BATTLE_OBS_DIM:
            battle_obs = np.pad(battle_obs, (0, BATTLE_OBS_DIM - len(battle_obs)))
        if len(draft_obs) < DRAFT_OBS_DIM:
            draft_obs = np.pad(draft_obs, (0, DRAFT_OBS_DIM - len(draft_obs)))
        
        streak_norm = np.array(
            [self.controller.run_stats.win_streak / config.game.max_streak],
            dtype=np.float32
        )
        
        return {
            "phase": np.array(phase_idx, dtype=np.int64),
            "battle_obs": battle_obs[:BATTLE_OBS_DIM].astype(np.float32),
            "draft_obs": draft_obs[:DRAFT_OBS_DIM].astype(np.float32),
            "action_mask": action_mask.astype(np.float32),
            "streak": streak_norm,
        }
    
    def reset(
        self,
        *,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
        """Reset for new Battle Factory run."""
        super().reset(seed=seed)
        
        self._ensure_connected()
        self.controller.reset_run()
        
        # Initialize to draft screen if needed
        if self.auto_initialize:
            self.controller.initialize_to_draft()
        
        self._episode_stats = {
            "battles_won": 0,
            "battles_lost": 0,
            "max_streak": 0,
            "total_turns": 0,
        }
        self._current_turn = 0
        self._draft_selections = []
        
        obs = self._get_observation()
        
        info = {
            "phase": self.controller.phase.name,
            "streak": self.controller.run_stats.win_streak,
        }
        
        return obs, info
    
    def step(
        self,
        action: int,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute action based on current phase.
        
        Action mapping:
        - 0-5: Battle actions (valid during battle phases)
        - 6-11: Draft selections (valid during DRAFT_SCREEN)
        - 12-15: Swap actions (valid during SWAP_SCREEN)
        """
        reward = 0.0
        terminated = False
        truncated = False
        phase = self.controller.phase
        
        if phase == GamePhase.DRAFT_SCREEN:
            # Draft action: collect selections
            if 6 <= action <= 11:
                selection_idx = action - 6
                self._draft_selections.append(selection_idx)
                
                # After 3 selections, execute draft
                if len(self._draft_selections) >= 3:
                    selections = np.array(self._draft_selections[:3])
                    
                    def drafter_fn(obs, ph):
                        return selections
                    
                    self.controller.step_draft(drafter_fn)
                    self._draft_selections = []
        
        elif phase == GamePhase.BATTLE_READY:
            # Wait for battle to start
            self.controller.wait_for_battle_start()
        
        elif phase == GamePhase.IN_BATTLE:
            # Battle action
            if 0 <= action <= 5:
                result = self.controller.step_turn(action)
                reward = result.reward
                self._current_turn += 1
                self._episode_stats["total_turns"] += 1
                
                if result.battle_ended:
                    # Handle outcome
                    outcome = result.outcome
                    
                    if outcome == BattleOutcome.WIN:
                        self._episode_stats["battles_won"] += 1
                        self._episode_stats["max_streak"] = max(
                            self._episode_stats["max_streak"],
                            self.controller.run_stats.win_streak
                        )
                    else:
                        self._episode_stats["battles_lost"] += 1
                        terminated = True
        
        elif phase == GamePhase.SWAP_SCREEN:
            # Swap action
            if 12 <= action <= 15:
                swap_action = action - 12
                
                def drafter_fn(obs, ph):
                    return np.array([swap_action])
                
                self.controller.step_swap(drafter_fn)
        
        elif phase == GamePhase.RUN_COMPLETE:
            terminated = True
        
        # Check truncation
        if self.controller.run_stats.win_streak >= self.max_battles:
            truncated = True
        
        obs = self._get_observation()
        
        info = {
            "phase": self.controller.phase.name,
            "streak": self.controller.run_stats.win_streak,
            "stats": self._episode_stats.copy(),
            "turn": self._current_turn,
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self) -> None:
        """Render current state."""
        logger.info(
            f"Phase: {self.controller.phase.name} | "
            f"Streak: {self.controller.run_stats.win_streak}"
        )
    
    def close(self) -> None:
        """Clean up resources."""
        if self._connected:
            self.controller.disconnect()
            self._connected = False


# =============================================================================
# Environment Registration for RLlib
# =============================================================================

def register_envs() -> None:
    """Register environments with Gymnasium."""
    from gymnasium.envs.registration import register
    
    try:
        register(
            id="BattleFactory-Tactician-v0",
            entry_point="src.env:TacticianEnv",
        )
        register(
            id="BattleFactory-Drafter-v0",
            entry_point="src.env:DrafterEnv",
        )
        register(
            id="BattleFactory-v0",
            entry_point="src.env:BattleFactoryEnv",
        )
    except Exception:
        pass  # Already registered


# Legacy compatibility alias
class EmeraldBattleFactoryEnv(BattleFactoryEnv):
    """Legacy alias for backwards compatibility."""
    pass
