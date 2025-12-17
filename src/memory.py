from typing import List, Optional, Dict
import struct
import logging
import time
from src.client import MgbaClient
from src.constants import *
from src.decryption import decrypt_data, unshuffle_substructures, verify_checksum
from src.db import PokemonDatabase
from src.models import PartyPokemon, BattlePokemon, RentalPokemon, BattleFactorySnapshot

logger = logging.getLogger(__name__)

def decode_string(data: bytes) -> str:
    """Decodes Gen 3 specific character map. Very basic implementation."""
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
    def __init__(self, client: MgbaClient):
        self.client = client
        self.db = PokemonDatabase()
        self.db.connect()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def _get_status_string(self, status: int) -> str:
        if status == 0: return "OK"
        s = []
        if status & 0x7: s.append("SLP")
        if status & 0x8: s.append("PSN")
        if status & 0x10: s.append("BRN")
        if status & 0x20: s.append("FRZ")
        if status & 0x40: s.append("PAR")
        if status & 0x80: s.append("TOX")
        return "|".join(s)

    def read_party(self, address: int, count: int = 6) -> List[PartyPokemon]:
        """Reads a list of Pokemon from memory using a single bulk read."""
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
            
            # Attacks: Move1(0-2)... Move4(6-8), PP1(8)..PP4(11)
            attacks = unshuffled[12:24]
            move_ids = [
                struct.unpack("<H", attacks[0:2])[0],
                struct.unpack("<H", attacks[2:4])[0],
                struct.unpack("<H", attacks[4:6])[0],
                struct.unpack("<H", attacks[6:8])[0],
            ]
            pp_values = [attacks[8], attacks[9], attacks[10], attacks[11]]
            
            status = struct.unpack("<I", data[80:84])[0]
            level = data[84]
            hp = struct.unpack("<H", data[86:88])[0]
            max_hp = struct.unpack("<H", data[88:90])[0]
            
            party.append(PartyPokemon(
                pid=pid,
                species_id=species_id,
                species_name=self.db.get_species_name(species_id),
                moves=[self.db.get_move_name(m) for m in move_ids if m != 0],
                pp=[p for p, m in zip(pp_values, move_ids) if m != 0],
                hp=max(0, hp), # Sanity check
                max_hp=max_hp,
                level=level,
                nickname=nickname,
                status=status,
                item_name=self.db.get_item_name(item_id)
            ))
            
        return party

    def read_battle_mons(self) -> List[BattlePokemon]:
        """Reads all 4 active battle mons in a single bulk read."""
        total_size = SIZE_BATTLE_MON * 4
        data_block = self.client.read_block(ADDR_BATTLE_MONS, total_size)
        
        battle_mons = []
        for i in range(4):
            offset = i * SIZE_BATTLE_MON
            data = data_block[offset : offset + SIZE_BATTLE_MON]
            
            species_id = struct.unpack("<H", data[0:2])[0]
            if species_id == 0:
                continue
                
            # Offsets based on pokeemerald struct BattlePokemon
            moves_coords = [
                struct.unpack("<H", data[12:14])[0],
                struct.unpack("<H", data[14:16])[0],
                struct.unpack("<H", data[16:18])[0],
                struct.unpack("<H", data[18:20])[0],
            ]
            
            pp = [data[36], data[37], data[38], data[39]]
            hp = struct.unpack("<H", data[40:42])[0]
            level = data[42]
            max_hp = struct.unpack("<H", data[44:46])[0]
            status = struct.unpack("<I", data[76:80])[0]

            species_name = self.db.get_species_name(species_id)
            moves = [self.db.get_move_name(m_id) for m_id in moves_coords]
            
            battle_mons.append(BattlePokemon(
                slot=i,
                species_id=species_id,
                species_name=species_name,
                level=level,
                hp=hp,
                max_hp=max_hp,
                status=status,
                moves=moves,
                pp=pp
            ))
        return battle_mons

    def read_rental_mons(self) -> List[RentalPokemon]:
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
            
            rentals.append(RentalPokemon(
                slot=i,
                species_id=facility_mon_id,
                species_name=self.db.get_rental_mon_species_name(facility_mon_id),
                ivs=ivs,
                ability_num=ability,
                personality=pid
            ))
        return rentals

    def read_snapshot(self) -> BattleFactorySnapshot:
        """Captures the entire relevant state in a single snapshot."""
        # 1. Read Critical State Variables
        outcome = self.client.read_u16(ADDR_BATTLE_OUTCOME) & 0xFF # Read u16 and mask to avoid single-byte read issues
        input_wait = self.client.input_waiting()
        rng = self.client.read_u32(ADDR_RNG_VALUE)
        map_layout = self.client.read_u16(ADDR_MAP_LAYOUT_ID)
        challenge_battle_num = self.client.read_u16(ADDR_CHALLENGE_BATTLE_NUM)
        
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
        
        return BattleFactorySnapshot(
            timestamp=time.time(),
            phase=phase,
            outcome=outcome,
            input_wait=input_wait,
            rng_seed=rng,
            last_move_player=last_move_player,
            last_move_enemy=last_move_enemy,
            player_party=player_party,
            enemy_party=enemy_party,
            active_battlers=active_battlers,
            rental_candidates=rental_candidates
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
