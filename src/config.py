"""
Centralized Configuration for Battle Factory RL System.

This module provides a single source of truth for all configuration
values used throughout the codebase, eliminating magic numbers and
ensuring consistency.

Usage:
    from src.config import config, BattleFactoryConfig
    
    # Use default config
    obs_dim = config.battle_obs_dim
    
    # Create custom config
    custom = BattleFactoryConfig(max_streak=21)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any
import json
from pathlib import Path


@dataclass
class DimensionConfig:
    """Observation and action space dimensions."""
    
    # Battle observation
    battle_obs_dim: int = 64
    battle_num_actions: int = 6  # Move 1-4, Switch 1-2
    
    # Draft observation
    draft_obs_dim: int = 128
    draft_num_candidates: int = 6
    draft_team_size: int = 3
    
    # Swap observation
    swap_obs_dim: int = 64
    swap_num_actions: int = 4  # Keep or swap slots 1-3


@dataclass
class GameConstants:
    """Pokemon Emerald Battle Factory game constants."""
    
    # Battle Factory rules
    max_streak: int = 42
    battles_per_round: int = 7
    rental_pool_size: int = 6
    team_size: int = 3
    
    # Factory Brain appears at these streaks
    silver_symbol_streak: int = 21
    gold_symbol_streak: int = 42
    
    # Gen 3 limits
    max_species_id: int = 440  # 386 Pokemon + buffer
    max_move_id: int = 470     # 354 moves + buffer
    max_item_id: int = 400     # 377 items + buffer
    max_ability_id: int = 80   # 77 abilities + buffer
    num_types: int = 18
    
    # Battle limits
    max_party_size: int = 6
    max_moves_per_pokemon: int = 4
    max_level: int = 100
    max_stat: int = 255
    max_base_stat: int = 255
    max_ev: int = 255
    max_iv: int = 31
    max_pp: int = 64


@dataclass
class NormalizationConfig:
    """Normalization constants for neural network inputs."""
    
    # These are the divisors used to normalize features to [0, 1] range
    species_divisor: float = 400.0
    move_divisor: float = 400.0
    stat_divisor: float = 255.0
    hp_divisor: float = 255.0
    level_divisor: float = 100.0
    streak_divisor: float = 42.0
    battle_divisor: float = 7.0
    turn_divisor: float = 100.0
    pp_divisor: float = 64.0
    accuracy_divisor: float = 100.0
    power_divisor: float = 250.0
    weather_divisor: float = 5.0
    iv_divisor: float = 31.0
    frontier_mon_divisor: float = 900.0


@dataclass  
class TimingConfig:
    """
    Timing constants for button presses and waits (in seconds).
    
    For faster gameplay, reduce button_hold_time and wait times.
    Minimum practical values depend on emulator speed:
    - At 1x speed: ~0.03s hold, ~0.05s wait minimum
    - At 2x speed: ~0.015s hold, ~0.025s wait minimum
    - At 4x+ speed: Can go even lower
    
    Use set_speed_mode() for quick presets.
    """
    
    # Button press durations
    button_hold_time: float = 0.08      # ~5 frames at 60fps
    
    # Wait times after actions
    wait_short: float = 0.25            # ~15 frames
    wait_medium: float = 0.5            # ~30 frames
    wait_long: float = 1.0              # ~60 frames
    wait_battle: float = 2.0            # For battle animations
    
    # Timeouts
    input_timeout: float = 60.0         # Max wait for input prompt
    battle_start_timeout: float = 10.0  # Max wait for battle to start
    connection_timeout: float = 5.0     # Socket connection timeout
    
    # Frame rate
    fps: int = 60
    
    def frames_to_seconds(self, frames: int) -> float:
        """Convert frame count to seconds."""
        return frames / self.fps
    
    def seconds_to_frames(self, seconds: float) -> int:
        """Convert seconds to frame count."""
        return int(seconds * self.fps)
    
    def set_speed_mode(self, mode: str) -> None:
        """
        Set timing for different speed modes.
        
        Args:
            mode: One of 'normal', 'fast', 'turbo', 'instant'
        
        Presets:
            normal:  Standard timing (default)
            fast:    2x faster, good for training
            turbo:   4x faster, for fast-forward emulation
            instant: Minimal delays, max speed
        """
        presets = {
            'normal': {
                'button_hold_time': 0.08,
                'wait_short': 0.25,
                'wait_medium': 0.5,
                'wait_long': 1.0,
                'wait_battle': 2.0,
            },
            'fast': {
                'button_hold_time': 0.04,
                'wait_short': 0.12,
                'wait_medium': 0.25,
                'wait_long': 0.5,
                'wait_battle': 1.0,
            },
            'turbo': {
                'button_hold_time': 0.02,
                'wait_short': 0.05,
                'wait_medium': 0.1,
                'wait_long': 0.2,
                'wait_battle': 0.5,
            },
            'instant': {
                'button_hold_time': 0.01,
                'wait_short': 0.02,
                'wait_medium': 0.04,
                'wait_long': 0.08,
                'wait_battle': 0.15,
            },
        }
        
        if mode not in presets:
            raise ValueError(f"Unknown speed mode: {mode}. Use: {list(presets.keys())}")
        
        for attr, value in presets[mode].items():
            setattr(self, attr, value)
    
    def set_custom_timing(
        self,
        button_hold: float | None = None,
        wait_short: float | None = None,
        wait_medium: float | None = None,
        wait_long: float | None = None,
        wait_battle: float | None = None,
    ) -> None:
        """
        Set custom timing values.
        
        Args:
            button_hold: How long to hold buttons (seconds)
            wait_short: Short wait after actions
            wait_medium: Medium wait for menu transitions
            wait_long: Long wait for screen transitions
            wait_battle: Wait for battle animations
        """
        if button_hold is not None:
            self.button_hold_time = button_hold
        if wait_short is not None:
            self.wait_short = wait_short
        if wait_medium is not None:
            self.wait_medium = wait_medium
        if wait_long is not None:
            self.wait_long = wait_long
        if wait_battle is not None:
            self.wait_battle = wait_battle
    
    def scale_timing(self, factor: float) -> None:
        """
        Scale all timing values by a factor.
        
        Args:
            factor: Multiplier (0.5 = twice as fast, 2.0 = twice as slow)
        """
        self.button_hold_time *= factor
        self.wait_short *= factor
        self.wait_medium *= factor
        self.wait_long *= factor
        self.wait_battle *= factor


@dataclass
class NetworkConfig:
    """Network connection configuration."""
    
    host: str = "127.0.0.1"
    port: int = 7777
    buffer_size: int = 4096


@dataclass
class RewardConfig:
    """Reward shaping configuration for RL training."""
    
    # Battle outcome rewards
    win_base_reward: float = 10.0
    win_streak_multiplier: float = 0.1
    loss_base_penalty: float = 10.0
    loss_streak_multiplier: float = 0.2
    
    # Damage shaping
    damage_dealt_multiplier: float = 0.01
    damage_taken_multiplier: float = 0.0005
    
    # Faint bonuses
    enemy_faint_bonus: float = 1.0
    player_faint_penalty: float = 0.5
    
    # Drafter rewards
    drafter_win_reward: float = 1.0
    drafter_loss_penalty: float = 1.0


@dataclass
class ModelConfig:
    """Neural network model configuration."""
    
    # Embedding dimensions
    embed_dim: int = 32
    type_embed_dim: int = 16
    
    # Tactician (LSTM) config
    lstm_hidden_size: int = 256
    lstm_num_layers: int = 2
    lstm_max_seq_len: int = 100
    
    # Drafter (Transformer) config
    transformer_heads: int = 4
    transformer_layers: int = 2
    transformer_ff_dim: int = 128
    
    # Shared MLP config
    mlp_hidden_sizes: tuple = (128, 64)
    
    # Training
    learning_rate: float = 3e-4
    gamma: float = 0.99
    lambda_gae: float = 0.95
    clip_param: float = 0.2
    entropy_coeff: float = 0.01


@dataclass
class BattleFactoryConfig:
    """
    Master configuration class for the Battle Factory RL system.
    
    Combines all sub-configurations into a single object that can
    be passed throughout the codebase.
    
    Example:
        config = BattleFactoryConfig()
        print(config.dimensions.battle_obs_dim)  # 64
        print(config.game.max_streak)  # 42
        print(config.timing.wait_short)  # 0.25
    """
    
    dimensions: DimensionConfig = field(default_factory=DimensionConfig)
    game: GameConstants = field(default_factory=GameConstants)
    normalization: NormalizationConfig = field(default_factory=NormalizationConfig)
    timing: TimingConfig = field(default_factory=TimingConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    rewards: RewardConfig = field(default_factory=RewardConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    
    # Convenience properties for common access patterns
    @property
    def battle_obs_dim(self) -> int:
        return self.dimensions.battle_obs_dim
    
    @property
    def draft_obs_dim(self) -> int:
        return self.dimensions.draft_obs_dim
    
    @property
    def num_battle_actions(self) -> int:
        return self.dimensions.battle_num_actions
    
    @property
    def max_streak(self) -> int:
        return self.game.max_streak
    
    @property
    def battles_per_round(self) -> int:
        return self.game.battles_per_round
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        return {
            "dimensions": self.dimensions.__dict__,
            "game": self.game.__dict__,
            "normalization": self.normalization.__dict__,
            "timing": {k: v for k, v in self.timing.__dict__.items() if not callable(v)},
            "network": self.network.__dict__,
            "rewards": self.rewards.__dict__,
            "model": {k: v if not isinstance(v, tuple) else list(v) 
                     for k, v in self.model.__dict__.items()},
        }
    
    def save(self, path: str | Path) -> None:
        """Save configuration to JSON file."""
        path = Path(path)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str | Path) -> BattleFactoryConfig:
        """Load configuration from JSON file."""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)
        
        return cls(
            dimensions=DimensionConfig(**data.get("dimensions", {})),
            game=GameConstants(**data.get("game", {})),
            normalization=NormalizationConfig(**data.get("normalization", {})),
            timing=TimingConfig(**{k: v for k, v in data.get("timing", {}).items()}),
            network=NetworkConfig(**data.get("network", {})),
            rewards=RewardConfig(**data.get("rewards", {})),
            model=ModelConfig(**{k: tuple(v) if k == "mlp_hidden_sizes" else v 
                                for k, v in data.get("model", {}).items()}),
        )


# Global default configuration instance
config = BattleFactoryConfig()


# Button constants (kept here for centralization)
class Buttons:
    """GBA button bitmask constants."""
    A = 1
    B = 2
    SELECT = 4
    START = 8
    RIGHT = 16
    LEFT = 32
    UP = 64
    DOWN = 128
    R = 256
    L = 512
    
    @classmethod
    def name(cls, button: int) -> str:
        """Get button name from bitmask."""
        names = {
            cls.A: "A",
            cls.B: "B",
            cls.SELECT: "SELECT",
            cls.START: "START",
            cls.RIGHT: "→",
            cls.LEFT: "←",
            cls.UP: "↑",
            cls.DOWN: "↓",
            cls.R: "R",
            cls.L: "L",
        }
        return names.get(button, f"BTN_{button}")

