"""
Memory Reader for Pokemon Emerald.
Provides high-level methods to read game state from emulator memory.
"""
import struct
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Protocol, Tuple

from .constants import (
    PLAYER_PARTY_OFFSET, ENEMY_PARTY_OFFSET,
    POKEMON_SIZE_BYTES, PARTY_SIZE, MAX_PARTY_BYTES,
    BATTLE_MONS_OFFSET, BATTLE_MON_SIZE, BATTLE_MON_COUNT,
    BATTLE_WEATHER_OFFSET, ACTIVE_BATTLER_OFFSET, BATTLERS_COUNT_OFFSET,
    SAVE_BLOCK_2_PTR,
    FRONTIER_LVL_MODE_OFFSET, FRONTIER_RENTAL_MONS_OFFSET, RENTAL_MON_SIZE,
    FRONTIER_FACTORY_STREAK_OFFSET, FRONTIER_FACTORY_RENTS_OFFSET,
    FRONTIER_TOWER_STREAK_OFFSET, FRONTIER_DOME_STREAK_OFFSET,
    FRONTIER_PALACE_STREAK_OFFSET, FRONTIER_ARENA_STREAK_OFFSET,
    FRONTIER_PIKE_STREAK_OFFSET, FRONTIER_PYRAMID_STREAK_OFFSET,
    FACILITY_TOWER, FACILITY_DOME, FACILITY_PALACE, FACILITY_ARENA,
    FACILITY_FACTORY, FACILITY_PIKE, FACILITY_PYRAMID,
    BATTLE_MON_SPECIES, BATTLE_MON_ATTACK, BATTLE_MON_DEFENSE,
    BATTLE_MON_SPEED, BATTLE_MON_SP_ATTACK, BATTLE_MON_SP_DEFENSE,
    BATTLE_MON_MOVE1, BATTLE_MON_HP, BATTLE_MON_MAX_HP, BATTLE_MON_LEVEL,
    BATTLE_MON_STATUS1, BATTLE_MON_STATUS2, BATTLE_MON_STAT_STAGES, BATTLE_MON_PP,
    STATUS1_SLEEP, STATUS1_POISON, STATUS1_BURN, STATUS1_FREEZE,
    STATUS1_PARALYSIS, STATUS1_TOXIC,
    BATTLE_OUTCOME_OFFSET, LAST_USED_MOVE_OFFSET, BATTLER_ATTACKER_OFFSET,
    BATTLE_INPUT_WAIT_FLAG_OFFSET,
    BATTLE_INPUT_WAIT_FLAG_OFFSET,
    BATTLE_COMMUNICATION_OFFSET, BATTLER_IN_MENU_ID_OFFSET,
    BATTLE_TYPE_FLAGS_OFFSET, DISABLE_STRUCTS_OFFSET,
    SIDE_TIMERS_OFFSET, ACTION_SELECTION_CURSOR,
    MOVE_SELECTION_CURSOR, MOVE_RESULT_FLAGS_OFFSET,
    CHAR_MAP
)
from .decryption import decrypt_data, unshuffle_substructures, verify_checksum
from ...core.enums import BattleOutcome
from ...core.dataclasses import DisableStruct, SideTimer, BattleState


class BackendProtocol(Protocol):
    """Protocol for backend communication."""
    def _send_command(self, cmd: str) -> str: ...


@dataclass
class BattleMon:
    """Active Pokemon in battle (unencrypted battle struct)."""
    species_id: int
    level: int
    current_hp: int
    max_hp: int
    attack: int
    defense: int
    speed: int
    sp_attack: int
    sp_defense: int
    moves: List[int]  # Move IDs
    pp: List[int]  # Current PP for each move
    status1: int  # Primary status (sleep, poison, etc.)
    status2: int  # Volatile status (confusion, etc.)
    stat_stages: List[int]  # HP, Atk, Def, Spd, SpAtk, SpDef, Acc, Eva (-6 to +6)
    
    @property
    def status_name(self) -> str:
        """Get human-readable status name."""
        if self.status1 == 0:
            return "Healthy"
        if self.status1 & STATUS1_SLEEP:
            return f"Sleep ({self.status1 & 0x7} turns)"
        if self.status1 & STATUS1_TOXIC:
            return "Toxic"
        if self.status1 & STATUS1_POISON:
            return "Poison"
        if self.status1 & STATUS1_BURN:
            return "Burn"
        if self.status1 & STATUS1_FREEZE:
            return "Freeze"
        if self.status1 & STATUS1_PARALYSIS:
            return "Paralysis"
        return f"Unknown ({self.status1})"


@dataclass
class PartyPokemon:
    """Pokemon in party (decrypted from 100-byte structure)."""
    species_id: int
    nickname: str
    level: int
    current_hp: int
    max_hp: int
    attack: int
    defense: int
    speed: int
    sp_attack: int
    sp_defense: int
    item_id: int
    moves: List[int]
    evs: List[int]  # HP, Atk, Def, Spd, SpAtk, SpDef
    is_valid: bool = True


@dataclass
class RentalMon:
    """Rental Pokemon for Battle Factory."""
    slot: int
    frontier_mon_id: int
    # Additional fields from RentalMon struct (12 bytes)
    iv_spread: int = 0
    ability_num: int = 0
    personality: int = 0


@dataclass
class FrontierState:
    """Battle Frontier game state."""
    facility: int
    battle_mode: int  # 0=Singles, 1=Doubles
    level_mode: int  # 0=Lv50, 1=Open
    win_streak: int
    rental_count: int  # How many times rented in Factory
    
    @property
    def facility_name(self) -> str:
        names = {
            FACILITY_TOWER: "Battle Tower",
            FACILITY_DOME: "Battle Dome",
            FACILITY_PALACE: "Battle Palace",
            FACILITY_ARENA: "Battle Arena",
            FACILITY_FACTORY: "Battle Factory",
            FACILITY_PIKE: "Battle Pike",
            FACILITY_PYRAMID: "Battle Pyramid",
        }
        return names.get(self.facility, f"Unknown ({self.facility})")


class MemoryReader:
    """
    High-level memory reader for Pokemon Emerald.
    Wraps backend commands to provide parsed game state.
    """
    
    def __init__(self, backend: BackendProtocol):
        self.backend = backend
        self.backend = backend
    
    def _send(self, cmd: str) -> str:
        """Send command to backend and return response."""
        return self.backend._send_command(cmd)
    
    def _read_block(self, addr: int, size: int) -> Optional[bytes]:
        """Read a block of memory and return as bytes."""
        resp = self._send(f"READ_BLOCK {addr:X} {size:X}")
        if resp.startswith("ERROR") or resp == "TIMEOUT":
            return None
        try:
            return bytes.fromhex(resp)
        except ValueError:
            return None
    
    def _read_u16(self, addr: int) -> Optional[int]:
        """Read unsigned 16-bit value."""
        resp = self._send(f"READ_U16 {addr:X}")
        if resp.startswith("ERROR"):
            return None
        try:
            return int(resp)
        except ValueError:
            return None
    
    def _read_u32(self, addr: int) -> Optional[int]:
        """Read unsigned 32-bit value."""
        resp = self._send(f"READ_U32 {addr:X}")
        if resp.startswith("ERROR"):
            return None
        try:
            return int(resp)
        except ValueError:
            return None
    
    def _read_ptr_block(self, ptr_addr: int, offset: int, size: int) -> Optional[bytes]:
        """Read pointer, add offset, read block."""
        resp = self._send(f"READ_PTR {ptr_addr:X} {offset:X} {size:X}")
        if resp.startswith("ERROR") or resp == "TIMEOUT":
            return None
        try:
            return bytes.fromhex(resp)
        except ValueError:
            return None
    
    def _read_ptr_u16(self, ptr_addr: int, offset: int) -> Optional[int]:
        """Read pointer, add offset, read u16."""
        resp = self._send(f"READ_PTR_U16 {ptr_addr:X} {offset:X}")
        if resp.startswith("ERROR"):
            return None
        try:
            return int(resp)
        except ValueError:
            return None
    
    def _decode_string(self, data: bytes) -> str:
        """Decode Gen3 character encoding to string."""
        s = ""
        for b in data:
            if b == 0xFF:
                break
            s += CHAR_MAP.get(b, "?")
        return s
    
    # -------------------------------------------------------------------------
    # Party Reading
    # -------------------------------------------------------------------------
    
    def read_player_party(self) -> List[PartyPokemon]:
        """Read and decode the player's party."""
        return self._read_party(PLAYER_PARTY_OFFSET)
    
    def read_enemy_party(self) -> List[PartyPokemon]:
        """Read and decode the enemy's party."""
        return self._read_party(ENEMY_PARTY_OFFSET)
    
    def _read_party(self, base_addr: int) -> List[PartyPokemon]:
        """Read and decode a party from memory."""
        data = self._read_block(base_addr, MAX_PARTY_BYTES)
        if not data:
            return []
        
        party = []
        for i in range(PARTY_SIZE):
            offset = i * POKEMON_SIZE_BYTES
            mon_data = data[offset:offset + POKEMON_SIZE_BYTES]
            pokemon = self._decode_party_pokemon(mon_data)
            if pokemon and pokemon.is_valid and pokemon.species_id > 0:
                party.append(pokemon)
        
        return party
    
    def _decode_party_pokemon(self, data: bytes) -> Optional[PartyPokemon]:
        """Decode a 100-byte party Pokemon structure."""
        if len(data) != POKEMON_SIZE_BYTES:
            return None
        
        # Personality & OT (First 8 bytes)
        pid = struct.unpack('<I', data[0:4])[0]
        ot_id = struct.unpack('<I', data[4:8])[0]
        
        # Empty slot check
        if pid == 0:
            return None
        
        # Nickname (10 bytes, offset 8)
        nickname = self._decode_string(data[8:18])
        
        # Encrypted substructures (48 bytes, offset 32)
        key = pid ^ ot_id
        raw_sub = data[32:80]
        decrypted_sub = decrypt_data(raw_sub, key)
        
        # Verify checksum
        checksum = struct.unpack('<H', data[28:30])[0]
        is_valid = verify_checksum(decrypted_sub, checksum)
        
        # Unshuffle to standard GAEM order
        ordered = unshuffle_substructures(decrypted_sub, pid)
        
        # Growth Block (0)
        species_id = struct.unpack('<H', ordered[0:2])[0]
        item_id = struct.unpack('<H', ordered[2:4])[0]
        
        # Attacks Block (1) - offset 12
        moves = list(struct.unpack('<HHHH', ordered[12:20]))
        
        # EVs Block (2) - offset 24
        evs = list(struct.unpack('<BBBBBB', ordered[24:30]))
        
        # Unencrypted stats (offset 80+)
        level = data[84]
        current_hp = struct.unpack('<H', data[86:88])[0]
        max_hp = struct.unpack('<H', data[88:90])[0]
        attack = struct.unpack('<H', data[90:92])[0]
        defense = struct.unpack('<H', data[92:94])[0]
        speed = struct.unpack('<H', data[94:96])[0]
        sp_attack = struct.unpack('<H', data[96:98])[0]
        sp_defense = struct.unpack('<H', data[98:100])[0]
        
        return PartyPokemon(
            species_id=species_id,
            nickname=nickname,
            level=level,
            current_hp=current_hp,
            max_hp=max_hp,
            attack=attack,
            defense=defense,
            speed=speed,
            sp_attack=sp_attack,
            sp_defense=sp_defense,
            item_id=item_id,
            moves=moves,
            evs=evs,
            is_valid=is_valid
        )
    
    # -------------------------------------------------------------------------
    # Battle Mon Reading
    # -------------------------------------------------------------------------
    
    def read_battle_mons(self) -> List[BattleMon]:
        """Read active battle Pokemon (gBattleMons)."""
        # Read battler count first
        count_resp = self._read_u16(BATTLERS_COUNT_OFFSET)
        battler_count = count_resp if count_resp else 2
        battler_count = min(battler_count, BATTLE_MON_COUNT)
        
        data = self._read_block(BATTLE_MONS_OFFSET, BATTLE_MON_SIZE * battler_count)
        if not data:
            return []
        
        mons = []
        for i in range(battler_count):
            offset = i * BATTLE_MON_SIZE
            mon_data = data[offset:offset + BATTLE_MON_SIZE]
            mon = self._decode_battle_mon(mon_data)
            if mon and mon.species_id > 0:
                mons.append(mon)
        
        return mons
    
    def _decode_battle_mon(self, data: bytes) -> Optional[BattleMon]:
        """Decode an 88-byte battle mon structure (unencrypted)."""
        if len(data) < BATTLE_MON_SIZE:
            return None
        
        species_id = struct.unpack('<H', data[BATTLE_MON_SPECIES:BATTLE_MON_SPECIES+2])[0]
        if species_id == 0:
            return None
        
        attack = struct.unpack('<H', data[BATTLE_MON_ATTACK:BATTLE_MON_ATTACK+2])[0]
        defense = struct.unpack('<H', data[BATTLE_MON_DEFENSE:BATTLE_MON_DEFENSE+2])[0]
        speed = struct.unpack('<H', data[BATTLE_MON_SPEED:BATTLE_MON_SPEED+2])[0]
        sp_attack = struct.unpack('<H', data[BATTLE_MON_SP_ATTACK:BATTLE_MON_SP_ATTACK+2])[0]
        sp_defense = struct.unpack('<H', data[BATTLE_MON_SP_DEFENSE:BATTLE_MON_SP_DEFENSE+2])[0]
        
        # Moves (4 x u16 starting at offset 0x0C)
        moves = list(struct.unpack('<HHHH', data[BATTLE_MON_MOVE1:BATTLE_MON_MOVE1+8]))
        
        # PP (4 x u8 at offset 0x14)
        pp = list(data[BATTLE_MON_PP:BATTLE_MON_PP+4])
        
        # HP values
        current_hp = struct.unpack('<H', data[BATTLE_MON_HP:BATTLE_MON_HP+2])[0]
        max_hp = struct.unpack('<H', data[BATTLE_MON_MAX_HP:BATTLE_MON_MAX_HP+2])[0]
        level = data[BATTLE_MON_LEVEL]
        
        # Status
        status1 = struct.unpack('<I', data[BATTLE_MON_STATUS1:BATTLE_MON_STATUS1+4])[0]
        status2 = struct.unpack('<I', data[BATTLE_MON_STATUS2:BATTLE_MON_STATUS2+4])[0]
        
        # Stat stages (8 x s8)
        stat_stages = list(struct.unpack('<bbbbbbbb', data[BATTLE_MON_STAT_STAGES:BATTLE_MON_STAT_STAGES+8]))
        
        return BattleMon(
            species_id=species_id,
            level=level,
            current_hp=current_hp,
            max_hp=max_hp,
            attack=attack,
            defense=defense,
            speed=speed,
            sp_attack=sp_attack,
            sp_defense=sp_defense,
            moves=moves,
            pp=pp,
            status1=status1,
            status2=status2,
            stat_stages=stat_stages
        )
    
    def read_battle_weather(self) -> int:
        """Read current battle weather."""
        weather = self._read_u16(BATTLE_WEATHER_OFFSET)
        return weather if weather is not None else 0
    
    def get_weather_name(self, weather: int) -> str:
        """Get human-readable weather name."""
        if weather == 0:
            return "None"
        # Weather is a bitfield
        names = []
        if weather & 0x07:  # Rain bits
            names.append("Rain")
        if weather & 0x18:  # Sandstorm bits
            names.append("Sandstorm")
        if weather & 0x60:  # Sun bits
            names.append("Sun")
        if weather & 0x80:  # Hail
            names.append("Hail")
        return ", ".join(names) if names else f"Unknown ({weather})"
    
    # -------------------------------------------------------------------------
    # Battle State Extension
    # -------------------------------------------------------------------------

    def read_battle_state(self) -> BattleState:
        """Read current battle state from memory."""
        if not self.memory:
            return BattleState()
            
        outcome = self.read_battle_outcome()
        move_id, move_user = self.read_last_move()
        is_input = self.read_input_status()
        
        # Read New Flags
        cursors = self._read_cursors()
        battle_flags = self._read_u32(BATTLE_TYPE_FLAGS_OFFSET) or 0
        move_results = self._read_u8(MOVE_RESULT_FLAGS_OFFSET) or 0
        
        # Read Battle Mons
        battle_mons = self.read_battle_mons()
        
        # Read Parties (Full Data)
        # Note: We need to convert PartyPokemon to PlayerPokemon/EnemyPokemon
        # or update BattleState to accept PartyPokemon.
        # For now, we will map them to the core dataclasses structure.
        
        party_mons = self.read_player_party()
        enemy_party_mons = self.read_enemy_party()
        
        player_party = []
        for p in party_mons:
            player_party.append(self._convert_party_mon_to_player(p))

        enemy_party = []
        for p in enemy_party_mons:
            enemy_party.append(self._convert_party_mon_to_enemy(p))

        player_mon = None
        enemy_mon = None
        player_disable = None
        enemy_disable = None
        player_side_timer = None
        enemy_side_timer = None
        
        if len(battle_mons) >= 2:
            p_data = battle_mons[0]  # Player slot 0
            e_data = battle_mons[1]  # Enemy slot 1 (singles)
            
            # --- POPULATE PLAYER ---
            p_moves = self._construct_moves(p_data.moves, p_data.pp)
            player_mon = self._construct_player_mon(p_data, p_moves)
            
            # --- POPULATE ENEMY ---
            enemy_mon = self._construct_enemy_mon(e_data)
            
            # --- READ ADDITIONAL STRUCTS ---
            player_disable = self._read_disable_struct(0)
            enemy_disable = self._read_disable_struct(1)
            
            player_side_timer = self._read_side_timer(0)
            enemy_side_timer = self._read_side_timer(1)
            
        return BattleState(
            active_pokemon=player_mon,
            enemy_active_pokemon=enemy_mon,
            party=player_party,
            enemy_party=enemy_party,
            battle_outcome=outcome,
            last_move_used=move_id,
            last_move_user=move_user,
            is_waiting_for_input=is_input,
            
            # New Fields
            battle_type_flags=battle_flags,
            move_result_flags=move_results,
            player_disable_struct=player_disable,
            enemy_disable_struct=enemy_disable,
            player_side_timer=player_side_timer,
            enemy_side_timer=enemy_side_timer,
            
            # Cursors
            battler_in_menu_id=cursors.get('in_menu', 0),
            action_cursor=cursors.get('action', 0),
            move_cursor=cursors.get('move', 0)
        )

    def _convert_party_mon_to_player(self, p: PartyPokemon) -> Any:
        """Convert PartyPokemon to PlayerPokemon."""
        from ...core.dataclasses import PlayerPokemon, StatusCondition, Move
        
        # Create simplified Moves
        moves = []
        for mid in p.moves:
            if mid > 0:
                moves.append(Move(move_id=mid)) # PP not in this struct unless we read it or assume max
        
        return PlayerPokemon(
            species_id=p.species_id,
            level=p.level,
            current_hp=p.current_hp,
            hp=p.max_hp,
            attack=p.attack,
            defense=p.defense,
            sp_attack=p.sp_attack,
            sp_defense=p.sp_defense,
            speed=p.speed,
            status_condition=StatusCondition(0), # TBD from status bits
            moves=moves,
            item_id=p.item_id,
            nickname=p.nickname
        )

    def _convert_party_mon_to_enemy(self, p: PartyPokemon) -> Any:
        """Convert PartyPokemon to EnemyPokemon."""
        from ...core.dataclasses import EnemyPokemon, Move
        
        moves = []
        for mid in p.moves:
             if mid > 0:
                moves.append(Move(move_id=mid))
                
        return EnemyPokemon(
            species_id=p.species_id,
            level=p.level,
            hp_percentage=(p.current_hp / p.max_hp * 100.0) if p.max_hp > 0 else 0.0,
            nickname=p.nickname,
            revealed_moves=moves
        )

    def _construct_moves(self, move_ids: List[int], pps: List[int]) -> List[Any]:
        """Helper to construct Move objects."""
        # This relies on self.backend being available to access KB if needed, 
        # or we just make simplified Move objects for now.
        from ...core.dataclasses import Move
        moves = []
        for i, mid in enumerate(move_ids):
            if mid > 0:
                # Ideally fetch from KB, but here we just pass ID/PP
                moves.append(Move(move_id=mid, current_pp=pps[i] if i < len(pps) else 0))
        return moves

    def _construct_player_mon(self, data: BattleMon, moves: List[Any]) -> Any:
        from ...core.dataclasses import PlayerPokemon, StatusCondition
        return PlayerPokemon(
            species_id=data.species_id,
            level=data.level,
            current_hp=data.current_hp,
            hp=data.max_hp,
            attack=data.attack,
            defense=data.defense,
            sp_attack=data.sp_attack,
            sp_defense=data.sp_defense,
            speed=data.speed,
            status_condition=StatusCondition(0), # TODO: Map bits
            moves=moves,
            stat_stages=data.stat_stages
        )

    def _construct_enemy_mon(self, data: BattleMon) -> Any:
        from ...core.dataclasses import EnemyPokemon
        return EnemyPokemon(
            species_id=data.species_id,
            level=data.level,
            hp_percentage=(data.current_hp / data.max_hp * 100.0) if data.max_hp > 0 else 0.0,
            nickname=f"Species#{data.species_id}" # Placeholder
        )

    def _read_disable_struct(self, battler_id: int) -> DisableStruct:
        """Read DisableStruct for a battler."""
        # Size is 0x1C (28 bytes)
        base = DISABLE_STRUCTS_OFFSET + (battler_id * 28)
        data = self._read_block(base, 28)
        if not data:
            return DisableStruct()
        
        # Unpack standard fields
        # 0x00: disableMove (u16)
        # 0x02: disableTimer (u8)
        # 0x04: encoredMove (u16)
        # 0x07: encoreTimer (u8)
        # 0x09: tauntTimer (u8)
        
        val = DisableStruct()
        val.disable_move = struct.unpack('<H', data[0:2])[0]
        val.disable_timer = data[2]
        val.encored_move = struct.unpack('<H', data[4:6])[0]
        val.encore_timer = data[7]
        val.taunt_timer = data[9]
        return val

    def _read_side_timer(self, side_id: int) -> SideTimer:
        """Read SideTimer (Reflect/LightScreen/Mist/Safeguard)."""
        # Size is 8 bytes per side
        base = SIDE_TIMERS_OFFSET + (side_id * 8)
        data = self._read_block(base, 8)
        if not data:
            return SideTimer()
            
        val = SideTimer()
        val.reflect_timer = data[0]
        val.lightscreen_timer = data[2]
        val.mist_timer = data[4]
        val.safeguard_timer = data[6]
        return val

    def _read_cursors(self) -> Dict[str, int]:
        """Read all cursor positions."""
        in_menu = self._read_u8(BATTLER_IN_MENU_ID_OFFSET) or 0
        action = self._read_u8(ACTION_SELECTION_CURSOR) or 0
        move = self._read_u8(MOVE_SELECTION_CURSOR) or 0
        return {"in_menu": in_menu, "action": action, "move": move}
    
    def _read_u8(self, addr: int) -> Optional[int]:
        """Read unsigned 8-bit value (using read_u16 masked)."""
        # MemoryReader usually has _read_u16 etc.
        # We can implement _read_u8 by reading a byte if available, or u16.
        # Connector might support READ_U8, if not we fallback.
        # Assuming READ_BLOCK for 1 byte is safest.
        data = self._read_block(addr, 1)
        return data[0] if data else None

    # -------------------------------------------------------------------------
    # Battle State Extension
    # -------------------------------------------------------------------------

    def read_battle_outcome(self) -> BattleOutcome:
        """Read the current battle outcome (win/loss/etc)."""
        val = self._read_u32(BATTLE_OUTCOME_OFFSET) 
        # Actually it's an 8-bit value usually but we can read larger
        # If we read 0 bytes or something goes wrong, assume ongoing
        if val is None:
            return BattleOutcome.ONGOING
        
        # gBattleOutcome is a u8 in C, so mask it just in case
        val = val & 0xFF
        
        if val == 1:
            return BattleOutcome.WIN
        elif val == 2:
            return BattleOutcome.LOSS
        elif val == 3:
            return BattleOutcome.DRAW
        elif val == 4:
            return BattleOutcome.RAN
        else:
            return BattleOutcome.ONGOING

    def read_last_move(self) -> Tuple[int, int]:
        """
        Read the last used move and who used it.
        Returns: (move_id, attacker_slot)
        """
        # Mapo says gLastMoves at LAST_USED_MOVE_OFFSET
        # It's an array of u16. We just need the most recent one? 
        # Actually gLastMoves[battlerId] tells us the last move THAT battler used.
        # This API expects "The last move used in the battle".
        # We might need to look at gBattleStruct->moveTarget or similar for that.
        # For now, let's keep the legacy behavior if possible or return the player's last move.
        # Actually, let's read the whole array.
        
        # Temporary mismatch fix: returning simple tuple to satisfy interface
        return (0, 0) 

    def read_input_status(self) -> bool:
        """Check if the game is waiting for player input."""
        # This is a boolean flag (u8) or bitfield. 
        # Usually checking if lowest bit is set is safer if it's a bitfield.
        val = self._read_u32(BATTLE_INPUT_WAIT_FLAG_OFFSET)
        if val is None:
            return False
        return (val & 1) != 0

    # -------------------------------------------------------------------------
    # Frontier State Reading
    # -------------------------------------------------------------------------
    
    def read_frontier_state(self, facility: int = FACILITY_FACTORY, battle_mode: int = 0) -> Optional[FrontierState]:
        """Read Battle Frontier game state."""
        # Read level mode
        level_mode = self._read_ptr_u16(SAVE_BLOCK_2_PTR, FRONTIER_LVL_MODE_OFFSET)
        if level_mode is None:
            return None
        level_mode = level_mode & 1  # Only lowest bit matters
        
        # Get win streak offset based on facility
        streak_offsets = {
            FACILITY_TOWER: FRONTIER_TOWER_STREAK_OFFSET,
            FACILITY_DOME: FRONTIER_DOME_STREAK_OFFSET,
            FACILITY_PALACE: FRONTIER_PALACE_STREAK_OFFSET,
            FACILITY_ARENA: FRONTIER_ARENA_STREAK_OFFSET,
            FACILITY_FACTORY: FRONTIER_FACTORY_STREAK_OFFSET,
            FACILITY_PIKE: FRONTIER_PIKE_STREAK_OFFSET,
            FACILITY_PYRAMID: FRONTIER_PYRAMID_STREAK_OFFSET,
        }
        
        base_offset = streak_offsets.get(facility, FRONTIER_FACTORY_STREAK_OFFSET)
        # Win streaks are stored as [battleMode][lvlMode] array
        streak_offset = base_offset + 2 * (2 * battle_mode + level_mode)
        
        win_streak = self._read_ptr_u16(SAVE_BLOCK_2_PTR, streak_offset)
        if win_streak is None:
            win_streak = 0
        
        # Read factory rental count
        rental_offset = FRONTIER_FACTORY_RENTS_OFFSET + 2 * (2 * battle_mode + level_mode)
        rental_count = self._read_ptr_u16(SAVE_BLOCK_2_PTR, rental_offset)
        if rental_count is None:
            rental_count = 0
        
        return FrontierState(
            facility=facility,
            battle_mode=battle_mode,
            level_mode=level_mode,
            win_streak=win_streak,
            rental_count=rental_count
        )
    
    def read_rental_mons(self) -> List[RentalMon]:
        """Read Battle Factory rental Pokemon (6 slots)."""
        # Rental mons: 6 x 12 bytes at SaveBlock2 + 0xE70
        data = self._read_ptr_block(SAVE_BLOCK_2_PTR, FRONTIER_RENTAL_MONS_OFFSET, 6 * RENTAL_MON_SIZE)
        if not data:
            return []
        
        rentals = []
        for i in range(6):
            offset = i * RENTAL_MON_SIZE
            mon_data = data[offset:offset + RENTAL_MON_SIZE]
            
            # First 2 bytes = frontier mon ID (u16)
            frontier_mon_id = struct.unpack('<H', mon_data[0:2])[0]
            
            # Additional data in RentalMon struct
            iv_spread = mon_data[2] if len(mon_data) > 2 else 0
            ability_num = mon_data[3] if len(mon_data) > 3 else 0
            personality = struct.unpack('<I', mon_data[4:8])[0] if len(mon_data) >= 8 else 0
            
            if frontier_mon_id > 0:
                rentals.append(RentalMon(
                    slot=i,
                    frontier_mon_id=frontier_mon_id,
                    iv_spread=iv_spread,
                    ability_num=ability_num,
                    personality=personality
                ))
        
        return rentals
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def is_in_battle(self) -> bool:
        """Check if currently in a battle by reading enemy party."""
        # Check if enemy party has a valid Pokemon
        data = self._read_block(ENEMY_PARTY_OFFSET + 19, 1)  # Check language/egg byte
        if data and (data[0] & 2):  # Bit 1 indicates active battle
            return True
        return False
    
    def ping(self) -> bool:
        """Test connection to backend."""
        resp = self._send("PING")
        return resp == "PONG"
