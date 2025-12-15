"""
Game Controller - Central orchestrator for Battle Factory gameplay.

This module provides a clean, step-based interface for controlling
the Battle Factory game loop. It handles:

1. Initialization - Connecting and navigating to the draft screen
2. Phase-level steps - Draft, Battle, Swap as discrete units
3. Turn-level steps - Individual battle turn control
4. State machine - Tracking current game state
5. Agent integration - Pluggable decision makers

Usage:
    controller = GameController()
    controller.connect()
    controller.initialize_to_draft()
    
    # Phase-level control
    controller.step_draft(drafter_agent)
    while not controller.is_run_complete():
        controller.step_battle(tactician_agent)
        if controller.state == GameState.SWAP_SCREEN:
            controller.step_swap(drafter_agent)
    
    # Or turn-level control
    while controller.state == GameState.IN_BATTLE:
        obs = controller.get_observation()
        action = agent(obs)
        controller.step_turn(action)
"""

import logging
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple, Union
import numpy as np

from .backends.emerald.backend import EmeraldBackend
from .backends.emerald.memory_reader import MemoryReader, BattleMon, RentalMon
from .core.enums import BattleOutcome
from .core.dataclasses import BattleState, FactoryState

logger = logging.getLogger(__name__)


# =============================================================================
# Game State Machine
# =============================================================================

class GameState(Enum):
    """
    All possible states in the Battle Factory game loop.
    
    The state machine transitions:
    UNINITIALIZED -> TITLE_SCREEN -> OVERWORLD -> FACTORY_LOBBY -> 
    DRAFT_SCREEN -> BATTLE_READY -> IN_BATTLE -> BATTLE_END ->
    (SWAP_SCREEN -> BATTLE_READY) or RUN_COMPLETE
    """
    UNINITIALIZED = auto()      # Not connected to emulator
    TITLE_SCREEN = auto()       # At game title/intro screens
    OVERWORLD = auto()          # Walking around in the game world
    FACTORY_LOBBY = auto()      # Inside Battle Factory building
    CHALLENGE_SETUP = auto()    # Selecting challenge options (level, mode)
    DRAFT_SCREEN = auto()       # Selecting 3 Pokemon from 6 rentals
    BATTLE_READY = auto()       # About to start a battle
    IN_BATTLE = auto()          # Mid-battle, waiting for player input
    BATTLE_ANIMATING = auto()   # Battle animation playing (no input needed)
    BATTLE_END = auto()         # Battle just ended
    SWAP_SCREEN = auto()        # Can swap a Pokemon with opponent's
    RUN_COMPLETE = auto()       # Run finished (win streak complete or lost)
    ERROR = auto()              # Something went wrong


# =============================================================================
# Result Dataclasses
# =============================================================================

@dataclass
class PhaseResult:
    """Result of executing a game phase (draft, battle, swap)."""
    success: bool
    phase: str
    next_state: GameState
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TurnResult:
    """Result of executing a single battle turn."""
    success: bool
    action_taken: int
    reward: float
    battle_ended: bool
    outcome: Optional[BattleOutcome] = None
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass  
class EpisodeResult:
    """Result of a complete Battle Factory episode."""
    success: bool
    win_streak: int
    battles_won: int
    battles_lost: int
    total_turns: int
    duration_seconds: float
    phases_completed: List[str] = field(default_factory=list)
    error: Optional[str] = None


# =============================================================================
# Agent Type Definitions
# =============================================================================

# Type aliases for agent callables
DrafterAgent = Callable[[np.ndarray, GameState], np.ndarray]
TacticianAgent = Callable[[np.ndarray, GameState, np.ndarray], int]


# =============================================================================
# Game Controller
# =============================================================================

class GameController:
    """
    Central controller for Battle Factory gameplay.
    
    Provides a clean interface for:
    - Connecting to the emulator
    - Auto-navigating to the draft screen
    - Stepping through phases (draft, battle, swap)
    - Stepping through individual battle turns
    - Tracking game state
    - Integrating with any agent (random, trained, interactive)
    
    Example - Full episode with random agents:
        controller = GameController()
        controller.connect()
        controller.initialize_to_draft()
        result = controller.run_episode(random_drafter, random_tactician)
        print(f"Win streak: {result.win_streak}")
    
    Example - Interactive turn-by-turn:
        controller = GameController()
        controller.connect()
        controller.initialize_to_draft()
        controller.step_draft()  # Uses default random agent
        
        while controller.state == GameState.IN_BATTLE:
            obs = controller.get_observation()
            valid = controller.get_valid_actions()
            print(f"Valid actions: {valid}")
            action = int(input("Action: "))
            result = controller.step_turn(action)
            print(f"Reward: {result.reward}")
    """
    
    # Button constants (matching backend ACTION_MAP)
    BUTTON_A = 1
    BUTTON_B = 2
    BUTTON_SELECT = 4
    BUTTON_START = 8
    BUTTON_RIGHT = 16
    BUTTON_LEFT = 32
    BUTTON_UP = 64
    BUTTON_DOWN = 128
    
    # Timing constants (in seconds - game runs continuously)
    TIME_BUTTON_PRESS = 0.08     # How long to hold a button (~5 frames)
    TIME_WAIT_SHORT = 0.25       # Short wait after button
    TIME_WAIT_MEDIUM = 0.5       # Medium wait (menu transitions)
    TIME_WAIT_LONG = 1.0         # Long wait (screen transitions)
    TIME_WAIT_BATTLE = 2.0       # Wait for battle animations
    
    def __init__(
        self,
        backend: Optional[EmeraldBackend] = None,
        auto_wait: bool = True,
        verbose: bool = False,
    ):
        """
        Initialize the game controller.
        
        Args:
            backend: EmeraldBackend instance (creates new if None)
            auto_wait: Whether to automatically wait after actions
            verbose: Enable verbose logging
        """
        self.backend = backend
        self.auto_wait = auto_wait
        self.verbose = verbose
        
        # State tracking
        self._state = GameState.UNINITIALIZED
        self._connected = False
        
        # Run tracking
        self.win_streak = 0
        self.current_battle = 0
        self.current_turn = 0
        self.total_turns = 0
        self.battles_won = 0
        self.battles_lost = 0
        
        # Battle state caching
        self._cached_battle_state: Optional[BattleState] = None
        self._cached_action_mask: Optional[np.ndarray] = None
        self._last_player_hp = [0, 0, 0]
        self._last_enemy_hp = 0.0
        
        # Hidden state for recurrent agents
        self.tactician_hidden_state = None
        
    # =========================================================================
    # Properties
    # =========================================================================
    
    @property
    def state(self) -> GameState:
        """Current game state."""
        return self._state
    
    @property
    def is_connected(self) -> bool:
        """Whether connected to emulator."""
        return self._connected
    
    def is_run_complete(self) -> bool:
        """Whether the current run has ended."""
        return self._state == GameState.RUN_COMPLETE
    
    def is_in_battle(self) -> bool:
        """Whether currently in a battle."""
        return self._state in [GameState.IN_BATTLE, GameState.BATTLE_ANIMATING]
    
    # =========================================================================
    # Connection
    # =========================================================================
    
    def connect(self, host: str = "127.0.0.1", port: int = 7777) -> bool:
        """
        Connect to the mGBA emulator.
        
        Args:
            host: Emulator host address
            port: Emulator port (connector.lua default: 7777)
            
        Returns:
            True if connection successful
        """
        logger.info(f"Connecting to emulator at {host}:{port}...")
        
        try:
            if self.backend is None:
                self.backend = EmeraldBackend()
            
            self.backend.connect("")
            
            # Verify connection
            response = self.backend._send_command("PING")
            if response != "PONG":
                logger.error(f"Unexpected PING response: {response}")
                return False
            
            self._connected = True
            self._state = GameState.TITLE_SCREEN  # Assume at title initially
            logger.info("✓ Connected to emulator")
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._state = GameState.ERROR
            return False
    
    def disconnect(self):
        """Disconnect from the emulator."""
        if self.backend and hasattr(self.backend, 'sock') and self.backend.sock:
            try:
                self.backend.sock.close()
            except:
                pass
        self._connected = False
        self._state = GameState.UNINITIALIZED
        logger.info("Disconnected from emulator")
    
    # =========================================================================
    # Input Helpers
    # =========================================================================
    
    def _press_button(self, button: int, hold_time: float = None, wait_time: float = None):
        """
        Press and release a button.
        
        Args:
            button: Button constant (BUTTON_A, BUTTON_B, etc.)
            hold_time: How long to hold in seconds (default: TIME_BUTTON_PRESS)
            wait_time: How long to wait after in seconds (default: TIME_WAIT_SHORT)
        """
        hold = hold_time if hold_time is not None else self.TIME_BUTTON_PRESS
        wait = wait_time if wait_time is not None else self.TIME_WAIT_SHORT
        
        # Press button
        self.backend._send_command(f"SET_INPUT {button}")
        time.sleep(hold)
        
        # Release button
        self.backend._send_command("SET_INPUT 0")
        
        # Wait after release
        if self.auto_wait and wait > 0:
            time.sleep(wait)
    
    def press_a(self, wait: float = None):
        """Press A button."""
        self._press_button(self.BUTTON_A, wait_time=wait)
    
    def press_b(self, wait: float = None):
        """Press B button."""
        self._press_button(self.BUTTON_B, wait_time=wait)
    
    def press_start(self, wait: float = None):
        """Press Start button."""
        self._press_button(self.BUTTON_START, wait_time=wait)
    
    def press_up(self, wait: float = None):
        """Press Up on D-pad."""
        self._press_button(self.BUTTON_UP, wait_time=wait)
    
    def press_down(self, wait: float = None):
        """Press Down on D-pad."""
        self._press_button(self.BUTTON_DOWN, wait_time=wait)
    
    def press_left(self, wait: float = None):
        """Press Left on D-pad."""
        self._press_button(self.BUTTON_LEFT, wait_time=wait)
    
    def press_right(self, wait: float = None):
        """Press Right on D-pad."""
        self._press_button(self.BUTTON_RIGHT, wait_time=wait)
    
    def wait(self, seconds: float):
        """Wait for N seconds without input."""
        time.sleep(seconds)
    
    def wait_frames(self, frames: int):
        """Wait for approximately N frames (at 60fps)."""
        time.sleep(frames / 60.0)
    
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
            val = int(response)
            if val == 1:
                return BattleOutcome.WIN
            elif val == 2:
                return BattleOutcome.LOSS
            elif val == 3:
                return BattleOutcome.DRAW
            elif val == 4:
                return BattleOutcome.RAN
            return BattleOutcome.ONGOING
        except ValueError:
            return BattleOutcome.ONGOING
    
    def _read_battle_state(self) -> BattleState:
        """Read current battle state from memory."""
        self._cached_battle_state = self.backend.read_battle_state()
        return self._cached_battle_state
    
    def _read_factory_state(self) -> FactoryState:
        """Read factory-specific state."""
        return self.backend.read_factory_state()
    
    def _read_rental_mons(self) -> List[RentalMon]:
        """Read rental Pokemon during draft."""
        return self.backend.memory.read_rental_mons()
    
    # =========================================================================
    # Observation Building
    # =========================================================================
    
    def get_observation(self) -> Dict[str, Any]:
        """
        Get observation dict for current state.
        
        Returns different observations based on current game state:
        - DRAFT_SCREEN: Rental Pokemon info
        - IN_BATTLE: Battle state, player/enemy Pokemon
        - SWAP_SCREEN: Current team + swap candidate
        
        Returns:
            Dictionary with state-appropriate observations
        """
        obs = {
            "state": self._state.name,
            "win_streak": self.win_streak,
            "current_battle": self.current_battle,
            "current_turn": self.current_turn,
        }
        
        if self._state == GameState.DRAFT_SCREEN:
            rentals = self._read_rental_mons()
            obs["rentals"] = [
                {
                    "slot": r.slot,
                    "frontier_mon_id": r.frontier_mon_id,
                    "iv_spread": r.iv_spread,
                    "ability_num": r.ability_num,
                }
                for r in rentals
            ]
            obs["rental_count"] = len(rentals)
            
        elif self._state in [GameState.IN_BATTLE, GameState.BATTLE_ANIMATING]:
            battle = self._read_battle_state()
            obs["battle"] = {
                "is_waiting": battle.is_waiting_for_input,
                "outcome": battle.battle_outcome.name,
                "turn": battle.turn_count,
            }
            if battle.active_pokemon:
                p = battle.active_pokemon
                obs["player"] = {
                    "species_id": p.species_id,
                    "hp": p.current_hp,
                    "max_hp": p.hp,
                    "level": p.level,
                }
            if battle.enemy_active_pokemon:
                e = battle.enemy_active_pokemon
                obs["enemy"] = {
                    "species_id": e.species_id,
                    "hp_percent": e.hp_percentage,
                    "level": e.level,
                }
                
        elif self._state == GameState.SWAP_SCREEN:
            # Read current team and swap candidate
            party = self.backend.memory.read_player_party()
            obs["team"] = [
                {"species_id": p.species_id, "hp": p.current_hp}
                for p in party[:3]
            ]
            # Swap candidate would need additional memory reading
            
        return obs
    
    def get_battle_observation_vector(self) -> np.ndarray:
        """
        Get flattened observation vector for battle (for neural network input).
        
        Returns:
            numpy array of battle features
        """
        battle = self._read_battle_state()
        features = []
        
        # Player Pokemon
        if battle.active_pokemon:
            p = battle.active_pokemon
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
        
        # Enemy Pokemon
        if battle.enemy_active_pokemon:
            e = battle.enemy_active_pokemon
            features.extend([
                e.species_id / 400.0,
                e.hp_percentage / 100.0,
                e.level / 100.0,
            ])
        else:
            features.extend([0.0] * 3)
        
        # Context
        features.extend([
            self.win_streak / 42.0,
            self.current_turn / 100.0,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_draft_observation_vector(self) -> np.ndarray:
        """
        Get flattened observation vector for draft (for neural network input).
        
        Returns:
            numpy array of rental Pokemon features
        """
        rentals = self._read_rental_mons()
        features = []
        
        for i in range(6):
            if i < len(rentals):
                features.extend([
                    rentals[i].frontier_mon_id / 900.0,
                    rentals[i].iv_spread / 31.0,
                    rentals[i].ability_num / 2.0,
                ])
            else:
                features.extend([0.0, 0.0, 0.0])
        
        features.extend([
            self.win_streak / 42.0,
            self.current_battle / 7.0,
        ])
        
        return np.array(features, dtype=np.float32)
    
    def get_valid_actions(self) -> np.ndarray:
        """
        Get mask of valid actions for current battle state.
        
        Returns:
            Binary mask [Move1, Move2, Move3, Move4, Switch1, Switch2]
        """
        mask = np.ones(6, dtype=np.float32)
        
        if self._cached_battle_state and self._cached_battle_state.active_pokemon:
            p = self._cached_battle_state.active_pokemon
            
            # Check move PP
            for i, move in enumerate(p.moves[:4]):
                if move is None or move.current_pp <= 0:
                    mask[i] = 0.0
            
            # Check switch availability
            party = self._cached_battle_state.party
            if len(party) < 2:
                mask[4] = 0.0
                mask[5] = 0.0
            elif len(party) < 3:
                mask[5] = 0.0
        
        self._cached_action_mask = mask
        return mask
    
    # =========================================================================
    # Initialization (Auto-Navigation)
    # =========================================================================
    
    def initialize_to_draft(self, from_title: bool = True) -> bool:
        """
        Auto-navigate from current position to the draft screen.
        
        This handles the full sequence:
        Title -> Continue -> Overworld -> Battle Factory -> Start Challenge -> Draft
        
        Args:
            from_title: If True, assumes starting from title screen
            
        Returns:
            True if successfully reached draft screen
        """
        logger.info("Initializing to draft screen...")
        
        try:
            # Import navigation sequences
            from .navigation import NavigationSequence
            nav = NavigationSequence(self)
            
            if from_title:
                # Navigate from title screen
                logger.info("  Navigating title screen...")
                nav.navigate_title_screen()
                self._state = GameState.OVERWORLD
                
                # Navigate to Battle Factory
                logger.info("  Navigating to Battle Factory...")
                nav.navigate_to_battle_factory()
                self._state = GameState.FACTORY_LOBBY
                
                # Start the challenge
                logger.info("  Starting challenge...")
                nav.start_factory_challenge()
                self._state = GameState.DRAFT_SCREEN
            
            else:
                # Assume already in factory, just need to detect state
                self._detect_current_state()
            
            logger.info("✓ Ready at draft screen")
            return self._state == GameState.DRAFT_SCREEN
            
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            self._state = GameState.ERROR
            return False
    
    def _detect_current_state(self) -> GameState:
        """
        Try to detect the current game state from memory.
        
        Returns:
            Detected GameState
        """
        # Check if in battle
        battle_mons = self.backend.memory.read_battle_mons()
        if len(battle_mons) >= 2 and battle_mons[0].species_id > 0:
            outcome = self._get_battle_outcome()
            if outcome == BattleOutcome.ONGOING:
                if self._is_waiting_for_input():
                    self._state = GameState.IN_BATTLE
                else:
                    self._state = GameState.BATTLE_ANIMATING
            else:
                self._state = GameState.BATTLE_END
            return self._state
        
        # Check for rental mons (draft screen)
        rentals = self._read_rental_mons()
        if len(rentals) > 0:
            self._state = GameState.DRAFT_SCREEN
            return self._state
        
        # Default to overworld
        self._state = GameState.OVERWORLD
        return self._state
    
    # =========================================================================
    # Phase-Level Steps
    # =========================================================================
    
    def step_draft(self, agent: DrafterAgent = None) -> PhaseResult:
        """
        Execute the draft phase - select 3 Pokemon from 6 rentals.
        
        Args:
            agent: Drafter agent callable. If None, uses random selection.
            
        Returns:
            PhaseResult with outcome
        """
        logger.info("=== DRAFT PHASE ===")
        
        if self._state != GameState.DRAFT_SCREEN:
            return PhaseResult(
                success=False,
                phase="draft",
                next_state=self._state,
                error=f"Not in draft state (current: {self._state.name})"
            )
        
        try:
            # Get observation
            obs = self.get_draft_observation_vector()
            
            # Get agent action or random
            if agent:
                selections = agent(obs, self._state)
            else:
                # Random selection
                selections = np.random.choice(6, size=3, replace=False)
            
            logger.info(f"  Selecting Pokemon: {selections}")
            
            # Execute selections
            self._execute_draft_selections(selections)
            
            # Advance to battle ready
            self._state = GameState.BATTLE_READY
            
            return PhaseResult(
                success=True,
                phase="draft",
                next_state=self._state,
                data={"selections": selections.tolist()}
            )
            
        except Exception as e:
            logger.error(f"Draft phase failed: {e}")
            return PhaseResult(
                success=False,
                phase="draft",
                next_state=GameState.ERROR,
                error=str(e)
            )
    
    def _execute_draft_selections(self, selections: np.ndarray):
        """
        Execute the draft selection inputs.
        
        For each of the 3 Pokemon indices (0-5):
        1. Press right arrow N times (N = index)
        2. Press A (select Pokemon)
        3. Press down arrow (move to confirm)
        4. Press A (confirm selection)
        5. Press left arrow N times (reset cursor position)
        
        After all 3 selections, press A 3 times to finalize team.
        
        Args:
            selections: Array of 3 indices [0-5] representing Pokemon to pick
        """
        logger.info(f"  Drafting Pokemon at indices: {selections}")
        
        for i, index in enumerate(selections):
            index = int(index)
            logger.info(f"    Picking Pokemon {i+1}/3 at index {index}")
            
            # Step 1: Press right arrow N times to reach the Pokemon
            for _ in range(index):
                self.press_right(wait=0.1)
            
            # Step 2: Press A to select the Pokemon
            self.press_a(wait=0.2)
            
            # Step 3: Press down arrow
            self.press_down(wait=0.1)
            
            # Step 4: Press A to confirm selection
            self.press_a(wait=0.3)
            
            # Step 5: Press left arrow N times to reset cursor
            for _ in range(index):
                self.press_left(wait=0.1)
        
        # Final confirmation: Press A 3 times
        logger.info("    Confirming team selection...")
        self.press_a(wait=0.3)
        self.press_a(wait=0.3)
        self.press_a(wait=0.5)
    
    def step_battle(self, agent: TacticianAgent = None) -> PhaseResult:
        """
        Execute an entire battle (multiple turns until end).
        
        Args:
            agent: Tactician agent callable. If None, uses random actions.
            
        Returns:
            PhaseResult with battle outcome
        """
        logger.info("=== BATTLE PHASE ===")
        
        # Wait for battle to start if needed
        if self._state == GameState.BATTLE_READY:
            self._wait_for_battle_start()
        
        if self._state not in [GameState.IN_BATTLE, GameState.BATTLE_ANIMATING]:
            return PhaseResult(
                success=False,
                phase="battle",
                next_state=self._state,
                error=f"Not in battle state (current: {self._state.name})"
            )
        
        try:
            self.current_turn = 0
            total_reward = 0.0
            
            # Battle loop
            while True:
                # Wait for input
                if not self._wait_for_input_or_end():
                    break  # Battle ended
                
                # Get observation and valid actions
                obs = self.get_battle_observation_vector()
                mask = self.get_valid_actions()
                
                # Get agent action
                if agent:
                    action = agent(obs, self._state, mask)
                else:
                    # Random valid action
                    valid = np.where(mask > 0)[0]
                    action = np.random.choice(valid) if len(valid) > 0 else 0
                
                # Execute turn
                result = self.step_turn(action)
                total_reward += result.reward
                
                if result.battle_ended:
                    break
            
            # Determine outcome
            outcome = self._get_battle_outcome()
            
            if outcome == BattleOutcome.WIN:
                self.battles_won += 1
                self.win_streak += 1
                self.current_battle += 1
                
                # Check if round complete or max streak
                if self.win_streak >= 42:
                    self._state = GameState.RUN_COMPLETE
                elif self.current_battle >= 7:
                    self.current_battle = 0
                    self._state = GameState.SWAP_SCREEN
                else:
                    self._state = GameState.BATTLE_READY
            else:
                self.battles_lost += 1
                self._state = GameState.RUN_COMPLETE
            
            logger.info(f"  Battle ended: {outcome.name}, streak={self.win_streak}")
            
            return PhaseResult(
                success=True,
                phase="battle",
                next_state=self._state,
                data={
                    "outcome": outcome.name,
                    "turns": self.current_turn,
                    "total_reward": total_reward,
                }
            )
            
        except Exception as e:
            logger.error(f"Battle phase failed: {e}")
            import traceback
            traceback.print_exc()
            return PhaseResult(
                success=False,
                phase="battle",
                next_state=GameState.ERROR,
                error=str(e)
            )
    
    def _wait_for_battle_start(self, timeout_seconds: float = 10.0):
        """Wait for battle to actually start."""
        logger.info("  Waiting for battle to start...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            battle_mons = self.backend.memory.read_battle_mons()
            if len(battle_mons) >= 2 and battle_mons[0].species_id > 0:
                self._state = GameState.IN_BATTLE
                return True
            
            time.sleep(0.1)  # Poll every 100ms
        
        logger.warning("  Timeout waiting for battle start")
        return False
    
    def _wait_for_input_or_end(self, timeout_seconds: float = 60.0) -> bool:
        """
        Wait until input is needed or battle ends.
        
        Returns:
            True if waiting for input, False if battle ended
        """
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_seconds:
            outcome = self._get_battle_outcome()
            if outcome != BattleOutcome.ONGOING:
                return False
            
            if self._is_waiting_for_input():
                self._state = GameState.IN_BATTLE
                return True
            
            self._state = GameState.BATTLE_ANIMATING
            time.sleep(0.1)  # Poll every 100ms
        
        logger.warning("  Timeout waiting for input")
        return False
    
    def step_turn(self, action: int) -> TurnResult:
        """
        Execute a single battle turn.
        
        Args:
            action: Action to take (0-3=Move, 4-5=Switch)
            
        Returns:
            TurnResult with outcome
        """
        if self._state != GameState.IN_BATTLE:
            return TurnResult(
                success=False,
                action_taken=action,
                reward=0.0,
                battle_ended=False,
                error=f"Not waiting for input (state: {self._state.name})"
            )
        
        try:
            # Record pre-action state
            pre_state = self._read_battle_state()
            pre_enemy_hp = pre_state.enemy_active_pokemon.hp_percentage if pre_state.enemy_active_pokemon else 0
            pre_player_hp = pre_state.active_pokemon.current_hp if pre_state.active_pokemon else 0
            
            # Execute action
            if action < 4:
                self._execute_move_action(action)
            else:
                self._execute_switch_action(action - 4)
            
            self.current_turn += 1
            self.total_turns += 1
            
            # Wait for result
            input_ready = self._wait_for_input_or_end()
            
            # Read post-action state
            post_state = self._read_battle_state()
            post_enemy_hp = post_state.enemy_active_pokemon.hp_percentage if post_state.enemy_active_pokemon else 0
            post_player_hp = post_state.active_pokemon.current_hp if post_state.active_pokemon else 0
            
            # Calculate reward
            reward = self._calculate_reward(
                pre_enemy_hp, post_enemy_hp,
                pre_player_hp, post_player_hp
            )
            
            # Check outcome
            outcome = self._get_battle_outcome()
            battle_ended = outcome != BattleOutcome.ONGOING
            
            if battle_ended:
                # Add win/loss bonus
                if outcome == BattleOutcome.WIN:
                    reward += 10.0 * (1.0 + self.win_streak * 0.1)
                elif outcome == BattleOutcome.LOSS:
                    reward -= 10.0 * (1.0 + self.win_streak * 0.2)
            
            return TurnResult(
                success=True,
                action_taken=action,
                reward=reward,
                battle_ended=battle_ended,
                outcome=outcome if battle_ended else None,
                data={
                    "turn": self.current_turn,
                    "damage_dealt": pre_enemy_hp - post_enemy_hp,
                    "damage_taken": pre_player_hp - post_player_hp,
                }
            )
            
        except Exception as e:
            logger.error(f"Turn execution failed: {e}")
            return TurnResult(
                success=False,
                action_taken=action,
                reward=0.0,
                battle_ended=False,
                error=str(e)
            )
    
    def _execute_move_action(self, move_index: int):
        """Execute a move selection (0-3)."""
        # Select Fight
        self.press_a(wait=self.TIME_WAIT_SHORT)
        
        # Navigate to move (2x2 grid)
        row = move_index // 2
        col = move_index % 2
        
        if row > 0:
            self.press_down()
        if col > 0:
            self.press_right()
        
        # Confirm move
        self.press_a(wait=self.TIME_WAIT_SHORT)
    
    def _execute_switch_action(self, pokemon_index: int):
        """Execute a switch action (0-1 = bench Pokemon 1-2)."""
        # Navigate to Pokemon menu
        self.press_right()  # From Fight to Pokemon
        self.press_a(wait=self.TIME_WAIT_SHORT)
        
        # Navigate to Pokemon (skip active at index 0)
        for _ in range(pokemon_index + 1):
            self.press_down()
        
        # Select and confirm
        self.press_a(wait=self.TIME_WAIT_SHORT)
        self.press_a(wait=self.TIME_WAIT_SHORT)
    
    def _calculate_reward(
        self,
        pre_enemy_hp: float,
        post_enemy_hp: float,
        pre_player_hp: int,
        post_player_hp: int,
    ) -> float:
        """Calculate reward for a turn."""
        reward = 0.0
        
        # Damage dealt (positive)
        damage_dealt = max(0, pre_enemy_hp - post_enemy_hp)
        reward += damage_dealt * 0.01
        
        # Damage taken (negative, but less weight)
        damage_taken = max(0, pre_player_hp - post_player_hp)
        reward -= damage_taken * 0.0005
        
        # Faint bonuses
        if pre_enemy_hp > 0 and post_enemy_hp <= 0:
            reward += 1.0  # Knocked out enemy
        if pre_player_hp > 0 and post_player_hp <= 0:
            reward -= 0.5  # Player Pokemon fainted
        
        return reward
    
    def step_swap(self, agent: DrafterAgent = None) -> PhaseResult:
        """
        Execute the swap phase - decide whether to swap a Pokemon.
        
        Args:
            agent: Drafter agent for swap decision. If None, randomly decide.
            
        Returns:
            PhaseResult with outcome
        """
        logger.info("=== SWAP PHASE ===")
        
        if self._state != GameState.SWAP_SCREEN:
            return PhaseResult(
                success=False,
                phase="swap",
                next_state=self._state,
                error=f"Not in swap state (current: {self._state.name})"
            )
        
        try:
            # Get observation (smaller than draft)
            obs = np.zeros(20, dtype=np.float32)  # Simplified
            obs[0] = self.win_streak / 42.0
            
            # Get action
            if agent:
                action = agent(obs, self._state)
                if isinstance(action, np.ndarray):
                    action = int(action[0]) if len(action) > 0 else 0
            else:
                # Random: 30% chance to swap
                action = np.random.choice([0, 1, 2, 3], p=[0.7, 0.1, 0.1, 0.1])
            
            logger.info(f"  Swap decision: {action} (0=keep)")
            
            # Execute swap
            if action == 0:
                # Decline swap
                self.press_b(wait=self.TIME_WAIT_LONG)
            else:
                # Accept swap for slot N
                for _ in range(action - 1):
                    self.press_down()
                self.press_a(wait=self.TIME_WAIT_MEDIUM)
                self.press_a(wait=self.TIME_WAIT_LONG)
            
            self._state = GameState.BATTLE_READY
            
            return PhaseResult(
                success=True,
                phase="swap",
                next_state=self._state,
                data={"action": int(action), "swapped": action > 0}
            )
            
        except Exception as e:
            logger.error(f"Swap phase failed: {e}")
            return PhaseResult(
                success=False,
                phase="swap",
                next_state=GameState.ERROR,
                error=str(e)
            )
    
    # =========================================================================
    # Full Episode
    # =========================================================================
    
    def run_episode(
        self,
        drafter: DrafterAgent = None,
        tactician: TacticianAgent = None,
    ) -> EpisodeResult:
        """
        Run a complete Battle Factory episode.
        
        Args:
            drafter: Agent for draft and swap decisions
            tactician: Agent for battle decisions
            
        Returns:
            EpisodeResult with full statistics
        """
        logger.info("\n" + "="*60)
        logger.info("STARTING EPISODE")
        logger.info("="*60)
        
        start_time = time.time()
        phases = []
        
        try:
            # Reset stats
            self._reset_run_stats()
            
            # Draft phase
            result = self.step_draft(drafter)
            phases.append("draft")
            if not result.success:
                raise Exception(f"Draft failed: {result.error}")
            
            # Battle loop
            while not self.is_run_complete():
                # Battle
                result = self.step_battle(tactician)
                phases.append(f"battle_{self.battles_won + self.battles_lost}")
                
                if not result.success:
                    raise Exception(f"Battle failed: {result.error}")
                
                # Swap if applicable
                if self._state == GameState.SWAP_SCREEN:
                    result = self.step_swap(drafter)
                    phases.append("swap")
                    if not result.success:
                        raise Exception(f"Swap failed: {result.error}")
            
            duration = time.time() - start_time
            
            logger.info(f"\n{'='*60}")
            logger.info(f"EPISODE COMPLETE - Streak: {self.win_streak}")
            logger.info(f"{'='*60}")
            
            return EpisodeResult(
                success=True,
                win_streak=self.win_streak,
                battles_won=self.battles_won,
                battles_lost=self.battles_lost,
                total_turns=self.total_turns,
                duration_seconds=duration,
                phases_completed=phases,
            )
            
        except Exception as e:
            logger.error(f"Episode failed: {e}")
            import traceback
            traceback.print_exc()
            
            return EpisodeResult(
                success=False,
                win_streak=self.win_streak,
                battles_won=self.battles_won,
                battles_lost=self.battles_lost,
                total_turns=self.total_turns,
                duration_seconds=time.time() - start_time,
                phases_completed=phases,
                error=str(e),
            )
    
    def _reset_run_stats(self):
        """Reset statistics for a new run."""
        self.win_streak = 0
        self.current_battle = 0
        self.current_turn = 0
        self.total_turns = 0
        self.battles_won = 0
        self.battles_lost = 0
        self.tactician_hidden_state = None
        self._cached_battle_state = None
        self._cached_action_mask = None

