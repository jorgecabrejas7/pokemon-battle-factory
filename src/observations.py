"""
Observation Builder - Centralized observation construction.

This module provides the ObservationBuilder class as a single source
of truth for building observation vectors for RL agents.

Usage:
    from src.observations import ObservationBuilder
    
    builder = ObservationBuilder()
    
    # Battle observation
    battle_obs = builder.build_battle_obs(battle_state)
    
    # Draft observation
    draft_obs = builder.build_draft_obs(rentals, context)
    
    # Full observation dict (for Gymnasium)
    obs_dict = builder.build_full_obs(battle_state, rentals, phase)
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from .config import config, BattleFactoryConfig
from .core.enums import GamePhase

if TYPE_CHECKING:
    from .core.dataclasses import BattleState, PlayerPokemon, EnemyPokemon
    from .backends.emerald.memory_reader import RentalMon


@dataclass
class ObservationSpec:
    """Specification for observation space dimensions."""
    battle_dim: int
    draft_dim: int
    swap_dim: int
    num_battle_actions: int
    num_draft_candidates: int
    num_swap_actions: int


class ObservationBuilder:
    """
    Centralized builder for RL observation vectors.
    
    Provides consistent observation construction across all environments
    and controllers, ensuring:
    - Same feature encoding everywhere
    - Consistent normalization
    - Proper padding/truncation to fixed dimensions
    
    Attributes:
        config: Configuration with normalization constants
        spec: Observation space specification
    """
    
    def __init__(self, cfg: Optional[BattleFactoryConfig] = None):
        """
        Initialize observation builder.
        
        Args:
            cfg: Configuration (uses global default if None)
        """
        self.config = cfg or config
        
        self.spec = ObservationSpec(
            battle_dim=self.config.dimensions.battle_obs_dim,
            draft_dim=self.config.dimensions.draft_obs_dim,
            swap_dim=self.config.dimensions.swap_obs_dim,
            num_battle_actions=self.config.dimensions.battle_num_actions,
            num_draft_candidates=self.config.dimensions.draft_num_candidates,
            num_swap_actions=self.config.dimensions.swap_num_actions,
        )
    
    @property
    def norm(self):
        """Normalization config shortcut."""
        return self.config.normalization
    
    # =========================================================================
    # Battle Observations
    # =========================================================================
    
    def build_battle_obs(
        self,
        state: BattleState,
        context: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Build battle observation vector.
        
        Features (in order):
        - Player Pokemon: species, hp_ratio, stats (6), level, moves (4) = 12
        - Enemy Pokemon: species, hp_pct, level, revealed_moves (4) = 7
        - Context: streak, turn, weather = 3
        Total base: 22 features, padded to battle_obs_dim
        
        Args:
            state: Current BattleState
            context: Optional context dict with 'streak', 'turn' keys
            
        Returns:
            Numpy array of shape (battle_obs_dim,)
        """
        features = []
        
        # Player Pokemon features
        features.extend(self._encode_player_pokemon(state.active_pokemon))
        
        # Enemy Pokemon features
        features.extend(self._encode_enemy_pokemon(state.enemy_active_pokemon))
        
        # Context features
        ctx = context or {}
        features.extend([
            ctx.get('streak', 0) / self.norm.streak_divisor,
            ctx.get('turn', 0) / self.norm.turn_divisor,
            (state.weather.value if state.weather else 0) / self.norm.weather_divisor,
        ])
        
        return self._pad_or_truncate(features, self.spec.battle_dim)
    
    def _encode_player_pokemon(self, pokemon: Optional[PlayerPokemon]) -> List[float]:
        """Encode player Pokemon to feature list."""
        if pokemon is None:
            return [0.0] * 12  # species + hp + 6 stats + level + 4 moves
        
        features = [
            pokemon.species_id / self.norm.species_divisor,
            pokemon.current_hp / max(pokemon.hp, 1),
            pokemon.attack / self.norm.stat_divisor,
            pokemon.defense / self.norm.stat_divisor,
            pokemon.sp_attack / self.norm.stat_divisor,
            pokemon.sp_defense / self.norm.stat_divisor,
            pokemon.speed / self.norm.stat_divisor,
            pokemon.level / self.norm.level_divisor,
        ]
        
        # Moves (4 slots)
        for i in range(4):
            if i < len(pokemon.moves) and pokemon.moves[i]:
                features.append(pokemon.moves[i].move_id / self.norm.move_divisor)
            else:
                features.append(0.0)
        
        return features
    
    def _encode_enemy_pokemon(self, pokemon: Optional[EnemyPokemon]) -> List[float]:
        """Encode enemy Pokemon to feature list."""
        if pokemon is None:
            return [0.0] * 7  # species + hp_pct + level + 4 moves
        
        features = [
            pokemon.species_id / self.norm.species_divisor,
            pokemon.hp_percentage / 100.0,
            pokemon.level / self.norm.level_divisor,
        ]
        
        # Revealed moves (4 slots)
        for i in range(4):
            if i < len(pokemon.revealed_moves):
                features.append(pokemon.revealed_moves[i].move_id / self.norm.move_divisor)
            else:
                features.append(0.0)
        
        return features
    
    def build_action_mask(
        self,
        state: Optional[BattleState],
    ) -> np.ndarray:
        """
        Build valid action mask for battle.
        
        Args:
            state: Current BattleState
            
        Returns:
            Binary mask of shape (num_battle_actions,)
        """
        mask = np.ones(self.spec.num_battle_actions, dtype=np.float32)
        
        if state is None or state.active_pokemon is None:
            return mask
        
        pokemon = state.active_pokemon
        
        # Check move PP (actions 0-3)
        for i in range(4):
            if i >= len(pokemon.moves):
                mask[i] = 0.0
            elif pokemon.moves[i] is None or pokemon.moves[i].current_pp <= 0:
                mask[i] = 0.0
        
        # Check switch availability (actions 4-5)
        party = state.party
        if len(party) < 2:
            mask[4] = 0.0
            mask[5] = 0.0
        elif len(party) < 3:
            mask[5] = 0.0
        
        return mask
    
    # =========================================================================
    # Draft Observations
    # =========================================================================
    
    def build_draft_obs(
        self,
        rentals: List[RentalMon],
        context: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Build draft observation vector.
        
        Features:
        - 6 rental Pokemon: frontier_mon_id, iv_spread, ability_num = 18
        - Context: streak, current_battle = 2
        Total base: 20 features, padded to draft_obs_dim
        
        Args:
            rentals: List of RentalMon objects
            context: Optional context dict
            
        Returns:
            Numpy array of shape (draft_obs_dim,)
        """
        features = []
        
        # Encode each rental slot
        for i in range(6):
            if i < len(rentals):
                features.extend([
                    rentals[i].frontier_mon_id / self.norm.frontier_mon_divisor,
                    rentals[i].iv_spread / self.norm.iv_divisor,
                    rentals[i].ability_num / 2.0,
                ])
            else:
                features.extend([0.0, 0.0, 0.0])
        
        # Context
        ctx = context or {}
        features.extend([
            ctx.get('streak', 0) / self.norm.streak_divisor,
            ctx.get('battle', 0) / self.config.game.battles_per_round,
        ])
        
        return self._pad_or_truncate(features, self.spec.draft_dim)
    
    # =========================================================================
    # Swap Observations
    # =========================================================================
    
    def build_swap_obs(
        self,
        team: List[Any],  # List of party Pokemon
        candidate: Optional[Any] = None,
        context: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """
        Build swap observation vector.
        
        Features:
        - Current team (3 Pokemon): species, hp_ratio = 6
        - Swap candidate: species, stats = variable
        - Context: streak, battle = 2
        
        Args:
            team: Current team Pokemon list
            candidate: Swap candidate (if available)
            context: Optional context dict
            
        Returns:
            Numpy array of shape (swap_obs_dim,)
        """
        features = []
        
        # Current team
        for i in range(3):
            if i < len(team):
                p = team[i]
                features.extend([
                    p.species_id / self.norm.species_divisor,
                    p.current_hp / max(p.max_hp, 1),
                ])
            else:
                features.extend([0.0, 0.0])
        
        # Candidate (if available)
        if candidate:
            features.extend([
                candidate.species_id / self.norm.species_divisor,
                1.0,  # Full HP for candidate
            ])
        else:
            features.extend([0.0, 0.0])
        
        # Context
        ctx = context or {}
        features.extend([
            ctx.get('streak', 0) / self.norm.streak_divisor,
            ctx.get('battle', 0) / self.config.game.battles_per_round,
        ])
        
        return self._pad_or_truncate(features, self.spec.swap_dim)
    
    # =========================================================================
    # Full Observation Dict (for Gymnasium)
    # =========================================================================
    
    def build_full_obs(
        self,
        battle_state: Optional[BattleState],
        rentals: Optional[List[RentalMon]],
        phase: GamePhase,
        context: Optional[Dict[str, float]] = None,
    ) -> Dict[str, np.ndarray]:
        """
        Build full observation dict for Gymnasium environment.
        
        Args:
            battle_state: Current BattleState (if in battle)
            rentals: Rental Pokemon (if in draft)
            phase: Current game phase
            context: Context dict with streak, turn, battle
            
        Returns:
            Dict with 'obs', 'action_mask', 'phase' keys
        """
        ctx = context or {}
        
        # Phase-specific observation
        if phase.is_battle_phase and battle_state:
            obs_vec = self.build_battle_obs(battle_state, ctx)
            action_mask = self.build_action_mask(battle_state)
        elif phase.is_draft_phase and rentals:
            obs_vec = self.build_draft_obs(rentals, ctx)
            action_mask = np.ones(self.spec.num_draft_candidates, dtype=np.float32)
        else:
            obs_vec = np.zeros(self.spec.battle_dim, dtype=np.float32)
            action_mask = np.zeros(self.spec.num_battle_actions, dtype=np.float32)
        
        return {
            "obs": obs_vec,
            "action_mask": action_mask,
            "phase": np.array(phase.value, dtype=np.int64),
            "streak": np.array([ctx.get('streak', 0) / self.norm.streak_divisor], dtype=np.float32),
        }
    
    # =========================================================================
    # Utilities
    # =========================================================================
    
    def _pad_or_truncate(self, features: List[float], target_dim: int) -> np.ndarray:
        """Pad or truncate feature list to target dimension."""
        arr = np.array(features, dtype=np.float32)
        
        if len(arr) < target_dim:
            # Pad with zeros
            arr = np.pad(arr, (0, target_dim - len(arr)))
        elif len(arr) > target_dim:
            # Truncate
            arr = arr[:target_dim]
        
        return arr
    
    def get_observation_spaces(self):
        """
        Get Gymnasium observation space specifications.
        
        Returns:
            Dict of gym.spaces for observation components
        """
        import gymnasium as gym
        from gymnasium import spaces
        
        return {
            "obs": spaces.Box(
                low=-1.0, high=1.0,
                shape=(self.spec.battle_dim,),
                dtype=np.float32
            ),
            "action_mask": spaces.Box(
                low=0.0, high=1.0,
                shape=(self.spec.num_battle_actions,),
                dtype=np.float32
            ),
            "phase": spaces.Discrete(len(GamePhase)),
            "streak": spaces.Box(
                low=0.0, high=1.0,
                shape=(1,),
                dtype=np.float32
            ),
        }


# Global default builder
obs_builder = ObservationBuilder()

