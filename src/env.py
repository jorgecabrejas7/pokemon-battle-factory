"""
Gymnasium Environments for Battle Factory RL System.

Provides RLlib-compatible environments for:
1. TacticianEnv: Battle decisions (Move 1-4, Switch 1-2)
2. DrafterEnv: Team selection and swaps
3. BattleFactoryEnv: Unified hierarchical environment

Uses Gymnasium (not old gym) for RLlib 2.x compatibility.
"""

import gymnasium as gym
from gymnasium import spaces
import numpy as np
from typing import Tuple, Dict, Any, Optional, List
import logging

from .backends.emerald.backend import EmeraldBackend
from .core.enums import BattleOutcome
from .core.dataclasses import BattleState, FactoryState
from .system import BattleFactorySystem, GamePhase

logger = logging.getLogger(__name__)


# =============================================================================
# Observation/Action Space Dimensions
# =============================================================================

# Battle observation features (for Tactician)
BATTLE_OBS_DIM = 64  # Flattened battle state
BATTLE_NUM_ACTIONS = 6  # Move 1-4, Switch 1-2

# Draft observation features (for Drafter)
DRAFT_OBS_DIM = 128  # Rental candidates + context
DRAFT_NUM_ACTIONS = 6  # Select from 6 candidates

# Swap observation features
SWAP_OBS_DIM = 64
SWAP_NUM_ACTIONS = 4  # Keep or swap 1-3


class TacticianEnv(gym.Env):
    """
    Environment for the Tactician (battle) agent.
    
    Handles turn-by-turn battle decisions with:
    - Action masking for invalid moves
    - LSTM-friendly observation format
    - Shaped rewards for damage/faints
    
    Compatible with RLlib's RecurrentPPO.
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config = config or {}
        
        # Backend connection
        self.backend = config.get("backend") or EmeraldBackend()
        self.system = config.get("system") or BattleFactorySystem(self.backend)
        self.connected = False
        
        # Config
        self.max_turns = config.get("max_turns", 100)
        self.reward_scale = config.get("reward_scale", 1.0)
        
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
        
    def _ensure_connected(self):
        """Ensure backend is connected."""
        if not self.connected:
            try:
                self.system.connect()
                self.connected = True
            except Exception as e:
                logger.warning(f"Backend connection failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Build observation dict with action mask."""
        obs_vec = self.system.get_battle_observation()
        
        # Pad/truncate to fixed size
        if len(obs_vec) < BATTLE_OBS_DIM:
            obs_vec = np.pad(obs_vec, (0, BATTLE_OBS_DIM - len(obs_vec)))
        else:
            obs_vec = obs_vec[:BATTLE_OBS_DIM]
        
        action_mask = self.system.get_action_mask()
        
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
        self.system.reset_battle()
        
        self.current_turn = 0
        self.episode_reward = 0.0
        
        obs = self._get_observation()
        self._last_obs = obs
        
        info = {
            "turn": self.current_turn,
            "streak": self.system.current_streak,
        }
        
        return obs, info
    
    def step(
        self, 
        action: int,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute battle action.
        
        Returns (obs, reward, terminated, truncated, info)
        """
        # Execute action
        reward, done = self.system.execute_battle_action(action)
        reward *= self.reward_scale
        
        self.current_turn += 1
        self.episode_reward += reward
        
        # Check truncation (max turns)
        truncated = self.current_turn >= self.max_turns
        terminated = done
        
        # Get new observation
        obs = self._get_observation()
        self._last_obs = obs
        
        info = {
            "turn": self.current_turn,
            "streak": self.system.current_streak,
            "episode_reward": self.episode_reward,
            "battle_outcome": self.system._get_battle_outcome().name,
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self):
        """Render current state."""
        if self._last_obs is not None:
            state = self.system._last_battle_state
            if state:
                logger.info(f"Turn {self.current_turn} | "
                           f"Player: {state.active_pokemon.species_id if state.active_pokemon else 'N/A'} | "
                           f"Enemy: {state.enemy_active_pokemon.species_id if state.enemy_active_pokemon else 'N/A'}")
    
    def close(self):
        """Clean up resources."""
        if hasattr(self.backend, 'sock') and self.backend.sock:
            self.backend.sock.close()


class DrafterEnv(gym.Env):
    """
    Environment for the Drafter (selection) agent.
    
    Handles:
    - Initial team selection (3 from 6)
    - Post-battle swaps
    
    Uses multi-discrete action space for selecting multiple Pokemon.
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config = config or {}
        
        # Backend connection
        self.backend = config.get("backend") or EmeraldBackend()
        self.system = config.get("system") or BattleFactorySystem(self.backend)
        self.connected = False
        
        # Mode: "draft" or "swap"
        self.mode = config.get("mode", "draft")
        
        # Action space depends on mode
        if self.mode == "draft":
            # Select 3 Pokemon from 6 (simplified to single selection for now)
            self.action_space = spaces.MultiDiscrete([6, 6, 6])
        else:
            # Swap: 0=keep, 1-3=swap with candidate
            self.action_space = spaces.Discrete(SWAP_NUM_ACTIONS)
        
        # Observation space
        obs_dim = DRAFT_OBS_DIM if self.mode == "draft" else SWAP_OBS_DIM
        self.observation_space = spaces.Dict({
            "obs": spaces.Box(
                low=-1.0, high=1.0,
                shape=(obs_dim,),
                dtype=np.float32,
            ),
            "action_mask": spaces.Box(
                low=0.0, high=1.0,
                shape=(6,) if self.mode == "draft" else (SWAP_NUM_ACTIONS,),
                dtype=np.float32,
            ),
        })
        
        self._last_obs = None
        
    def _ensure_connected(self):
        """Ensure backend is connected."""
        if not self.connected:
            try:
                self.system.connect()
                self.connected = True
            except Exception as e:
                logger.warning(f"Backend connection failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Get observation based on mode."""
        if self.mode == "draft":
            obs_vec = self.system.get_draft_observation()
            obs_dim = DRAFT_OBS_DIM
        else:
            obs_vec = self.system.get_swap_observation()
            obs_dim = SWAP_OBS_DIM
        
        # Pad/truncate
        if len(obs_vec) < obs_dim:
            obs_vec = np.pad(obs_vec, (0, obs_dim - len(obs_vec)))
        else:
            obs_vec = obs_vec[:obs_dim]
        
        # Action mask (all valid for now)
        mask_size = 6 if self.mode == "draft" else SWAP_NUM_ACTIONS
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
            "streak": self.system.current_streak,
        }
        
        return obs, info
    
    def step(
        self,
        action,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """Execute draft/swap action."""
        if self.mode == "draft":
            # Multi-discrete action
            action_array = np.array(action) if not isinstance(action, np.ndarray) else action
            success = self.system.execute_draft(action_array)
            # Drafter reward comes from battle outcomes (delayed)
            reward = 0.0
        else:
            # Discrete swap action
            success = self.system.execute_swap(int(action))
            reward = 0.0
        
        obs = self._get_observation()
        self._last_obs = obs
        
        # Draft/swap is single step
        terminated = True
        truncated = False
        
        info = {
            "success": success,
            "streak": self.system.current_streak,
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self):
        """Render current state."""
        logger.info(f"Mode: {self.mode} | Streak: {self.system.current_streak}")
    
    def close(self):
        """Clean up resources."""
        if hasattr(self.backend, 'sock') and self.backend.sock:
            self.backend.sock.close()


class BattleFactoryEnv(gym.Env):
    """
    Unified hierarchical environment for Battle Factory.
    
    Manages the full game loop:
    1. Draft phase (Drafter agent)
    2. Battle phase (Tactician agent)
    3. Post-battle (outcome + potential swap)
    
    RLlib can use this with multi-agent configuration.
    """
    
    metadata = {"render_modes": ["human", "ansi"]}
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        config = config or {}
        
        # Backend
        self.backend = config.get("backend") or EmeraldBackend()
        self.system = BattleFactorySystem(self.backend)
        self.connected = False
        
        # Phase tracking
        self.phase = GamePhase.INITIALIZING
        
        # Config
        self.max_battles = config.get("max_battles", 42)
        self.max_turns_per_battle = config.get("max_turns_per_battle", 100)
        
        # Combined observation space
        # Includes phase indicator + phase-specific obs
        self.observation_space = spaces.Dict({
            "phase": spaces.Discrete(len(GamePhase)),
            "battle_obs": spaces.Box(-1.0, 1.0, (BATTLE_OBS_DIM,), np.float32),
            "draft_obs": spaces.Box(-1.0, 1.0, (DRAFT_OBS_DIM,), np.float32),
            "action_mask": spaces.Box(0.0, 1.0, (BATTLE_NUM_ACTIONS,), np.float32),
            "streak": spaces.Box(0.0, 1.0, (1,), np.float32),
        })
        
        # Action space: union of all possible actions
        # 0-5: Battle actions (Move 1-4, Switch 1-2)
        # 6-11: Draft selections (select Pokemon 0-5)
        # 12-15: Swap actions (keep, swap 1-3)
        self.action_space = spaces.Discrete(16)
        
        self._episode_stats = {}
        
    def _ensure_connected(self):
        """Ensure backend is connected."""
        if not self.connected:
            try:
                self.system.connect()
                self.connected = True
            except Exception as e:
                logger.warning(f"Backend connection failed: {e}")
    
    def _get_observation(self) -> Dict[str, np.ndarray]:
        """Get unified observation."""
        # Phase indicator
        phase_idx = list(GamePhase).index(self.phase)
        
        # Get phase-specific observations
        if self.phase in [GamePhase.BATTLE, GamePhase.POST_BATTLE]:
            battle_obs = self.system.get_battle_observation()
            action_mask = self.system.get_action_mask()
        else:
            battle_obs = np.zeros(BATTLE_OBS_DIM, dtype=np.float32)
            action_mask = np.zeros(BATTLE_NUM_ACTIONS, dtype=np.float32)
        
        if self.phase in [GamePhase.DRAFT, GamePhase.SWAP]:
            draft_obs = self.system.get_draft_observation()
        else:
            draft_obs = np.zeros(DRAFT_OBS_DIM, dtype=np.float32)
        
        # Pad observations
        if len(battle_obs) < BATTLE_OBS_DIM:
            battle_obs = np.pad(battle_obs, (0, BATTLE_OBS_DIM - len(battle_obs)))
        if len(draft_obs) < DRAFT_OBS_DIM:
            draft_obs = np.pad(draft_obs, (0, DRAFT_OBS_DIM - len(draft_obs)))
        
        streak_norm = np.array([self.system.current_streak / 42.0], dtype=np.float32)
        
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
        self.system.reset_run()
        self.phase = GamePhase.DRAFT
        
        self._episode_stats = {
            "battles_won": 0,
            "battles_lost": 0,
            "max_streak": 0,
            "total_turns": 0,
        }
        
        obs = self._get_observation()
        
        info = {
            "phase": self.phase.name,
            "streak": self.system.current_streak,
        }
        
        return obs, info
    
    def step(
        self,
        action: int,
    ) -> Tuple[Dict[str, np.ndarray], float, bool, bool, Dict[str, Any]]:
        """
        Execute action based on current phase.
        
        Action mapping:
        - 0-5: Battle actions (valid during BATTLE phase)
        - 6-11: Draft/swap selections (valid during DRAFT/SWAP phase)
        """
        reward = 0.0
        terminated = False
        truncated = False
        
        if self.phase == GamePhase.DRAFT:
            # Draft action: convert to multi-selection
            # Simplified: action 6-11 maps to single selection
            if 6 <= action <= 11:
                selection_idx = action - 6
                # For simplicity, auto-select 3 starting from chosen index
                selections = np.array([(selection_idx + i) % 6 for i in range(3)])
                self.system.execute_draft(selections)
                self.phase = GamePhase.PRE_BATTLE
        
        elif self.phase == GamePhase.BATTLE:
            # Battle action
            if 0 <= action <= 5:
                step_reward, done = self.system.execute_battle_action(action)
                reward = step_reward
                self._episode_stats["total_turns"] += 1
                
                if done:
                    self.phase = GamePhase.POST_BATTLE
        
        elif self.phase == GamePhase.POST_BATTLE:
            # Handle battle outcome
            drafter_reward, run_complete = self.system.handle_post_battle()
            reward += drafter_reward
            
            if self.system.run_stats.battles_won > self._episode_stats["battles_won"]:
                self._episode_stats["battles_won"] = self.system.run_stats.battles_won
                self._episode_stats["max_streak"] = max(
                    self._episode_stats["max_streak"],
                    self.system.current_streak
                )
            
            if run_complete:
                terminated = True
                self.phase = GamePhase.RUN_COMPLETE
            elif self.system.phase == GamePhase.SWAP:
                self.phase = GamePhase.SWAP
            else:
                self.phase = GamePhase.BATTLE
                self.system.reset_battle()
        
        elif self.phase == GamePhase.SWAP:
            # Swap action
            if 6 <= action <= 9:
                swap_action = action - 6  # 0=keep, 1-3=swap
                self.system.execute_swap(swap_action)
                self.phase = GamePhase.BATTLE
                self.system.reset_battle()
        
        # Check truncation
        if self.system.current_streak >= self.max_battles:
            truncated = True
        
        obs = self._get_observation()
        
        info = {
            "phase": self.phase.name,
            "streak": self.system.current_streak,
            "stats": self._episode_stats.copy(),
        }
        
        return obs, reward, terminated, truncated, info
    
    def render(self):
        """Render current state."""
        logger.info(f"Phase: {self.phase.name} | Streak: {self.system.current_streak}")
    
    def close(self):
        """Clean up resources."""
        if hasattr(self.backend, 'sock') and self.backend.sock:
            self.backend.sock.close()


# =============================================================================
# Environment Registration for RLlib
# =============================================================================

def register_envs():
    """Register environments with Gymnasium."""
    from gymnasium.envs.registration import register
    
    # Note: These registrations allow RLlib to create envs by string ID
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


# Legacy compatibility with old gym
class EmeraldBattleFactoryEnv(BattleFactoryEnv):
    """Legacy alias for backwards compatibility."""
    pass
