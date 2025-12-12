import sys
import os
import struct
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backends.emerald.decoder import EmeraldDecoder
from src.backends.emerald.decryption import decrypt_data

def create_mock_pokemon_bytes():
    """
    Creates a valid 100-byte encrypted Pokemon structure.
    Target: Bulbasaur (Species 1), Level 5, Nickname "TEST"
    """
    # 1. Header (PID, OTID, Nick, Lang, OTName, Mark, Csum, Pad) -> 32 bytes
    pid = 0x12345678 # PID
    otid = 0x87654321 # OTID
    
    # Nickname "TEST"
    # T=0xCE, E=0xBF, S=0xCD, T=0xCE
    nick = b'\xCE\xBF\xCD\xCE\xFF\x00\x00\x00\x00\x00'
    
    # 2. Substructures (Growth, Attacks, EVs, Misc)
    # Block Order for PID 0x12345678 % 24 = 0 -> GAEM (0, 1, 2, 3)
    
    # Growth (Species 1, Item 0)
    growth = struct.pack('<HHII', 1, 0, 1000, 0) # Species, Item, XP, Pad
    
    # Attacks (Move 1: Pound=1)
    # 4 Moves (8 bytes), PP Bonus (1 byte), 3 bytes padding
    attacks = struct.pack('<HHHHBxxx', 1, 0, 0, 0, 0)
    assert len(attacks) == 12
    
    # EVs
    evs = b'\x00' * 12
    
    # Misc
    misc = b'\x00' * 12
    
    raw_sub = growth + attacks + evs + misc
    
    # Calculate Checksum (Sum of 16-bit words)
    checksum = 0
    for i in range(0, 48, 2):
        word = struct.unpack('<H', raw_sub[i:i+2])[0]
        checksum = (checksum + word) & 0xFFFF
        
    # Encrypt
    key = pid ^ otid
    encrypted_sub = decrypt_data(raw_sub, key) # XOR is symmetric
    
    # Header Construction
    header = struct.pack('<II', pid, otid) + nick + b'\x02\x02\x00\x00' # Lang=2 (Eng)
    
    # Insert Checksum at byte 28
    # 0-27 is 28 bytes. Header is 20 bytes (PID+OT+Nick+Lang+OTName..)
    # Structure:
    # 0-3: PID
    # 4-7: OTID
    # 8-17: Nick
    # 18-19: Lang
    # 20-26: OT Name (7 bytes)
    # 27: Markings
    # 28-29: Checksum
    # 30-31: Padding
    
    
    ot_name = b'\xC1\x00\x00\x00\x00\x00\x00' # "G"
    header_part = struct.pack('<II', pid, otid) + nick + struct.pack('<H', 0x0202) + ot_name + b'\x00'
    header_final = header_part + struct.pack('<H', checksum) + b'\x00\x00'
    
    # Header Calc:
    # 4 (PID) + 4 (OTID) + 10 (Nick) + 2 (Lang) + 7 (OTName) + 1 (Markings) + 2 (Checksum) + 2 (Pad) = 32 bytes
    # Current header_part: 4+4+10+2+7+1 = 28 bytes
    # header_final adds 2 (checksum) + 2 (pad) = 32 bytes.
    # Total so far: 32 bytes.
    
    # Substructs is 48 bytes.
    # Stats is 20 bytes.
    # Total = 32 + 48 + 20 = 100 bytes.
    
    # Let's verify what I did wrong before. 
    # Previous code:
    # header_part = ... + nick + struct.pack('<H', 0x0202) + ot_name + b'\x00'
    # 4+4 = 8. +10 = 18. +2 = 20. +7 = 27. +1 = 28. Correct.
    # header_final = header_part + struct.pack('<H', checksum) + b'\x00\x00'
    # 28 + 2 + 2 = 32. Correct.
    
    # Stats:
    # stats = struct.pack('<IBBHHHHHHH', 0, 5, 0, 20, 20, 10, 10, 10, 10, 10)
    # I (4) + B (1) + B (1) + 7*H (14) = 20 bytes. Correct.
    
    # Substructs:
    # raw_sub = growth + attacks + evs + misc
    # growth = 12. attacks = 12. evs=12. misc=12. Total 48. Correct.
    
    # Total should be 100.
    # Wait, the failure said 104.
    # Where did 4 bytes come from?
    
    # Ah, I added "header_part = ... + b'\x02\x02\x00\x00'" in the lines ABOVE the final assignment?
    # No, I see:
    # header = struct.pack('<II', pid, otid) + nick + b'\x02\x02\x00\x00' # Lang=2 (Eng)
    # Then I redefined header_part below it effectively ignoring 'header'.
    # But wait, looking at the file I wrote...
    
    # Let's check the previous file write content.
    # header = ...
    # ...
    # header_part = ...
    # header_final = header_part ...
    # total = header_final + encrypted_sub + stats 
    
    # Maybe I pasted a snippet that had 'header' variable unused but causing confusion?
    # No, 'header' variable is unused.
    # Let's look at Attacks struct. pack('<HHHHII', ...)
    # H(2)*4 = 8. I(4)*2 = 8. Total 16 bytes!
    # Attacks block should be 12 bytes.
    # struct SpeciesInfo is 12 bytes. 
    # Attacks substruct: 4 moves (2 bytes each) = 8 bytes. PP bonuses (1 byte). 3 bytes padding (usually).
    # Or 4 moves, pp bonus, and then... ?
    # Gen 3 Attack substruct:
    # Moves: 2*4 = 8
    # PP Bonuses: 1
    # Padding/IVs? No IVs are in Misc.
    # 3 bytes of padding/unused.
    # My pack string was '<HHHHII' -> 2*4 + 4*2 = 16 bytes. 
    # That explains +4 bytes! 
    
    # Fixed Attacks packing:
    
    # 3. Status/Stats (Unencrypted)
    # Level 5, HP 20, Atk 10...
    stats = struct.pack('<IBBHHHHHHH', 0, 5, 0, 20, 20, 10, 10, 10, 10, 10)
    
    total = header_final + encrypted_sub + stats
    return total

def test_decoder(tmp_path):
    # Setup Mock DB
    db_file = os.path.join(tmp_path, "knowledge_base.db")
    import sqlite3
    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE moves (id INTEGER, name TEXT, power INTEGER, accuracy INTEGER, pp INTEGER)")
    conn.execute("INSERT INTO moves VALUES (1, 'Pound', 40, 100, 35)")
    conn.commit()
    conn.close()
    
    decoder = EmeraldDecoder(db_path=str(db_file))
    
    data = create_mock_pokemon_bytes()
    print(f"DEBUG: Data Length: {len(data)}")
    assert len(data) == 100
    
    pokemon = decoder.decode_pokemon(data)
    
    assert pokemon is not None
    assert pokemon.species_id == 1 # Bulbasaur
    assert pokemon.nickname == "TEST"
    assert pokemon.level == 5
    assert len(pokemon.moves) >= 1
    assert pokemon.moves[0].name == "Pound"
    
    print("Decoder Test Passed!")

if __name__ == "__main__":
    import shutil
    # Manual run setup
    if os.path.exists("temp_test"):
        shutil.rmtree("temp_test")
    os.makedirs("temp_test", exist_ok=True)
    try:
        test_decoder("temp_test")
    finally:
        if os.path.exists("temp_test"):
            shutil.rmtree("temp_test")
