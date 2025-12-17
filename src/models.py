from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class PartyPokemon:
    pid: int
    species_id: int
    species_name: str
    moves: List[str]
    pp: List[int]
    hp: int
    max_hp: int
    level: int
    nickname: str
    status: int
    item_name: str
    
    @property
    def is_fainted(self) -> bool:
        return self.hp == 0

@dataclass
class BattlePokemon:
    slot: int
    species_id: int
    species_name: str
    hp: int
    max_hp: int
    level: int
    status: int
    moves: List[str]
    pp: List[int]
    
    @property
    def pct_hp(self) -> float:
        return self.hp / self.max_hp if self.max_hp > 0 else 0.0

@dataclass
class RentalPokemon:
    slot: int
    species_id: int
    species_name: str
    ivs: int
    ability_num: int
    personality: int
    
    def __str__(self):
        return f"{self.species_name} (IVs: {self.ivs})"

@dataclass
class BattleFactorySnapshot:
    """Unified snapshot of the game state at a specific point in time."""
    timestamp: float
    phase: str  # "BATTLE", "RENTAL", "MENU", "IDLE"
    outcome: int
    input_wait: bool
    rng_seed: int
    
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
