from typing import List, Optional, Dict
import struct
import logging
import time
from src.client import MgbaClient
from src.constants import *
from src.decryption import decrypt_data, unshuffle_substructures, verify_checksum
from src.db import PokemonDatabase
from src.models import PartyPokemon, BattlePokemon, RentalPokemon, BattleFactorySnapshot, FrontierMetadata

logger = logging.getLogger(__name__)

def decode_string(data: bytes) -> str:
    """Decodes a Gen 3 character string.
    
    The Generation 3 games use a proprietary character map. This function maps selected
    hex values to their ASCII equivalents.

    Args:
        data (bytes): The raw byte string from memory.

    Returns:
        str: The decoded string (e.g., "PIKACHU").
    """
    res = ""
    for b in data:
        if b == 0xFF: break
        if 0xBB <= b <= 0xD4:
            res += chr(b - 0xBB + 65)
        elif 0xD5 <= b <= 0xEE:
            res += chr(b - 0xD5 + 97)
        elif 0xA1 <= b <= 0xAA:
            res += chr(b - 0xA1 + 48)
        else:
            res += "?"
    return res

class MemoryReader:
    """Handles low-level memory operations to read game state.
    
    This class bridges the gap between raw emulator RAM and structured Python objects.
    It handles addressing, decryption, and parsing of Pokémon data structures.
    
    Attributes:
        client (MgbaClient): The client connection to the emulator.
        db (PokemonDatabase): Connection to the knowledge base for enriching raw data.
    """
    
    def __init__(self, client: MgbaClient):
        """Initializes the MemoryReader.
        
        Args:
            client (MgbaClient): An active MgbaClient instance.
        """
        self.client = client
        self.db = PokemonDatabase()
        self.db.connect()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def _get_status_string(self, status: int) -> str:
        """Converts a status bitmask into a human-readable string (e.g., "SLP|PSN")."""
        if status == 0: return "OK"
        s = []
        if status & 0x7: s.append("SLP")
        if status & 0x8: s.append("PSN")
        if status & 0x10: s.append("BRN")
        if status & 0x20: s.append("FRZ")
        if status & 0x40: s.append("PAR")
        if status & 0x80: s.append("TOX")
        return "|".join(s)


    def _create_move(self, move_id: int) -> 'Move':
        """Factory method to create a Move object from an ID."""
        # Import here to avoid circular dependency if models imports db
        from src.models import Move
        d = self.db.get_move_details(move_id)
        if not d:
             # Fallback
             return Move(move_id, f"Move {move_id}", "Normal", 0, 0, 0, "", "", 0, [], "Physical")
        return Move(**d)

    def _create_species(self, species_id: int) -> Optional['SpeciesInfo']:
        """Factory method to create a SpeciesInfo object from an ID."""
        from src.models import SpeciesInfo
        d = self.db.get_species_details(species_id)
        if not d: return None
        return SpeciesInfo(**d)

    def _create_item(self, item_id: int) -> 'ItemInfo':
        """Factory method to create an ItemInfo object from an ID."""
        from src.models import ItemInfo
        d = self.db.get_item_details(item_id)
        if not d: return ItemInfo(item_id, f"Item {item_id}", "", "None", 0)
        return ItemInfo(**d)

    def read_party(self, address: int, count: int = 6) -> List[PartyPokemon]:
        """Reads a list of Pokémon from a party memory block.
        
        This method performs a single bulk read for efficiency and then iterates through
        the block to parse each Pokémon. It handles the specific encryption and shuffling
        logic used in Gen 3 party data.

        Args:
            address (int): Memory address where the party starts (e.g., ADDR_PLAYER_PARTY).
            count (int): Number of Pokémon slots to read (default 6).

        Returns:
            List[PartyPokemon]: A list of populated PartyPokemon objects. Empty slots are skipped.
        """
        total_size = SIZE_POKEMON * count
        # Bulk read the entire party block
        party_data = self.client.read_block(address, total_size)
        
        party = []
        for i in range(count):
            offset = i * SIZE_POKEMON
            data = party_data[offset : offset + SIZE_POKEMON]
            
            pid = struct.unpack("<I", data[0:4])[0]
            
            if pid == 0:
                continue 

            otid = struct.unpack("<I", data[4:8])[0]
            nickname = decode_string(data[8:18])
            checksum = struct.unpack("<H", data[28:30])[0]
            
            key = pid ^ otid
            substruct_data = data[32:80]
            decrypted = decrypt_data(substruct_data, key)
            
            if not verify_checksum(decrypted, checksum):
                logger.warning(f"Checksum failed for mon {i} PID:{pid:X}")
                
            unshuffled = unshuffle_substructures(decrypted, pid)
            
            # Growth: Species (0-2), Item (2-4), XP (4-8), PPBonuses (8), Friend (9)
            growth = unshuffled[0:12]
            species_id = struct.unpack("<H", growth[0:2])[0]
            item_id = struct.unpack("<H", growth[2:4])[0]
            exp = struct.unpack("<I", growth[4:8])[0]
            pp_bonuses = growth[8]
            friendship = growth[9]
            
            # Attacks: Move1(0-2)... Move4(6-8), PP1(8)..PP4(11)
            attacks = unshuffled[12:24]
            move_ids = [
                struct.unpack("<H", attacks[0:2])[0],
                struct.unpack("<H", attacks[2:4])[0],
                struct.unpack("<H", attacks[4:6])[0],
                struct.unpack("<H", attacks[6:8])[0],
            ]
            pp_values = [attacks[8], attacks[9], attacks[10], attacks[11]]
            
            # EV & Condition: HP(0), Atk(1), Def(2), Spd(3), SpAtk(4), SpDef(5)...
            evs_data = unshuffled[24:36]
            evs = {
                "hp": evs_data[0],
                "atk": evs_data[1],
                "def": evs_data[2],
                "spe": evs_data[3],
                "spa": evs_data[4],
                "spd": evs_data[5]
            }
            # Condition: Cool(6), Beauty(7), Cute(8), Smart(9), Tough(10), Feel(11) - Skip for now
            
            # Misc: Pokerus, MetLocation, IVs, etc. index 36:48
            misc = unshuffled[36:48]
            pokerus = misc[0]
            met_location = misc[1]
            
            # IVs, Egg, Ability are packed into a u32 at offset 4
            iv_word = struct.unpack("<I", misc[4:8])[0]
            # Bitfield:
            # 0-4: HP IV (5 bits)
            # 5-9: Atk IV
            # 10-14: Def IV
            # 15-19: Spd IV
            # 20-24: SpAtk IV
            # 25-29: SpDef IV
            # 30: Is Egg
            # 31: Ability Num
            
            ivs = {
                "hp": iv_word & 0x1F,
                "atk": (iv_word >> 5) & 0x1F,
                "def": (iv_word >> 10) & 0x1F,
                "spe": (iv_word >> 15) & 0x1F,
                "spa": (iv_word >> 20) & 0x1F,
                "spd": (iv_word >> 25) & 0x1F
            }
            is_egg = bool((iv_word >> 30) & 1)
            ability_num = (iv_word >> 31) & 1
            
            status = struct.unpack("<I", data[80:84])[0]
            level = data[84]
            hp = struct.unpack("<H", data[86:88])[0]
            max_hp = struct.unpack("<H", data[88:90])[0]
            
            # Real Stats (calculated by game and stored in RAM for valid party mons)
            atk = struct.unpack("<H", data[90:92])[0]
            defense = struct.unpack("<H", data[92:94])[0]
            speed = struct.unpack("<H", data[94:96])[0]
            sp_atk = struct.unpack("<H", data[96:98])[0]
            sp_def = struct.unpack("<H", data[98:100])[0]
            
            real_stats = {"atk": atk, "def": defense, "spe": speed, "spa": sp_atk, "spd": sp_def}
            
            party.append(PartyPokemon(
                pid=pid,
                species_id=species_id,
                species_name=self.db.get_species_name(species_id),
                moves=[self._create_move(m) for m in move_ids if m != 0],
                pp=[p for p, m in zip(pp_values, move_ids) if m != 0],
                hp=max(0, hp), # Sanity check
                max_hp=max_hp,
                level=level,
                nickname=nickname,
                status=status,
                item=self._create_item(item_id),
                real_stats=real_stats,
                species_info=self._create_species(species_id),
                ivs=ivs,
                evs=evs,
                friendship=friendship,
                exp=exp,
                pp_bonuses=pp_bonuses,
                pokerus=pokerus,
                met_location=met_location,
                is_egg=is_egg,
                ability_num=ability_num
            ))
            
        return party

    def read_battle_mons(self) -> List[BattlePokemon]:
        """Reads the active battle Pokémon structures.
        
        The game stores transient battle data (stats changes, current HP, etc.) in a
        separate `gBattleMons` array during combat. This method reads all 4 potential slots.
        
        Returns:
            List[BattlePokemon]: List of active battlers (Slot 0=Player, 1=Enemy, etc.).
        """
        total_size = SIZE_BATTLE_MON * 4
        data_block = self.client.read_block(ADDR_BATTLE_MONS, total_size)
        
        battle_mons = []
        for i in range(4):
            offset = i * SIZE_BATTLE_MON
            data = data_block[offset : offset + SIZE_BATTLE_MON]
            
            species_id = struct.unpack("<H", data[0:2])[0]
            if species_id == 0:
                continue
            
            # Battle Struct Stats
            # 0x00 Species
            # 0x02 Attack
            # 0x04 Defense
            # 0x06 Speed
            # 0x08 SpAtk
            # 0x0A SpDef
            atk = struct.unpack("<H", data[2:4])[0]
            defense = struct.unpack("<H", data[4:6])[0]
            speed = struct.unpack("<H", data[6:8])[0]
            sp_atk = struct.unpack("<H", data[8:10])[0]
            sp_def = struct.unpack("<H", data[10:12])[0]
            
            real_stats = {"atk": atk, "def": defense, "spe": speed, "spa": sp_atk, "spd": sp_def}

            # Offsets based on pokeemerald struct BattlePokemon
            # 0x0C (12) - Moves
            moves_coords = [
                struct.unpack("<H", data[12:14])[0],
                struct.unpack("<H", data[14:16])[0],
                struct.unpack("<H", data[16:18])[0],
                struct.unpack("<H", data[18:20])[0],
            ]
            
            # 0x1E (30) - Ability
            ability_id = data[30]
            # 0x1F (31) - Types
            type1_id = data[31]
            type2_id = data[32]
            
            # 0x24 (36) - PP
            pp = [data[36], data[37], data[38], data[39]]
            
            # 0x28 (40) - HP
            hp = struct.unpack("<H", data[40:42])[0]
            # 0x2A (42) - Level
            level = data[42]
            # 0x2C (44) - MaxHP (matches prev code)
            max_hp = struct.unpack("<H", data[44:46])[0]
            
            # 0x2E (46) - Held Item (Active)
            item_id = struct.unpack("<H", data[46:48])[0]
            
            # 0x39 (57) - PP Bonuses
            pp_bonuses = data[57]
            
            # 0x4C (76) - Status1 (Sleep, Poison, etc)
            status = struct.unpack("<I", data[76:80])[0]
            
            # 0x50 (80) - Status2 (Volatile: Confusion, etc)
            status2 = struct.unpack("<I", data[80:84])[0]

            species_name = self.db.get_species_name(species_id)
            moves = [self._create_move(m_id) for m_id in moves_coords]
            
            # PID at offset 52 (0x34) in Gen 3 Battle Struct?
            # Previous code said 52. Let's keep it.
            pid = struct.unpack("<I", data[52:56])[0]
            
            # Resolve Types strings
            # We assume type IDs match standard Gen 3 types. 
            # 0=Normal, 1=Fighting, etc.
            # We can use a helper or simple map. 
            # For strict correctness we should have get_type_name.
            # I'll stick to raw IDs or a default string for now, or use models.
            # Actually models has type as string. 
            # Let's add get_type_name to DB or simple map here to be safe.
            type_map = [
                "Normal", "Fighting", "Flying", "Poison", "Ground", "Rock", "Bug", "Ghost", "Steel",
                "Mystery", "Fire", "Water", "Grass", "Electric", "Psychic", "Ice", "Dragon", "Dark"
            ]
            def get_type_str(tid):
                return type_map[tid] if 0 <= tid < len(type_map) else f"Type{tid}"

            battle_mons.append(BattlePokemon(
                slot=i,
                species_id=species_id,
                species_name=species_name,
                level=level,
                hp=hp,
                max_hp=max_hp,
                status=status,
                moves=moves,
                pp=pp,
                real_stats=real_stats,
                species_info=self._create_species(species_id),
                pid=pid,
                type1=get_type_str(type1_id),
                type2=get_type_str(type2_id),
                ability_id=ability_id,
                item_id=item_id,
                status2=status2,
                pp_bonuses=pp_bonuses
            ))
        return battle_mons

    def read_rental_mons(self) -> List[RentalPokemon]:
        """Reads the available rental/swap Pokémon in the Battle Factory.
        
        Rental Pokémon are stored in a contiguous array in the Battle Frontier data section.
        This method parses their compact structure (Species, IVs, Ability, PID) and
        enriches it with static move/item data from the database since the game doesn't
        store moves continuously in RAM for rentals.

        Returns:
            List[RentalPokemon]: List of the 3 (initial) or 6 (swap) logical options.
        """
        # Pointer to SaveBlock2
        sb2 = self.client.read_u32(ADDR_SAVEBLOCK2_PTR)
        if not sb2: return []
        
        # Rentals are at offset 0xE70 from SaveBlock2
        start_addr = sb2 + OFFSET_FACTORY_RENTAL_MONS
        data = self.client.read_block(start_addr, SIZE_RENTAL_MON * 6)
        
        rentals = []
        for i in range(6):
            offset = i * SIZE_RENTAL_MON
            # Struct: MonID (2), IVs (1), Ability (1), Personality (4), OTID (4) = 12 bytes
            mon_data = data[offset:offset+12]
            
            facility_mon_id = struct.unpack("<H", mon_data[0:2])[0]
            ivs = mon_data[2]
            ability = mon_data[3]
            pid = struct.unpack("<I", mon_data[4:8])[0]
            
            # We need to query battle_frontier_mons table to get moves/item for this facility mon
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT species_id, move1_id, move2_id, move3_id, move4_id, item_id
                FROM battle_frontier_mons WHERE id = ?
            """, (facility_mon_id,))
            row = cursor.fetchone()
            
            if row:
                 species_id = row['species_id']
                 move_ids = [row['move1_id'], row['move2_id'], row['move3_id'], row['move4_id']]
                 item_id = row['item_id']
                 
                 moves = [self._create_move(m) for m in move_ids if m != 0]
                 item = self._create_item(item_id)
                 
                 if not moves:
                     logger.warning(f"Rental Mon {i} (ID: {facility_mon_id}) found in DB but has NO moves! MoveIDs: {move_ids}")
            else:
                 logger.warning(f"Rental Mon {i} (ID: {facility_mon_id}) NOT found in battle_frontier_mons table!")
                 species_id = facility_mon_id # Fallback if ID matches species directly (unlikely)
                 moves = []
                 item = None

            rentals.append(RentalPokemon(
                slot=i,
                species_id=species_id,
                species_name=self.db.get_species_name(species_id),
                ivs=ivs,
                ability_num=ability,
                personality=pid,
                species_info=self._create_species(species_id),
                moves=moves,
                item=item
            ))
        return rentals

    def read_frontier_metadata(self) -> Optional[FrontierMetadata]:
        """Reads Battle Frontier metadata from SaveBlock2."""
        sb2 = self.client.read_u32(ADDR_SAVEBLOCK2_PTR)
        if not sb2: return None
        
        # Read Frontier Vars
        # lv_mode: u8 at OFFSET_FRONTIER_LVL_MODE
        lvl_mode = self.client.read_u8(sb2 + OFFSET_FRONTIER_LVL_MODE)
        
        # battle_num: u16 at OFFSET_FRONTIER_BATTLE_NUM
        # Note: logic in constants.py says u16.
        battle_num = self.client.read_u16(sb2 + OFFSET_FRONTIER_BATTLE_NUM)
        
        # We can infer rental count or read it if we had an offset?
        # For now, just placeholder or deduce from rental array size?
        # Actually OFFSET_FACTORY_RENTS_COUNT is defined in constants. But it says u16[][]?
        # Let's just store 0 for now or derive validation.
        rental_count = 0
        
        return FrontierMetadata(
            lvl_mode=lvl_mode,
            battle_num=battle_num,
            rental_count=rental_count
        )


    def read_snapshot(self) -> BattleFactorySnapshot:
        """Captures the entire relevant state in a single snapshot.
        
        This is the main entry point for observation. It reads:
        1. Global game variables (Phase, Outcome, Input Wait).
        2. Context (Last moves used).
        3. Parties (Player and Enemy).
        4. Battle-specific data (Active Battlers) if relevant.
        5. Rental options if relevant.

        Returns:
             BattleFactorySnapshot: A fully populated snapshot of the current frame.
        """
        # 1. Read Critical State Variables
        outcome = self.client.read_u16(ADDR_BATTLE_OUTCOME) & 0xFF # Read u16 and mask to avoid single-byte read issues
        input_wait = self.client.input_waiting()
        rng = self.client.read_u32(ADDR_RNG_VALUE)
        map_layout = self.client.read_u16(ADDR_MAP_LAYOUT_ID)
        challenge_battle_num = self.client.read_u16(ADDR_CHALLENGE_BATTLE_NUM)
        
        # Weather
        weather_flags = self.client.read_u16(ADDR_BATTLE_WEATHER)
        weather_str = "Clear"
        if weather_flags & (WEATHER_RAIN_TEMPORARY | WEATHER_RAIN_DOWNPOUR | WEATHER_RAIN_PERMANENT):
            weather_str = "Rain"
        elif weather_flags & (WEATHER_SANDSTORM_TEMPORARY | WEATHER_SANDSTORM_PERMANENT):
             weather_str = "Sandstorm"
        elif weather_flags & (WEATHER_SUN_TEMPORARY | WEATHER_SUN_PERMANENT):
             weather_str = "Sun"
        elif weather_flags & WEATHER_HAIL_TEMPORARY:
             weather_str = "Hail"

        
        # 2. Last Moves
        last_moves_data = self.client.read_block(ADDR_LAST_MOVES, 8) 
        last_move_player_id = struct.unpack("<H", last_moves_data[0:2])[0]
        last_move_enemy_id = struct.unpack("<H", last_moves_data[2:4])[0]
        last_move_player = self.db.get_move_name(last_move_player_id) if last_move_player_id else "-"
        last_move_enemy = self.db.get_move_name(last_move_enemy_id) if last_move_enemy_id else "-"
        
        # 3. Read Parties (Needed for Phase Detection)
        player_party = self.read_party(ADDR_PLAYER_PARTY)
        enemy_party = self.read_party(ADDR_ENEMY_PARTY)
        
        # 4. Phase Detection Logic
        # | Phase | Layout | Party | Round |
        # | Rental | 347 | Empty | 0 |
        # | Swap | 347 | Full | 0-6 |
        # | Battle | 348 | Full | 0-6 |
        
        party_count = len(player_party)
        phase = "UNKNOWN"
        
        if map_layout == LAYOUT_FACTORY_PRE_BATTLE:
            if party_count == 0:
                phase = "RENTAL"
            else:
                phase = "SWAP"
        elif map_layout == LAYOUT_FACTORY_BATTLE:
            phase = "BATTLE"
             
        # Fallback/Sanity Check
        if phase == "UNKNOWN":
             # If we are in neither layout, we might be in transition or elsewhere?
             # For now, stick to the known states or report Map ID for debugging
            phase = f"UNKNOWN(Map:{map_layout})"

        # 5. Read Battle Mons (Only relevant if in Battle phase usually, but good to have)
        active_battlers = self.read_battle_mons()
        
        # 6. Read Rentals (Only needed in Rental/Swap)
        rental_candidates = []
        if phase in ["RENTAL", "SWAP"]:
            rental_candidates = self.read_rental_mons()
        
        # 7. Read Frontier Metadata
        frontier_info = self.read_frontier_metadata()
        
        return BattleFactorySnapshot(
            timestamp=time.time(),
            phase=phase,
            outcome=outcome,
            input_wait=input_wait,
            rng_seed=rng,
            weather=weather_str,
            last_move_player=last_move_player,
            last_move_enemy=last_move_enemy,
            player_party=player_party,
            enemy_party=enemy_party,
            active_battlers=active_battlers,
            rental_candidates=rental_candidates,
            frontier_info=frontier_info
        )
    # Legacy Game State Method (Deprecated but kept for compat if needed, though we will update main.py)
    def get_game_state(self):
        """Deprecated: Use read_snapshot() instead."""
        snapshot = self.read_snapshot()
        return {
            "outcome": {0: "Ongoing", 1: "Won", 2: "Lost", 3: "Draw", 4: "Ran"}.get(snapshot.outcome, f"Unknown({snapshot.outcome})"),
            "input_wait": "YES" if snapshot.input_wait else "NO",
            "rng": snapshot.rng_seed,
            "last_move_player": snapshot.last_move_player,
            "last_move_enemy": snapshot.last_move_enemy,
            "phase": snapshot.phase
        }
