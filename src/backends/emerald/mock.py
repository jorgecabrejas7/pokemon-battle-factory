from typing import Optional, List
import time
import random
from ...core.protocols import BattleBackend
from ...core.dataclasses import BattleState, FactoryState, PlayerPokemon, EnemyPokemon, Move, RentalPokemon
from ...core.enums import StatusCondition, Weather, Terrain, MoveCategory

class MockEmeraldBackend(BattleBackend):
    """
    A Mock Backend for Pokemon Emerald that simulates basic battle flow.
    Used for testing Agent logic when the actual Emulator/ROM is not available.
    """
    
    def __init__(self, rom_path: str = "mock.gba"):
        self.rom_path = rom_path
        self.connected = False
        self.turn_count = 0
        self.state = BattleState()
        self.factory_state = FactoryState()
        
    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        print(f"[MockBackend] Connecting to {rom_path}...")
        self.connected = True
        self.reset()
        print("[MockBackend] Connected.")

    def reset(self) -> None:
        """Sets up a fresh dummy state."""
        self.turn_count = 0
        
        # Create Dummy Player Mon (Swampert)
        p_mon = PlayerPokemon(
            species_id=260, # Swampert
            level=50,
            nickname="Swampert",
            gender_id=1,
            hp=175, attack=130, defense=110, sp_attack=105, sp_defense=110, speed=80,
            current_hp=175,
            moves=[
                Move(move_id=57, name="Surf", type_id=11, category=MoveCategory.SPECIAL, base_power=95, accuracy=100, current_pp=15, max_pp=15),
                Move(move_id=89, name="Earthquake", type_id=4, category=MoveCategory.PHYSICAL, base_power=100, accuracy=100, current_pp=10, max_pp=10),
                Move(move_id=58, name="Ice Beam", type_id=15, category=MoveCategory.SPECIAL, base_power=95, accuracy=100, current_pp=10, max_pp=10),
                Move(move_id=182, name="Protect", type_id=0, category=MoveCategory.STATUS, base_power=0, accuracy=0, current_pp=10, max_pp=10),
            ]
        )
        
        # Create Dummy Enemy Mon (Sceptile)
        e_mon = EnemyPokemon(
            species_id=254, # Sceptile
            level=50,
            nickname="Sceptile",
            gender_id=1,
        )
        
        self.state = BattleState(
            active_pokemon=p_mon,
            party=[p_mon],
            enemy_active_pokemon=e_mon,
            enemy_party=[e_mon],
            weather=Weather.NONE,
            terrain=Terrain.NONE,
            turn_count=0,
            is_waiting_for_input=True,
            available_actions=[1, 2, 3, 4] # Move slots 1-4
        )
        
        # Factory State
        self.factory_state = FactoryState(
            current_round=1,
            current_battle=1,
            win_streak=0,
            rental_pool=[
                RentalPokemon(species_id=1, nickname="Bulbasaur", level=50),
                RentalPokemon(species_id=4, nickname="Charmander", level=50),
                RentalPokemon(species_id=7, nickname="Squirtle", level=50),
            ],
            current_team=[]
        )

    def read_battle_state(self) -> BattleState:
        return self.state

    def read_factory_state(self) -> FactoryState:
        return self.factory_state

    def inject_action(self, action_id: int) -> None:
        print(f"[MockBackend] Action Injected: {action_id}")
        self.state.is_waiting_for_input = False
        # Simulate 'Processing' state

    def advance_frame(self, frames: int = 1) -> None:
        # In a real emulator, this steps the clock.
        # In mock, if we are not waiting for input, we advance logic.
        if not self.state.is_waiting_for_input:
            # Simulate a turn passing
            time.sleep(0.1) 
            self.turn_count += 1
            self.state.turn_count = self.turn_count
            
            # Simple logic: Enemy takes damage, Player takes damage
            if self.state.enemy_active_pokemon:
                self.state.enemy_active_pokemon.hp_percentage = max(0.0, self.state.enemy_active_pokemon.hp_percentage - 25.0)
            
            if self.state.active_pokemon:
                self.state.active_pokemon.current_hp = max(0, self.state.active_pokemon.current_hp - 20)

            # Check if battle over (mock)
            if self.state.active_pokemon and self.state.active_pokemon.current_hp == 0:
                print("[MockBackend] Player Fainted! Resetting...")
                self.reset()
            elif self.state.enemy_active_pokemon and self.state.enemy_active_pokemon.hp_percentage == 0:
                print("[MockBackend] Enemy Fainted! Next Battle...")
                self.reset() # Just reset for infinite loop for now
            else:
                self.state.is_waiting_for_input = True # Ready for next turn

    def save_state(self) -> bytes:
        return b"MOCK_STATE"

    def load_state(self, state: bytes) -> None:
        print("[MockBackend] Loaded State")

    def run_until_input_required(self) -> BattleState:
        print("[MockBackend] Fast-forwarding...")
        while not self.state.is_waiting_for_input:
            self.advance_frame()
        return self.state

    def get_game_version(self) -> str:
        return "emerald"
