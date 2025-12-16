"""
Battle Factory System - Orchestrates the complete game loop.

This is the main coordinator that manages:
1. Draft Phase: Drafter agent selects 3 Pokemon from 6 rentals
2. Battle Loop: Tactician agent makes turn-by-turn decisions
3. Post-Battle: Handle wins (swaps) and losses (reset)

Designed for single-emulator operation with manual game loop
(not vectorized environments).
"""

import time
import logging
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
import numpy as np

from .backends.emerald.backend import EmeraldBackend
from .backends.emerald.memory_reader import MemoryReader, BattleMon, RentalMon
from .core.enums import BattleOutcome, ScreenType
from .core.dataclasses import BattleState, FactoryState

logger = logging.getLogger(__name__)


class GamePhase(Enum):
    """Current phase of the Battle Factory run."""
    INITIALIZING = auto()
    DRAFT = auto()         # Selecting initial 3 Pokemon
    PRE_BATTLE = auto()    # Navigating menus before battle
    BATTLE = auto()        # In battle, Tactician acting
    POST_BATTLE = auto()   # Battle ended, checking outcome
    SWAP = auto()          # Won battle, deciding on swap
    RUN_COMPLETE = auto()  # Run ended (win or loss)


@dataclass
class TacticianTransition:
    """Single transition for Tactician agent."""
    observation: np.ndarray
    action: int
    reward: float
    next_observation: np.ndarray
    done: bool
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DrafterTransition:
    """Single transition for Drafter agent."""
    observation: np.ndarray
    action: np.ndarray  # Multi-discrete for draft
    reward: float
    next_observation: np.ndarray
    done: bool
    info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunStats:
    """Statistics for a single Battle Factory run."""
    streak: int = 0
    battles_won: int = 0
    battles_lost: int = 0
    total_turns: int = 0
    pokemon_fainted_enemy: int = 0
    pokemon_fainted_player: int = 0
    swaps_made: int = 0


class BattleFactorySystem:
    """
    Main orchestrator for Battle Factory RL training.
    
    Manages the game loop for a single emulator instance:
    1. Coordinates between Drafter and Tactician agents
    2. Handles phase transitions
    3. Computes rewards
    4. Stores transitions for training
    
    Usage:
        system = BattleFactorySystem(backend)
        system.connect()
        
        while training:
            # Draft phase
            draft_obs = system.get_draft_observation()
            draft_action = drafter.act(draft_obs)
            system.execute_draft(draft_action)
            
            # Battle phase
            while not system.is_battle_over():
                battle_obs = system.get_battle_observation()
                action = tactician.act(battle_obs, hidden_state)
                reward, done = system.execute_battle_action(action)
            
            # Post-battle
            if system.did_win():
                swap_obs = system.get_swap_observation()
                swap_action = drafter.act(swap_obs)
                system.execute_swap(swap_action)
    """
    
    # Button masks for input
    BUTTON_A = 1
    BUTTON_B = 2
    BUTTON_SELECT = 4
    BUTTON_START = 8
    BUTTON_RIGHT = 16
    BUTTON_LEFT = 32
    BUTTON_UP = 64
    BUTTON_DOWN = 128
    
    # Timing constants (frames)
    FRAMES_BUTTON_HOLD = 3
    FRAMES_WAIT_SHORT = 10
    FRAMES_WAIT_LONG = 60
    
    def __init__(
        self,
        backend: Optional[EmeraldBackend] = None,
        max_streak: int = 42,  # Factory Brain appears at 21 and 42
    ):
        self.backend = backend or EmeraldBackend()
        self.max_streak = max_streak
        
        # State tracking
        self.phase = GamePhase.INITIALIZING
        self.run_stats = RunStats()
        self.current_streak = 0
        self.current_battle = 0  # 0-6 within a round
        
        # Battle state tracking
        self.battle_turn = 0
        self.last_player_hp = [0, 0, 0]  # HP tracking for damage calculation
        self.last_enemy_hp = [0, 0, 0]
        self.tactician_hidden_state = None
        
        # Transition buffers
        self.tactician_buffer: List[TacticianTransition] = []
        self.drafter_buffer: List[DrafterTransition] = []
        
        # Observation caching
        self._last_battle_state: Optional[BattleState] = None
        self._last_factory_state: Optional[FactoryState] = None
    
    def connect(self) -> bool:
        """Connect to the emulator."""
        try:
            self.backend.connect("")
            self.phase = GamePhase.INITIALIZING
            logger.info("Connected to emulator")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False
    
    # =========================================================================
    # Input Helpers
    # =========================================================================
    
    def _press_button(self, button: int, hold_frames: int = None):
        """Press a button and release."""
        hold = hold_frames or self.FRAMES_BUTTON_HOLD
        self.backend._send_command(f"SET_INPUT {button}")
        self.backend.advance_frame(hold)
        self.backend._send_command("SET_INPUT 0")
        self.backend.advance_frame(self.FRAMES_WAIT_SHORT)
    
    def _press_a(self):
        """Press A button."""
        self._press_button(self.BUTTON_A)
    
    def _press_b(self):
        """Press B button."""
        self._press_button(self.BUTTON_B)
    
    def _press_direction(self, direction: str):
        """Press a direction."""
        buttons = {
            'up': self.BUTTON_UP,
            'down': self.BUTTON_DOWN,
            'left': self.BUTTON_LEFT,
            'right': self.BUTTON_RIGHT,
        }
        self._press_button(buttons[direction])
    
    def _navigate_menu(self, target_index: int, current_index: int = 0, vertical: bool = True):
        """Navigate a menu to a specific index."""
        diff = target_index - current_index
        direction = 'down' if diff > 0 else 'up'
        if not vertical:
            direction = 'right' if diff > 0 else 'left'
        
        for _ in range(abs(diff)):
            self._press_direction(direction)
    
    # =========================================================================
    # Memory Reading
    # =========================================================================
    
    def _is_waiting_for_input(self) -> bool:
        """Check if game is waiting for player input."""
        response = self.backend._send_command("IS_WAITING_INPUT")
        return response == "YES"
    
    def _get_battle_outcome(self) -> BattleOutcome:
        """Get current battle outcome."""
        response = self.backend._send_command("GET_BATTLE_OUTCOME")
        try:
            outcome_val = int(response)
            return BattleOutcome(outcome_val) if outcome_val in [0, 1, 2, 3, 4] else BattleOutcome.ONGOING
        except ValueError:
            return BattleOutcome.ONGOING
    
    def _read_rng(self) -> int:
        """Read current RNG value."""
        response = self.backend._send_command("READ_RNG")
        try:
            return int(response)
        except ValueError:
            return 0
    
    def _read_last_moves(self) -> Tuple[int, int]:
        """Read last move and attacker."""
        response = self.backend._send_command("READ_LAST_MOVES")
        try:
            move_id, attacker = response.split(',')
            return int(move_id), int(attacker)
        except ValueError:
            return 0, 0
    
    def refresh_battle_state(self) -> BattleState:
        """Read current battle state from memory."""
        self._last_battle_state = self.backend.read_battle_state()
        return self._last_battle_state
    
    def refresh_factory_state(self) -> FactoryState:
        """Read current factory state from memory."""
        self._last_factory_state = self.backend.read_factory_state()
        self.current_streak = self._last_factory_state.win_streak
        return self._last_factory_state
    
    # =========================================================================
    # Phase Management
    # =========================================================================
    
    def wait_for_input(self, timeout_frames: int = 3600) -> bool:
        """
        Run emulator until input is required or battle ends.
        
        Returns True if waiting for input, False if battle ended.
        """
        frames = 0
        while frames < timeout_frames:
            outcome = self._get_battle_outcome()
            if outcome != BattleOutcome.ONGOING:
                return False
            
            if self._is_waiting_for_input():
                return True
            
            self.backend.advance_frame(5)
            frames += 5
        
        logger.warning("Timeout waiting for input")
        return False
    
    def detect_phase(self) -> GamePhase:
        """
        Detect current game phase from memory state.
        
        This is a simplified detection - in practice you'd need
        to check more memory addresses to reliably detect phase.
        """
        # Check if in battle
        battle_mons = self.backend.memory.read_battle_mons()
        if len(battle_mons) >= 2 and battle_mons[0].species_id > 0:
            outcome = self._get_battle_outcome()
            if outcome == BattleOutcome.ONGOING:
                return GamePhase.BATTLE
            else:
                return GamePhase.POST_BATTLE
        
        # Check rental mons (draft phase)
        rentals = self.backend.memory.read_rental_mons()
        if len(rentals) > 0:
            return GamePhase.DRAFT
        
        return GamePhase.INITIALIZING
    
    # =========================================================================
    # Draft Phase
    # =========================================================================
    
    def get_draft_observation(self) -> np.ndarray:
        """
        Get observation for draft phase.
        
        Returns flattened array of:
        - 6 rental Pokemon features
        - Current streak context
        - Round/battle context
        """
        rentals = self.backend.memory.read_rental_mons()
        
        # Encode each rental (simplified - just IDs for now)
        rental_features = []
        for i in range(6):
            if i < len(rentals):
                rental_features.extend([
                    rentals[i].frontier_mon_id / 900.0,  # Normalize
                    rentals[i].iv_spread / 31.0,
                    rentals[i].ability_num,
                ])
            else:
                rental_features.extend([0.0, 0.0, 0.0])
        
        # Context
        context = [
            self.current_streak / self.max_streak,
            self.current_battle / 7.0,
        ]
        
        return np.array(rental_features + context, dtype=np.float32)
    
    def execute_draft(self, selections: np.ndarray) -> bool:
        """
        Execute draft action - select 3 Pokemon from 6.
        
        Args:
            selections: Array of 3 indices [0-5] indicating which Pokemon to pick
            
        Returns:
            True if successful
        """
        # Validate selections
        if len(selections) != 3:
            logger.error(f"Invalid draft selection: need 3, got {len(selections)}")
            return False
        
        # Navigate and select each Pokemon
        for i, idx in enumerate(selections):
            # Navigate to Pokemon
            self._navigate_menu(int(idx), current_index=0)
            # Press A to select
            self._press_a()
            time.sleep(0.05)
        
        # Confirm selection
        self._press_a()
        self._press_a()
        
        self.phase = GamePhase.PRE_BATTLE
        logger.info(f"Draft complete: selected {selections}")
        return True
    
    # =========================================================================
    # Battle Phase
    # =========================================================================
    
    def get_battle_observation(self) -> np.ndarray:
        """
        Get observation for battle phase.
        
        Returns flattened array of:
        - Player active Pokemon features
        - Enemy active Pokemon features
        - Battle context (weather, turn, streak)
        - Valid action mask
        """
        state = self.refresh_battle_state()
        
        features = []
        
        # Player Pokemon features
        if state.active_pokemon:
            p = state.active_pokemon
            features.extend([
                p.species_id / 400.0,
                p.current_hp / max(p.hp, 1),
                p.attack / 255.0,
                p.defense / 255.0,
                p.sp_attack / 255.0,
                p.sp_defense / 255.0,
                p.speed / 255.0,
                p.level / 100.0,
            ])
            # Moves
            for move in p.moves[:4]:
                features.append(move.move_id / 400.0 if move else 0.0)
        else:
            features.extend([0.0] * 12)
        
        # Enemy Pokemon features
        if state.enemy_active_pokemon:
            e = state.enemy_active_pokemon
            features.extend([
                e.species_id / 400.0,
                e.hp_percentage / 100.0,
                e.level / 100.0,
            ])
            # Revealed moves
            for i in range(4):
                if i < len(e.revealed_moves):
                    features.append(e.revealed_moves[i].move_id / 400.0)
                else:
                    features.append(0.0)
        else:
            features.extend([0.0] * 7)
        
        # Context
        features.extend([
            self.current_streak / self.max_streak,
            self.battle_turn / 100.0,
            state.weather.value / 5.0 if state.weather else 0.0,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_action_mask(self) -> np.ndarray:
        """
        Get valid action mask for battle.
        
        Actions: [Move1, Move2, Move3, Move4, Switch1, Switch2]
        """
        mask = np.ones(6, dtype=np.float32)
        
        state = self._last_battle_state
        if state and state.active_pokemon:
            # Check move PP
            for i, move in enumerate(state.active_pokemon.moves[:4]):
                if move is None or move.current_pp <= 0:
                    mask[i] = 0.0
            
            # Check if can switch (simplified)
            # In Battle Factory, you always have 3 Pokemon
            # Switch is valid if bench Pokemon have HP
            if len(state.party) < 2:
                mask[4] = 0.0
                mask[5] = 0.0
        
        return mask
    
    def execute_battle_action(self, action: int) -> Tuple[float, bool]:
        """
        Execute a battle action.
        
        Args:
            action: 0-3 = Move 1-4, 4-5 = Switch to Pokemon 1-2
            
        Returns:
            (reward, done) tuple
        """
        # Record pre-action state
        pre_state = self.refresh_battle_state()
        pre_enemy_hp = pre_state.enemy_active_pokemon.hp_percentage if pre_state.enemy_active_pokemon else 0
        pre_player_hp = pre_state.active_pokemon.current_hp if pre_state.active_pokemon else 0
        
        # Execute action
        if action < 4:
            # Move action
            self._execute_move(action)
        else:
            # Switch action
            self._execute_switch(action - 4)
        
        # Wait for next input or battle end
        input_ready = self.wait_for_input()
        
        # Get outcome
        outcome = self._get_battle_outcome()
        done = outcome != BattleOutcome.ONGOING
        
        # Read post-action state
        post_state = self.refresh_battle_state()
        post_enemy_hp = post_state.enemy_active_pokemon.hp_percentage if post_state.enemy_active_pokemon else 0
        post_player_hp = post_state.active_pokemon.current_hp if post_state.active_pokemon else 0
        
        # Calculate reward
        reward = self._calculate_battle_reward(
            pre_enemy_hp, post_enemy_hp,
            pre_player_hp, post_player_hp,
            outcome,
        )
        
        self.battle_turn += 1
        self.run_stats.total_turns += 1
        
        if done:
            self.phase = GamePhase.POST_BATTLE
        
        return reward, done
    
    def _execute_move(self, move_index: int):
        """Execute a move selection."""
        # Ensure on Fight menu
        self._press_a()  # Select Fight
        
        # Navigate to move
        row = move_index // 2
        col = move_index % 2
        if row > 0:
            self._press_direction('down')
        if col > 0:
            self._press_direction('right')
        
        # Confirm move
        self._press_a()
    
    def _execute_switch(self, pokemon_index: int):
        """Execute a Pokemon switch."""
        # Navigate to Pokemon menu
        self._press_direction('right')  # From Fight to Pokemon
        self._press_a()
        
        # Navigate to Pokemon (index 0 is active, so +1)
        self._navigate_menu(pokemon_index + 1, current_index=0)
        
        # Select and confirm switch
        self._press_a()
        self._press_a()  # Confirm switch
    
    def _calculate_battle_reward(
        self,
        pre_enemy_hp: float,
        post_enemy_hp: float,
        pre_player_hp: int,
        post_player_hp: int,
        outcome: BattleOutcome,
    ) -> float:
        """
        Calculate reward for a battle action.
        
        Reward structure:
        - Win: +10 * (1 + streak * 0.1)
        - Loss: -10 * (1 + streak * 0.2)
        - Damage dealt: Small positive
        - Damage taken: Small negative
        - Faint enemy: +1
        - Self fainted: -1
        """
        reward = 0.0
        
        # Outcome rewards
        if outcome == BattleOutcome.WIN:
            reward += 10.0 * (1.0 + self.current_streak * 0.1)
            self.run_stats.battles_won += 1
        elif outcome == BattleOutcome.LOSS:
            reward -= 10.0 * (1.0 + self.current_streak * 0.2)
            self.run_stats.battles_lost += 1
        
        # Damage rewards (scaled by 0.01)
        damage_dealt = max(0, pre_enemy_hp - post_enemy_hp)
        damage_taken = max(0, pre_player_hp - post_player_hp)
        reward += damage_dealt * 0.01
        reward -= damage_taken * 0.0005  # Less penalty for taking damage
        
        # Faint rewards
        if pre_enemy_hp > 0 and post_enemy_hp <= 0:
            reward += 1.0
            self.run_stats.pokemon_fainted_enemy += 1
        if pre_player_hp > 0 and post_player_hp <= 0:
            reward -= 0.5
            self.run_stats.pokemon_fainted_player += 1
        
        return reward
    
    # =========================================================================
    # Post-Battle / Swap Phase
    # =========================================================================
    
    def handle_post_battle(self) -> Tuple[float, bool]:
        """
        Handle post-battle phase.
        
        Returns:
            (drafter_reward, run_complete) tuple
        """
        outcome = self._get_battle_outcome()
        
        if outcome == BattleOutcome.WIN:
            self.current_streak += 1
            self.current_battle += 1
            drafter_reward = 1.0  # Win reward for drafter
            
            # Check if round complete (7 battles)
            if self.current_battle >= 7:
                self.current_battle = 0
                # May have swap opportunity
                self.phase = GamePhase.SWAP
            else:
                self.phase = GamePhase.PRE_BATTLE
            
            run_complete = self.current_streak >= self.max_streak
            
        else:  # Loss
            drafter_reward = -1.0
            run_complete = True
            self.phase = GamePhase.RUN_COMPLETE
        
        return drafter_reward, run_complete
    
    def get_swap_observation(self) -> np.ndarray:
        """
        Get observation for swap decision.
        
        Similar to draft but includes current team info.
        """
        # Get current team from player party
        party = self.backend.memory.read_player_party()
        
        # Get swap candidates (opponent's Pokemon)
        # In Battle Factory, you can swap with opponent after winning
        # This would need additional memory reading
        
        # Simplified observation
        features = []
        
        # Current team
        for i in range(3):
            if i < len(party):
                features.extend([
                    party[i].species_id / 400.0,
                    party[i].current_hp / max(party[i].max_hp, 1),
                ])
            else:
                features.extend([0.0, 0.0])
        
        # Context
        features.extend([
            self.current_streak / self.max_streak,
            self.current_battle / 7.0,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def execute_swap(self, swap_action: int) -> bool:
        """
        Execute swap decision.
        
        Args:
            swap_action: 0 = don't swap, 1-3 = swap slot N with offered Pokemon
            
        Returns:
            True if successful
        """
        if swap_action == 0:
            # Don't swap - press B to decline
            self._press_b()
        else:
            # Navigate to swap slot and confirm
            self._navigate_menu(swap_action - 1)
            self._press_a()
            self._press_a()  # Confirm
            self.run_stats.swaps_made += 1
        
        self.phase = GamePhase.PRE_BATTLE
        logger.info(f"Swap decision: {swap_action}")
        return True
    
    # =========================================================================
    # Training Loop Helpers
    # =========================================================================
    
    def reset_run(self):
        """Reset for a new Battle Factory run."""
        self.run_stats = RunStats()
        self.current_streak = 0
        self.current_battle = 0
        self.battle_turn = 0
        self.tactician_hidden_state = None
        self.tactician_buffer.clear()
        self.drafter_buffer.clear()
        self.phase = GamePhase.INITIALIZING
        
        # Optionally reset emulator to save state
        # self.backend.reset()
    
    def reset_battle(self):
        """Reset for a new battle within a run."""
        self.battle_turn = 0
        self.tactician_hidden_state = None
        self.last_player_hp = [0, 0, 0]
        self.last_enemy_hp = [0, 0, 0]
    
    def get_tactician_transitions(self) -> List[TacticianTransition]:
        """Get buffered Tactician transitions for training."""
        transitions = self.tactician_buffer.copy()
        self.tactician_buffer.clear()
        return transitions
    
    def get_drafter_transitions(self) -> List[DrafterTransition]:
        """Get buffered Drafter transitions for training."""
        transitions = self.drafter_buffer.copy()
        self.drafter_buffer.clear()
        return transitions
    
    def run_training_episode(
        self,
        drafter_policy,  # Callable that takes obs and returns action
        tactician_policy,  # Callable that takes (obs, hidden_state) and returns (action, new_hidden)
    ) -> RunStats:
        """
        Run a complete Battle Factory episode.
        
        This is a convenience method for training that handles
        the full game loop with the provided policies.
        """
        self.reset_run()
        
        # Draft phase
        self.phase = GamePhase.DRAFT
        draft_obs = self.get_draft_observation()
        draft_action = drafter_policy(draft_obs)
        self.execute_draft(draft_action)
        
        run_complete = False
        
        while not run_complete:
            # Wait for battle to start
            self.phase = GamePhase.PRE_BATTLE
            while not self._is_waiting_for_input():
                self.backend.advance_frame(10)
                if self._get_battle_outcome() != BattleOutcome.ONGOING:
                    break
            
            # Battle loop
            self.reset_battle()
            self.phase = GamePhase.BATTLE
            
            battle_done = False
            while not battle_done:
                obs = self.get_battle_observation()
                mask = self.get_action_mask()
                
                action, self.tactician_hidden_state = tactician_policy(
                    obs, 
                    self.tactician_hidden_state,
                    mask
                )
                
                reward, battle_done = self.execute_battle_action(action)
                
                # Store transition
                next_obs = self.get_battle_observation()
                self.tactician_buffer.append(TacticianTransition(
                    observation=obs,
                    action=action,
                    reward=reward,
                    next_observation=next_obs,
                    done=battle_done,
                ))
            
            # Post-battle
            drafter_reward, run_complete = self.handle_post_battle()
            
            # Swap phase (if applicable)
            if self.phase == GamePhase.SWAP:
                swap_obs = self.get_swap_observation()
                swap_action = drafter_policy(swap_obs)
                self.execute_swap(swap_action)
        
        logger.info(f"Episode complete: streak={self.run_stats.streak}, "
                   f"won={self.run_stats.battles_won}, lost={self.run_stats.battles_lost}")
        
        return self.run_stats

