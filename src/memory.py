from dataclasses import dataclass, field
from typing import List, Optional, Dict
import struct
import logging
from src.client import MgbaClient
from src.constants import *
from src.decryption import decrypt_data, unshuffle_substructures, verify_checksum
from src.db import PokemonDatabase

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
        party = []
        for i in range(count):
            offset = i * SIZE_POKEMON
            data = self.client.read_block(address + offset, SIZE_POKEMON)
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
        battle_mons = []
        for i in range(4):
            offset = i * SIZE_BATTLE_MON
            data = self.client.read_block(ADDR_BATTLE_MONS + offset, SIZE_BATTLE_MON)
            
            species_id = struct.unpack("<H", data[0:2])[0]
            if species_id == 0:
                continue
                
            # Correct Offsets for Gen 3 BattlePokemon (gBattleMons)
            # 0x0C: Moves (u16 * 4)
            # 0x14: PP (u8 * 4)
            # 0x28: HP (u16)
            # 0x2A: MaxHP (u16)
            # 0x2C: Level (u8)
            # 0x4C: Status1 (u32)
            
            # Offsets based on pokeemerald struct BattlePokemon
            # Moves: 0x0C (12) -> 4 * u16 = 8 bytes (12-20)
            moves_coords = [
                struct.unpack("<H", data[12:14])[0],
                struct.unpack("<H", data[14:16])[0],
                struct.unpack("<H", data[16:18])[0],
                struct.unpack("<H", data[18:20])[0],
            ]
            
            # PP: 0x24 (36) -> 4 * u8 = 4 bytes (36-40)
            pp = [data[36], data[37], data[38], data[39]]
            
            # HP: 0x28 (40) -> u16
            hp = struct.unpack("<H", data[40:42])[0]
            
            # Level: 0x2A (42) -> u8
            level = data[42]
            
            # Max HP: 0x2C (44) -> u16
            max_hp = struct.unpack("<H", data[44:46])[0]
            
            # Status: 0x4C (76) -> u32
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
                species_id=facility_mon_id, # Keeping as ID, but technically it's facility ID
                species_name=self.db.get_rental_mon_species_name(facility_mon_id),
                ivs=ivs,
                ability_num=ability,
                personality=pid
            ))
        return rentals

    def get_game_state(self):
        outcome_map = {0: "Ongoing", 1: "Won", 2: "Lost", 3: "Draw", 4: "Ran"}
        outcome = self.client.read_block(ADDR_BATTLE_OUTCOME, 1)[0]
        
        # Determine Phase
        # Simple heuristic: If outcome is 0, we are in battle.
        # If outcome is not 0, we are likely in a menu, overworld, or rental selection.
        # Ideally we'd check specific callbacks or menu IDs, but this serves the purpose for now.
        phase = "BATTLE" if outcome == 0 else "RENTAL/MENU"
        
        # Read gLastMoves array (size 4 * 2 = 8 bytes)
        last_moves_data = self.client.read_block(0x02024248, 8) 
        last_move_player = struct.unpack("<H", last_moves_data[0:2])[0]
        last_move_enemy = struct.unpack("<H", last_moves_data[2:4])[0]
        
        return {
             "outcome": outcome_map.get(outcome, f"Unknown({outcome})"),
             "input_wait": "YES" if self.client.input_waiting() else "NO",
             "rng": self.client.read_u32(ADDR_RNG_VALUE),
             "last_move_player": self.db.get_move_name(last_move_player) if last_move_player else "-",
             "last_move_enemy": self.db.get_move_name(last_move_enemy) if last_move_enemy else "-",
             "phase": phase
        }
