"""
Enumerations for Battle Factory RL System.

This module provides all enum types used throughout the codebase,
ensuring consistent state representation and type safety.
"""

from __future__ import annotations

from enum import Enum, IntEnum, auto


# =============================================================================
# Battle Enums
# =============================================================================

class MoveCategory(IntEnum):
    """Pokemon move damage category."""
    PHYSICAL = 0
    SPECIAL = 1
    STATUS = 2


class StatusCondition(IntEnum):
    """Primary status conditions (mutually exclusive)."""
    NONE = 0
    SLEEP = 1
    POISON = 2
    BURN = 3
    FREEZE = 4
    PARALYSIS = 5
    BAD_POISON = 6  # Toxic


class VolatileStatus(IntEnum):
    """Volatile status conditions (can stack)."""
    NONE = 0
    CONFUSION = 1 << 0
    FLINCH = 1 << 1
    CHARGING = 1 << 2  # Solar Beam, etc.
    TRAPPED = 1 << 3   # Mean Look, etc.
    LEECH_SEED = 1 << 4
    CURSE = 1 << 5


class Weather(IntEnum):
    """Battle weather conditions."""
    NONE = 0
    RAIN = 1
    SUN = 2
    SANDSTORM = 3
    HAIL = 4


class Terrain(IntEnum):
    """Battle terrain types (Gen 7+, included for future compatibility)."""
    NONE = 0
    ELECTRIC = 1
    GRASSY = 2
    MISTY = 3
    PSYCHIC = 4


class BattleOutcome(IntEnum):
    """Battle result states."""
    ONGOING = 0
    WIN = 1
    LOSS = 2
    DRAW = 3
    RAN = 4  # Fled from battle


# =============================================================================
# Game Phase / State Enums
# =============================================================================

class GamePhase(Enum):
    """
    Unified game phase enum for Battle Factory.
    
    This replaces the separate GamePhase (system.py) and GameState 
    (game_controller.py) enums with a single source of truth.
    
    State Machine:
        UNINITIALIZED -> TITLE_SCREEN -> OVERWORLD -> FACTORY_LOBBY ->
        CHALLENGE_SETUP -> DRAFT_SCREEN -> BATTLE_READY -> IN_BATTLE ->
        BATTLE_ANIMATING -> BATTLE_END -> (SWAP_SCREEN -> BATTLE_READY) or RUN_COMPLETE
    """
    # Connection states
    UNINITIALIZED = auto()     # Not connected to emulator
    ERROR = auto()             # Error state
    
    # Navigation states
    TITLE_SCREEN = auto()      # At game title/intro screens
    OVERWORLD = auto()         # Walking around in game world
    FACTORY_LOBBY = auto()     # Inside Battle Factory building
    CHALLENGE_SETUP = auto()   # Selecting challenge options
    
    # Draft phase
    DRAFT_SCREEN = auto()      # Selecting 3 Pokemon from 6 rentals
    
    # Battle phases
    BATTLE_READY = auto()      # About to start a battle
    PRE_BATTLE = auto()        # Navigating menus before battle
    IN_BATTLE = auto()         # Mid-battle, waiting for player input
    BATTLE_ANIMATING = auto()  # Battle animation playing
    BATTLE_END = auto()        # Battle just ended
    POST_BATTLE = auto()       # Processing battle outcome
    
    # Post-battle phases
    SWAP_SCREEN = auto()       # Can swap Pokemon with opponent's
    
    # Run completion
    RUN_COMPLETE = auto()      # Run finished (streak complete or lost)
    
    @property
    def is_battle_phase(self) -> bool:
        """Check if in any battle-related phase."""
        return self in (
            GamePhase.BATTLE_READY,
            GamePhase.PRE_BATTLE,
            GamePhase.IN_BATTLE,
            GamePhase.BATTLE_ANIMATING,
            GamePhase.BATTLE_END,
            GamePhase.POST_BATTLE,
        )
    
    @property
    def is_draft_phase(self) -> bool:
        """Check if in draft or swap phase."""
        return self in (GamePhase.DRAFT_SCREEN, GamePhase.SWAP_SCREEN)
    
    @property
    def requires_input(self) -> bool:
        """Check if phase requires agent input."""
        return self in (
            GamePhase.DRAFT_SCREEN,
            GamePhase.IN_BATTLE,
            GamePhase.SWAP_SCREEN,
        )
    
    @property
    def is_terminal(self) -> bool:
        """Check if phase is terminal (run ended)."""
        return self in (GamePhase.RUN_COMPLETE, GamePhase.ERROR)


# Backwards compatibility aliases
class ScreenType(Enum):
    """Screen type enum (legacy, use GamePhase instead)."""
    Other = auto()
    DRAFT = auto()
    SWAP = auto()
    BATTLE = auto()
    RESULT = auto()


# =============================================================================
# Battle Factory Specific Enums
# =============================================================================

class FacilityType(IntEnum):
    """Battle Frontier facility types."""
    TOWER = 0
    DOME = 1
    PALACE = 2
    ARENA = 3
    FACTORY = 4
    PIKE = 5
    PYRAMID = 6


class BattleMode(IntEnum):
    """Battle mode (singles vs doubles)."""
    SINGLES = 0
    DOUBLES = 1


class LevelMode(IntEnum):
    """Level mode for Battle Frontier."""
    LEVEL_50 = 0
    OPEN_LEVEL = 1


# =============================================================================
# Type Enums
# =============================================================================

class PokemonType(IntEnum):
    """Pokemon types (Gen 3)."""
    NORMAL = 0
    FIGHTING = 1
    FLYING = 2
    POISON = 3
    GROUND = 4
    ROCK = 5
    BUG = 6
    GHOST = 7
    STEEL = 8
    FIRE = 9
    WATER = 10
    GRASS = 11
    ELECTRIC = 12
    PSYCHIC = 13
    ICE = 14
    DRAGON = 15
    DARK = 16
    # Note: Fairy added in Gen 6
    
    @classmethod
    def from_name(cls, name: str) -> PokemonType:
        """Get type from name string."""
        return cls[name.upper()]


# =============================================================================
# Action Space Enums
# =============================================================================

class BattleAction(IntEnum):
    """Battle action indices."""
    MOVE_1 = 0
    MOVE_2 = 1
    MOVE_3 = 2
    MOVE_4 = 3
    SWITCH_1 = 4
    SWITCH_2 = 5
    
    @property
    def is_move(self) -> bool:
        return self.value < 4
    
    @property
    def is_switch(self) -> bool:
        return self.value >= 4
    
    @property
    def move_index(self) -> int:
        """Get move index (0-3) if this is a move action."""
        return self.value if self.value < 4 else -1
    
    @property
    def switch_index(self) -> int:
        """Get switch index (0-1) if this is a switch action."""
        return self.value - 4 if self.value >= 4 else -1


class SwapAction(IntEnum):
    """Swap decision indices."""
    KEEP = 0      # Don't swap
    SWAP_1 = 1    # Swap slot 1
    SWAP_2 = 2    # Swap slot 2
    SWAP_3 = 3    # Swap slot 3
    
    @property
    def should_swap(self) -> bool:
        return self.value > 0
    
    @property
    def swap_slot(self) -> int:
        """Get slot to swap (0-2), or -1 if keeping."""
        return self.value - 1 if self.value > 0 else -1
