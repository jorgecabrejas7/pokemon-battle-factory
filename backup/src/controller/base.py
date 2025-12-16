"""
Base Controller - Common functionality for all controller types.

This module provides the BaseController class with shared logic for:
- Connection management
- State tracking
- Observation building
- Memory reading

Usage:
    # Don't use directly - subclass instead
    class MyController(BaseController):
        def step_battle(self, agent):
            ...
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING
import numpy as np

from ..core.enums import GamePhase, BattleOutcome
from ..core.dataclasses import BattleState, FactoryState
from ..core.exceptions import DisconnectedError, InvalidStateError
from ..config import config

from .input import InputController
from .state_machine import StateMachine, detect_phase_from_memory

if TYPE_CHECKING:
    from ..backends.emerald.backend import EmeraldBackend
    from ..backends.emerald.memory_reader import RentalMon

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    """Statistics for a Battle Factory run."""
    win_streak: int = 0
    current_battle: int = 0  # 0-6 within round
    battles_won: int = 0
    battles_lost: int = 0
    total_turns: int = 0
    pokemon_fainted_enemy: int = 0
    pokemon_fainted_player: int = 0
    swaps_made: int = 0
    
    def reset(self) -> None:
        """Reset all stats."""
        self.win_streak = 0
        self.current_battle = 0
        self.battles_won = 0
        self.battles_lost = 0
        self.total_turns = 0
        self.pokemon_fainted_enemy = 0
        self.pokemon_fainted_player = 0
        self.swaps_made = 0


@dataclass
class BattleStats:
    """Statistics for a single battle."""
    turn_count: int = 0
    total_reward: float = 0.0
    damage_dealt: float = 0.0
    damage_taken: float = 0.0
    enemy_faints: int = 0
    player_faints: int = 0


class BaseController:
    """
    Base controller with common Battle Factory functionality.
    
    Provides:
    - Backend connection management
    - State machine for phase tracking
    - Input controller for button presses
    - Memory reading utilities
    - Observation building
    - Statistics tracking
    
    Subclasses should implement specific step methods.
    """
    
    def __init__(
        self,
        backend: Optional[EmeraldBackend] = None,
        verbose: bool = False,
    ):
        """
        Initialize base controller.
        
        Args:
            backend: EmeraldBackend instance (creates new if None)
            verbose: Enable verbose logging
        """
        self._backend: Optional[EmeraldBackend] = backend
        self.verbose = verbose
        
        # State management
        self._state_machine = StateMachine()
        self._connected = False
        
        # Input controller (set after connection)
        self._input: Optional[InputController] = None
        
        # Statistics
        self.run_stats = RunStats()
        self.battle_stats = BattleStats()
        
        # Cached states
        self._cached_battle_state: Optional[BattleState] = None
        self._cached_factory_state: Optional[FactoryState] = None
        
        # HP tracking for reward calculation
        self._last_player_hp = [0, 0, 0]
        self._last_enemy_hp = 0.0
        
        # Hidden state for recurrent agents
        self.tactician_hidden_state = None
    
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def backend(self) -> EmeraldBackend:
        """Get backend, raising if not connected."""
        if self._backend is None:
            raise DisconnectedError("Backend not initialized")
        return self._backend
    
    @property
    def input(self) -> InputController:
        """Get input controller."""
        if self._input is None:
            raise DisconnectedError("Not connected")
        return self._input
    
    @property
    def phase(self) -> GamePhase:
        """Current game phase."""
        return self._state_machine.phase
    
    @property
    def is_connected(self) -> bool:
        """Whether connected to emulator."""
        return self._connected and self._backend is not None
    
    @property
    def is_run_complete(self) -> bool:
        """Whether current run has ended."""
        return self.phase.is_terminal
    
    @property
    def is_in_battle(self) -> bool:
        """Whether currently in battle."""
        return self.phase.is_battle_phase
    
    @property
    def win_streak(self) -> int:
        """Current win streak."""
        return self.run_stats.win_streak
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    def connect(
        self, 
        host: str | None = None, 
        port: int | None = None
    ) -> bool:
        """
        Connect to emulator.
        
        Args:
            host: mGBA host (default from config)
            port: mGBA port (default from config)
            
        Returns:
            True if connected successfully
        """
        host = host or config.network.host
        port = port or config.network.port
        
        logger.info(f"Connecting to {host}:{port}...")
        
        try:
            if self._backend is None:
                from ..backends.emerald.backend import EmeraldBackend
                self._backend = EmeraldBackend(host=host, port=port)
            
            self._backend.connect()
            self._input = InputController(self._backend, verbose=self.verbose)
            self._connected = True
            
            # Detect initial state
            detected = detect_phase_from_memory(self._backend)
            self._state_machine.transition_to(detected, force=True)
            
            logger.info(f"Connected, detected phase: {self.phase.name}")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._connected = False
            return False
    
    def disconnect(self) -> None:
        """Disconnect from emulator."""
        if self._backend:
            self._backend.disconnect()
        self._connected = False
        self._input = None
        self._state_machine.reset()
        logger.info("Disconnected")
    
    def _ensure_connected(self) -> None:
        """Raise if not connected."""
        if not self.is_connected:
            raise DisconnectedError()
    
    # =========================================================================
    # State Management
    # =========================================================================
    
    def transition_to(self, phase: GamePhase, force: bool = False) -> None:
        """Transition to a new phase."""
        self._state_machine.transition_to(phase, force=force)
    
    def detect_phase(self) -> GamePhase:
        """Detect current phase from memory."""
        if not self.is_connected:
            return GamePhase.UNINITIALIZED
        return detect_phase_from_memory(self._backend)
    
    # =========================================================================
    # Memory Reading
    # =========================================================================
    
    def _is_waiting_for_input(self) -> bool:
        """Check if game is waiting for input."""
        return self.backend.is_waiting_for_input()
    
    def _get_battle_outcome(self) -> BattleOutcome:
        """Get current battle outcome."""
        return self.backend.get_battle_outcome()
    
    def refresh_battle_state(self) -> BattleState:
        """Read current battle state."""
        self._cached_battle_state = self.backend.read_battle_state()
        return self._cached_battle_state
    
    def refresh_factory_state(self) -> FactoryState:
        """Read current factory state."""
        self._cached_factory_state = self.backend.read_factory_state()
        self.run_stats.win_streak = self._cached_factory_state.win_streak
        return self._cached_factory_state
    
    def read_rental_mons(self) -> list[RentalMon]:
        """Read rental Pokemon during draft."""
        return self.backend.memory.read_rental_mons()
    
    # =========================================================================
    # Observation Building
    # =========================================================================
    
    def get_battle_observation(self) -> np.ndarray:
        """
        Build observation vector for battle phase.
        
        Returns:
            Numpy array of battle features
        """
        state = self.refresh_battle_state()
        features = []
        
        norm = config.normalization
        
        # Player Pokemon features
        if state.active_pokemon:
            p = state.active_pokemon
            features.extend([
                p.species_id / norm.species_divisor,
                p.current_hp / max(p.hp, 1),
                p.attack / norm.stat_divisor,
                p.defense / norm.stat_divisor,
                p.sp_attack / norm.stat_divisor,
                p.sp_defense / norm.stat_divisor,
                p.speed / norm.stat_divisor,
                p.level / norm.level_divisor,
            ])
            # Moves (4 move IDs)
            for move in p.moves[:4]:
                features.append(move.move_id / norm.move_divisor if move else 0.0)
        else:
            features.extend([0.0] * 12)
        
        # Enemy Pokemon features
        if state.enemy_active_pokemon:
            e = state.enemy_active_pokemon
            features.extend([
                e.species_id / norm.species_divisor,
                e.hp_percentage / 100.0,
                e.level / norm.level_divisor,
            ])
            # Revealed moves (up to 4)
            for i in range(4):
                if i < len(e.revealed_moves):
                    features.append(e.revealed_moves[i].move_id / norm.move_divisor)
                else:
                    features.append(0.0)
        else:
            features.extend([0.0] * 7)
        
        # Context
        features.extend([
            self.run_stats.win_streak / norm.streak_divisor,
            self.battle_stats.turn_count / norm.turn_divisor,
            state.weather.value / norm.weather_divisor if state.weather else 0.0,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_draft_observation(self) -> np.ndarray:
        """
        Build observation vector for draft phase.
        
        Returns:
            Numpy array of rental Pokemon features
        """
        rentals = self.read_rental_mons()
        features = []
        
        norm = config.normalization
        
        # Encode each rental
        for i in range(6):
            if i < len(rentals):
                features.extend([
                    rentals[i].frontier_mon_id / norm.frontier_mon_divisor,
                    rentals[i].iv_spread / norm.iv_divisor,
                    rentals[i].ability_num / 2.0,
                ])
            else:
                features.extend([0.0, 0.0, 0.0])
        
        # Context
        features.extend([
            self.run_stats.win_streak / norm.streak_divisor,
            self.run_stats.current_battle / config.game.battles_per_round,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_swap_observation(self) -> np.ndarray:
        """
        Build observation vector for swap phase.
        
        Returns:
            Numpy array of team + candidate features
        """
        # Read current team
        party = self.backend.memory.read_player_party()
        features = []
        
        norm = config.normalization
        
        # Current team (3 Pokemon)
        for i in range(3):
            if i < len(party):
                features.extend([
                    party[i].species_id / norm.species_divisor,
                    party[i].current_hp / max(party[i].max_hp, 1),
                ])
            else:
                features.extend([0.0, 0.0])
        
        # Context
        features.extend([
            self.run_stats.win_streak / norm.streak_divisor,
            self.run_stats.current_battle / config.game.battles_per_round,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_action_mask(self) -> np.ndarray:
        """
        Get valid action mask for battle.
        
        Returns:
            Binary mask [Move1, Move2, Move3, Move4, Switch1, Switch2]
        """
        mask = np.ones(6, dtype=np.float32)
        
        state = self._cached_battle_state
        if state and state.active_pokemon:
            # Check move PP
            for i, move in enumerate(state.active_pokemon.moves[:4]):
                if move is None or move.current_pp <= 0:
                    mask[i] = 0.0
            
            # Check switch availability
            party = state.party
            if len(party) < 2:
                mask[4] = 0.0
                mask[5] = 0.0
            elif len(party) < 3:
                mask[5] = 0.0
        
        return mask
    
    # =========================================================================
    # Reward Calculation
    # =========================================================================
    
    def calculate_battle_reward(
        self,
        pre_enemy_hp: float,
        post_enemy_hp: float,
        pre_player_hp: int,
        post_player_hp: int,
        outcome: BattleOutcome,
    ) -> float:
        """
        Calculate reward for a battle action.
        
        Args:
            pre_enemy_hp: Enemy HP % before action
            post_enemy_hp: Enemy HP % after action
            pre_player_hp: Player HP before action
            post_player_hp: Player HP after action
            outcome: Battle outcome
            
        Returns:
            Reward value
        """
        reward = 0.0
        rewards = config.rewards
        
        # Outcome rewards
        if outcome == BattleOutcome.WIN:
            reward += rewards.win_base_reward * (1.0 + self.run_stats.win_streak * rewards.win_streak_multiplier)
        elif outcome == BattleOutcome.LOSS:
            reward -= rewards.loss_base_penalty * (1.0 + self.run_stats.win_streak * rewards.loss_streak_multiplier)
        
        # Damage rewards
        damage_dealt = max(0, pre_enemy_hp - post_enemy_hp)
        damage_taken = max(0, pre_player_hp - post_player_hp)
        reward += damage_dealt * rewards.damage_dealt_multiplier
        reward -= damage_taken * rewards.damage_taken_multiplier
        
        # Faint rewards
        if pre_enemy_hp > 0 and post_enemy_hp <= 0:
            reward += rewards.enemy_faint_bonus
            self.run_stats.pokemon_fainted_enemy += 1
            self.battle_stats.enemy_faints += 1
        
        if pre_player_hp > 0 and post_player_hp <= 0:
            reward -= rewards.player_faint_penalty
            self.run_stats.pokemon_fainted_player += 1
            self.battle_stats.player_faints += 1
        
        return reward
    
    # =========================================================================
    # Run Management
    # =========================================================================
    
    def reset_run(self) -> None:
        """Reset for a new Battle Factory run."""
        self.run_stats.reset()
        self.battle_stats = BattleStats()
        self.tactician_hidden_state = None
        self._cached_battle_state = None
        self._cached_factory_state = None
        self._last_player_hp = [0, 0, 0]
        self._last_enemy_hp = 0.0
    
    def reset_battle(self) -> None:
        """Reset for a new battle within a run."""
        self.battle_stats = BattleStats()
        self.tactician_hidden_state = None
        self._last_player_hp = [0, 0, 0]
        self._last_enemy_hp = 0.0
    
    # =========================================================================
    # Waiting Utilities
    # =========================================================================
    
    def wait_for_input(self, timeout: float | None = None) -> bool:
        """
        Wait until input is needed or battle ends.
        
        Args:
            timeout: Timeout in seconds (default from config)
            
        Returns:
            True if waiting for input, False if battle ended
        """
        import time
        
        timeout = timeout or config.timing.input_timeout
        start = time.time()
        
        while (time.time() - start) < timeout:
            outcome = self._get_battle_outcome()
            if outcome != BattleOutcome.ONGOING:
                return False
            
            if self._is_waiting_for_input():
                self.transition_to(GamePhase.IN_BATTLE, force=True)
                return True
            
            self.transition_to(GamePhase.BATTLE_ANIMATING, force=True)
            time.sleep(0.1)
        
        logger.warning("Timeout waiting for input")
        return False
    
    def wait_for_battle_start(self, timeout: float | None = None) -> bool:
        """
        Wait for battle to start.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            True if battle started
        """
        import time
        
        timeout = timeout or config.timing.battle_start_timeout
        start = time.time()
        
        while (time.time() - start) < timeout:
            battle_mons = self.backend.memory.read_battle_mons()
            if len(battle_mons) >= 2 and battle_mons[0].species_id > 0:
                self.transition_to(GamePhase.IN_BATTLE, force=True)
                return True
            time.sleep(0.1)
        
        logger.warning("Timeout waiting for battle start")
        return False

