from dataclasses import dataclass, field
from typing import List, Optional
from .enums import MoveCategory, StatusCondition, Weather, Terrain, ScreenType, BattleOutcome

@dataclass
class Move:
    move_id: int
    name: str = ""
    type_id: int = 0
    category: MoveCategory = MoveCategory.PHYSICAL
    base_power: int = 0
    accuracy: int = 0
    priority: int = 0
    current_pp: int = 0
    max_pp: int = 0
    effect_id: int = 0
    effect_chance: int = 0
    target_type: int = 0

@dataclass
class BasePokemon:
    species_id: int
    level: int = 100
    nickname: str = ""
    gender_id: int = 0  # 0=Genderless, 1=Male, 2=Female

@dataclass
class RentalPokemon(BasePokemon):
    ability_id: int = 0
    item_id: int = 0
    nature_id: int = 0
    
    # Concrete Stats - fully known
    hp: int = 0
    attack: int = 0
    defense: int = 0
    sp_attack: int = 0
    sp_defense: int = 0
    speed: int = 0
    
    # Known Moves
    moves: List[Move] = field(default_factory=list)

@dataclass
class PlayerPokemon(RentalPokemon):
    # Dynamic Battle State
    current_hp: int = 0
    status_condition: StatusCondition = StatusCondition.NONE
    is_confused: bool = False
    stat_stages: List[int] = field(default_factory=lambda: [0]*6)
    volatile_status: int = 0

@dataclass
class EnemyPokemon(BasePokemon):
    # Partial Info / Estimates
    hp_percentage: float = 100.0
    predicted_item_id: Optional[int] = None
    predicted_ability_id: Optional[int] = None
    predicted_nature_id: Optional[int] = None
    
    # Assessment
    turn_count_active: int = 0
    revealed_moves: List[Move] = field(default_factory=list)

@dataclass
class DisableStruct:
    disable_timer: int = 0
    disable_move: int = 0
    encored_move: int = 0
    encore_timer: int = 0
    taunt_timer: int = 0

@dataclass
class SideTimer:
    reflect_timer: int = 0
    lightscreen_timer: int = 0
    mist_timer: int = 0
    safeguard_timer: int = 0

@dataclass
class BattleState:
    # Player Side
    active_pokemon: Optional[PlayerPokemon] = None
    party: List[PlayerPokemon] = field(default_factory=list)
    player_side_conditions: int = 0 
    player_disable_struct: Optional[DisableStruct] = None
    player_side_timer: Optional[SideTimer] = None

    # Enemy Side
    enemy_active_pokemon: Optional[EnemyPokemon] = None
    enemy_party: List[EnemyPokemon] = field(default_factory=list)
    enemy_side_conditions: int = 0 
    enemy_disable_struct: Optional[DisableStruct] = None
    enemy_side_timer: Optional[SideTimer] = None

    # Field
    weather: Weather = Weather.NONE
    terrain: Terrain = Terrain.NONE
    turn_count: int = 0
    battle_type_flags: int = 0

    # Flags & Cursors
    is_waiting_for_input: bool = False
    battler_in_menu_id: int = 0
    action_cursor: int = 0
    move_cursor: int = 0
    move_result_flags: int = 0
    
    available_actions: List[int] = field(default_factory=list)
    
    # Last Action Info
    last_move_used: int = 0
    last_move_user: int = -1
    battle_outcome: BattleOutcome = BattleOutcome.ONGOING

@dataclass
class FactoryState:
    # Context
    current_round: int = 0
    current_battle: int = 0
    win_streak: int = 0

    # Draft Info
    rental_pool: List[RentalPokemon] = field(default_factory=list)
    current_team: List[RentalPokemon] = field(default_factory=list)

    # Hints
    scientist_hint_id: int = 0
    hint_payload: Optional[dict] = None

    # Screen
    screen_type: ScreenType = ScreenType.Other
