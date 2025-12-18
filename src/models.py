from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class Move:
    """Represents a Pokémon move with its battle properties.

    Attributes:
        id (int): The unique internal ID of the move.
        name (str): The display name of the move.
        type (str): The elemental type of the move (e.g., "Fire", "Water").
        power (int): The base power of the move.
        accuracy (int): The accuracy percentage (0-100).
        pp (int): The base Power Points.
        effect (str): A description of the move's secondary effect.
        target (str): The targeting scope (e.g., "Selected Target", "All Opponents").
        priority (int): The move's priority bracket.
        flags (List[str]): detailed flags (e.g. "Contact", "Protect").
        split (str): The damage category ("Physical", "Special", or "Status").
    """
    id: int
    name: str 
    type: str
    power: int
    accuracy: int
    pp: int
    effect: str
    target: str
    priority: int
    flags: List[str]
    split: str
    
    def __str__(self) -> str:
        return f"{self.name} ({self.type}/{self.split}) Pwr:{self.power} Acc:{self.accuracy}"

@dataclass
class SpeciesInfo:
    """Static data for a Pokémon species.

    Attributes:
        id (int): The unique national DEX or internal ID.
        name (str): The species name (e.g., "Bulbasaur").
        type1 (str): The primary type.
        type2 (str): The secondary type (or "None").
        base_stats (Dict[str, int]): Dictionary of base stats (hp, atk, def, spa, spd, spe).
        abilities (List[str]): List of possible ability names.
    """
    id: int
    name: str
    type1: str
    type2: str
    base_stats: Dict[str, int] # hp, atk, def, spa, spd, spe
    abilities: List[str]

@dataclass
class ItemInfo:
    """Represents a held item.

    Attributes:
        id (int): The unique internal ID of the item.
        name (str): The display name of the item.
        description (str): In-game description.
        hold_effect (str): The effect ID or name when held.
        hold_effect_param (int): Parameter for the hold effect (e.g., boost amount).
    """
    id: int
    name: str
    description: str
    hold_effect: str
    hold_effect_param: int


NATURES = [
    "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
    "Bold", "Docile", "Relaxed", "Impish", "Lax",
    "Timid", "Hasty", "Serious", "Jolly", "Naive",
    "Modest", "Mild", "Quiet", "Bashful", "Rash",
    "Calm", "Gentle", "Sassy", "Careful", "Quirky"
]

def get_nature(pid: int) -> str:
    """Determines the nature based on the Personality Value (PID).

    Args:
        pid (int): The 32-bit personality value of the Pokémon.

    Returns:
        str: The name of the nature.
    """
    return NATURES[pid % 25]

@dataclass
class PartyPokemon:
    """Represents a Pokémon in the player's full party (snapshot from memory).

    Attributes:
        pid (int): Personality Value.
        species_id (int): Internal species ID.
        species_name (str): Display name of the species.
        moves (List[Move]): List of known moves (up to 4).
        pp (List[int]): Current PP for each move.
        hp (int): Current HP.
        max_hp (int): Maximum HP.
        level (int): Current level.
        nickname (str): The Pokémon's nickname.
        status (int): Status condition bitmask.
        item (ItemInfo): Held item data.
        real_stats (Dict[str, int]): Actual stats (Atk, Def, etc.) calculated by the game.
        species_info (Optional[SpeciesInfo]): Static species data enriched from DB.
    """
    pid: int
    species_id: int
    species_name: str
    moves: List[Move]
    pp: List[int]
    hp: int
    max_hp: int
    level: int
    nickname: str
    status: int
    item: ItemInfo
    
    # Extended Data
    ivs: Dict[str, int] = field(default_factory=dict)
    evs: Dict[str, int] = field(default_factory=dict)
    friendship: int = 0
    exp: int = 0
    pp_bonuses: int = 0
    pokerus: int = 0
    met_location: int = 0
    is_egg: bool = False
    ability_num: int = 0
    
    # Enrichments
    real_stats: Dict[str, int] = field(default_factory=dict)
    species_info: Optional[SpeciesInfo] = None
    
    @property
    def is_fainted(self) -> bool:
        """Checks if the Pokémon has 0 HP."""
        return self.hp == 0
        
    @property
    def nature(self) -> str:
        """Calculates the nature from the PID."""
        return get_nature(self.pid)

@dataclass
class BattlePokemon:
    """Represents an active battler on the field.

    This struct corresponds to the data found in the `gBattleMons` array in memory.

    Attributes:
        slot (int): The battle slot index (0-3).
        species_id (int): Internal species ID.
        species_name (str): Display name.
        hp (int): Current HP.
        max_hp (int): Total HP.
        level (int): Current level.
        status (int): Status condition bitmask.
        moves (List[Move]): Moves currently available in battle.
        pp (List[int]): Current PP of the moves.
        real_stats (Dict[str, int]): Effective stats in battle (unboosted by stages).
        species_info (Optional[SpeciesInfo]): Enriched static species data.
        pid (int): Personality Value (if available/decodable).
    """
    slot: int
    species_id: int
    species_name: str
    hp: int
    max_hp: int
    level: int
    status: int
    moves: List[Move]
    pp: List[int]
    
    # Enrichments
    real_stats: Dict[str, int] = field(default_factory=dict)
    species_info: Optional[SpeciesInfo] = None
    
    # Extended Battle Data
    type1: str = "Normal"
    type2: str = "None"
    ability_id: int = 0
    item_id: int = 0 # Active item (might be different from party item due to Knock Off)
    status2: int = 0 # Volatile status (Confusion, Infatuation, etc.)
    pp_bonuses: int = 0
    
    pid: int = 0
    
    @property
    def pct_hp(self) -> float:
        """Returns the percentage of HP remaining (0.0 to 1.0)."""
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

    @property
    def nature(self) -> str:
        """Calculates nature from PID if available, else 'Unknown'."""
        return get_nature(self.pid) if self.pid else "Unknown"

@dataclass
class RentalPokemon:
    """Represents a rental or swap candidate in the Battle Factory.

    Attributes:
        slot (int): Index in the rental array.
        species_id (int): Internal species ID.
        species_name (str): Name of the species.
        ivs (int): Individual Value (fixed for all stats in Factory).
        ability_num (int): Which ability slot (0 or 1) is used.
        personality (int): PID of the rental mon.
        species_info (Optional[SpeciesInfo]): Static species data.
        moves (List[Move]): The moveset of the rental mon.
        item (Optional[ItemInfo]): The held item.
    """
    slot: int
    species_id: int
    species_name: str
    ivs: int
    ability_num: int
    personality: int
    
    # Enrichments
    species_info: Optional[SpeciesInfo] = None
    moves: List[Move] = field(default_factory=list)
    item: Optional[ItemInfo] = None
    
    @property
    def nature(self) -> str:
        """Calculates nature from personality."""
        return get_nature(self.personality)

    def __str__(self) -> str:
        return f"{self.species_name} (IVs: {self.ivs})"

@dataclass
class BattleFactorySnapshot:
    """Unified snapshot of the game state at a specific point in time.

    This object serves as the single source of truth for the environment state,
    containing all data read from memory and enriched from the database.

    Attributes:
        timestamp (float): Time when the snapshot was taken.
        phase (str): Current game phase ("BATTLE", "RENTAL", "MENU", "IDLE").
        outcome (int): Battle outcome flag (0=Ongoing, 1=Win, etc.).
        input_wait (bool): True if the game is waiting for user input.
        rng_seed (int): Current RNG seed value.
        last_move_player (str): Name of the last move used by the player.
        last_move_enemy (str): Name of the last move used by the enemy.
        player_party (List[PartyPokemon]): The player's current party.
        enemy_party (List[PartyPokemon]): The enemy's party (revealed so far).
        active_battlers (List[BattlePokemon]): Pokémon currently in the active battle slots.
        rental_candidates (List[RentalPokemon]): Available Pokémon for rental/swap.
        frame_count (int): (Optional) Frame counter from emulator.
    """
    timestamp: float
    phase: str  # "BATTLE", "RENTAL", "MENU", "IDLE"
    outcome: int
    input_wait: bool
    rng_seed: int
    weather: str
    
    # Context
    last_move_player: str
    last_move_enemy: str
    
    # Data
    player_party: List[PartyPokemon]
    enemy_party: List[PartyPokemon]
    active_battlers: List[BattlePokemon]
    rental_candidates: List[RentalPokemon]
    
    # Metadata
    frame_count: int = 0  # Could be useful if we track frames

