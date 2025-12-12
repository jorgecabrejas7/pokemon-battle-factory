import struct
import sqlite3
import os
from typing import List, Optional
from ...core.dataclasses import PlayerPokemon, Move
from ...core.enums import MoveCategory
from .decryption import decrypt_data, unshuffle_substructures, verify_checksum
from .constants import POKEMON_SIZE_BYTES

# Gen 3 Character Map (Simplified subset)
# To be expanded or replaced with a proper lookup table file
CHAR_MAP = {
    0x00: " ", 0xA1: "0", 0xA2: "1", 0xA3: "2", 0xA4: "3", 0xA5: "4", 
    0xA6: "5", 0xA7: "6", 0xA8: "7", 0xA9: "8", 0xAA: "9",
    0xBB: "A", 0xBC: "B", 0xBD: "C", 0xBE: "D", 0xBF: "E", 0xC0: "F", 
    0xC1: "G", 0xC2: "H", 0xC3: "I", 0xC4: "J", 0xC5: "K", 0xC6: "L", 
    0xC7: "M", 0xC8: "N", 0xC9: "O", 0xCA: "P", 0xCB: "Q", 0xCC: "R", 
    0xCD: "S", 0xCE: "T", 0xCF: "U", 0xD0: "V", 0xD1: "W", 0xD2: "X", 
    0xD3: "Y", 0xD4: "Z",
    0xD5: "a", 0xD6: "b", 0xD7: "c", 0xD8: "d", 0xD9: "e", 0xDA: "f", 
    0xDB: "g", 0xDC: "h", 0xDD: "i", 0xDE: "j", 0xDF: "k", 0xE0: "l", 
    0xE1: "m", 0xE2: "n", 0xE3: "o", 0xE4: "p", 0xE5: "q", 0xE6: "r", 
    0xE7: "s", 0xE8: "t", 0xE9: "u", 0xEA: "v", 0xEB: "w", 0xEC: "x", 
    0xED: "y", 0xEE: "z",
    0xFF: "" # Terminator
}

class EmeraldDecoder:
    def __init__(self, db_path: str = "src/data/knowledge_base.db"):
        self.db_path = db_path
        self._conn = None
        self._cursor = None

    def _connect_db(self):
        if not self._conn:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._cursor = self._conn.cursor()

    def _decode_string(self, data: bytes) -> str:
        s = ""
        for b in data:
            if b == 0xFF: break
            s += CHAR_MAP.get(b, "?")
        return s

    def decode_pokemon(self, data: bytes) -> Optional[PlayerPokemon]:
        if len(data) != POKEMON_SIZE_BYTES:
            print(f"Error: Invalid data length {len(data)}")
            return None

        # 1. Personality & OT (First 8 bytes)
        pid = struct.unpack('<I', data[0:4])[0]
        ot_id = struct.unpack('<I', data[4:8])[0]
        
        # 2. Nickname (10 bytes)
        nickname_bytes = data[8:18]
        nickname = self._decode_string(nickname_bytes)
        
        # 3. Data Substructures (48 bytes, offset 32)
        # Encryption Key is PID ^ OTID
        key = pid ^ ot_id
        raw_sub = data[32:80]
        decrypted_sub = decrypt_data(raw_sub, key)
        
        # Verify Checksum
        checksum = struct.unpack('<H', data[28:30])[0]
        if not verify_checksum(decrypted_sub, checksum):
            # Checksum failed implies Bad Egg or Empty Slot
            # But for empty slots, PID is usually 0.
            if pid == 0: return None
            # print(f"Warning: Checksum failed for PID {pid:X}")
        
        ordered_data = unshuffle_substructures(decrypted_sub, pid)
        
        # 4. Parse Blocks (Growth, Attacks, EVs, Misc)
        # Growth (Block 0)
        species_id = struct.unpack('<H', ordered_data[0:2])[0]
        item_id = struct.unpack('<H', ordered_data[2:4])[0]
        xp = struct.unpack('<I', ordered_data[4:8])[0]
        
        # Attacks (Block 1) - 4 Moves * 2 bytes
        move_ids = struct.unpack('<HHHH', ordered_data[12:20])
        pp_bonuses = ordered_data[20]
        
        # EVs (Block 2)
        evs = struct.unpack('<BBBBBB', ordered_data[24:30]) # HP, Atk, Def, Spd, SpAtk, SpDef
        
        # Misc (Block 3)
        iv_egg_ability = struct.unpack('<I', ordered_data[36:40])[0]
        # IVs parsing omitted for brevity (bit shifting)
        
        # 5. Status & Stats (Last 20 bytes, UNENCRYPTED)
        level = data[84]
        current_hp = struct.unpack('<H', data[86:88])[0]
        max_hp = struct.unpack('<H', data[88:90])[0]
        atk = struct.unpack('<H', data[90:92])[0]
        def_ = struct.unpack('<H', data[92:94])[0]
        spd = struct.unpack('<H', data[94:96])[0]
        sp_atk = struct.unpack('<H', data[96:98])[0]
        sp_def = struct.unpack('<H', data[98:100])[0]

        # 6. Enlighten with DB
        self._connect_db()
        moves = []
        for m_id in move_ids:
            if m_id == 0: continue
            row = self._cursor.execute("SELECT * FROM moves WHERE id=?", (m_id,)).fetchone()
            if row:
                moves.append(Move(
                    move_id=m_id,
                    name=row['name'],
                    type_id=0, # TODO: Map Type string to int
                    base_power=row['power'],
                    accuracy=row['accuracy'],
                    current_pp=10, # Placeholder, need to parse PP byte
                    max_pp=row['pp']
                ))

        return PlayerPokemon(
            species_id=species_id,
            level=level,
            nickname=nickname,
            item_id=item_id,
            hp=max_hp, attack=atk, defense=def_, sp_attack=sp_atk, sp_defense=sp_def, speed=spd,
            current_hp=current_hp,
            moves=moves
        )
