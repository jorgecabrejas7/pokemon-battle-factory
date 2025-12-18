import sqlite3
import re
import os
import sys
from typing import Dict, List, Tuple

"""
Battle Frontier Pokémon Seeder.

This script parses the `battle_frontier_mons.h` file to populate the 
`battle_frontier_mons` table in the database. 

It now performs deep parsing to resolve:
- Species IDs
- Move IDs (up to 4)
- Item IDs (heuristically mapping BATTLE_FRONTIER_ITEM_ -> ITEM_)
- Nature (String name)
- EV Spread (Bitmask integer)
"""

DB_PATH = "src/data/knowledge_base.db"
RAW_DIR = "data/raw"

FILES = {
    "frontier_mons": os.path.join(RAW_DIR, "battle_frontier_mons.h"),
    "frontier_consts": os.path.join(RAW_DIR, "battle_frontier_mons_constants.h"),
    "bf_consts": os.path.join(RAW_DIR, "battle_frontier_constants.h"),
    "species_consts": os.path.join(RAW_DIR, "species_constants.h"),
    "moves_consts": os.path.join(RAW_DIR, "moves_constants.h"),
    "item_consts": os.path.join(RAW_DIR, "item_constants.h"),
    "poke_consts": os.path.join(RAW_DIR, "pokemon_constants.h")
}

def load_defines(path: str, prefix: str = "") -> Dict[str, int]:
    """Parses #define CONSTANT val."""
    mapping = {}
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return {}
        
    with open(path, 'r') as f:
        for line in f:
            # Match #define NAME value. value can be hex 0x...
            match = re.match(r'#define\s+(\w+)\s+((?:0x[0-9A-Fa-f]+)|\d+)', line)
            if match:
                key, val = match.groups()
                if prefix and not key.startswith(prefix):
                    continue
                mapping[key] = int(val, 0) # 0 handles 0x prefix auto-detection
    return mapping

def resolve_item_map(bf_items: Dict[str, int], real_items: Dict[str, int]) -> Dict[int, int]:
    """Maps Battle Frontier Item Constants (Values) -> Real Item IDs."""
    # Logic: BATTLE_FRONTIER_ITEM_X -> ITEM_X
    mapping = {}
    
    # Reverse map real items for name lookup if needed, checking keys directly is easier
    # items_by_name: ITEM_X -> ID
    
    for bf_key, bf_val in bf_items.items():
        if not bf_key.startswith("BATTLE_FRONTIER_ITEM_"):
            continue
            
        suffix = bf_key.replace("BATTLE_FRONTIER_ITEM_", "")
        real_key = f"ITEM_{suffix}"
        
        if real_key in real_items:
            mapping[bf_val] = real_items[real_key]
        elif suffix == "NONE":
            mapping[bf_val] = 0
        else:
            # print(f"Warning: Could not map {bf_key} -> {real_key}")
            mapping[bf_val] = 0
            
    return mapping

def parse_nature_name(nature_const: str) -> str:
    # NATURE_HARDY -> Hardy
    return nature_const.replace("NATURE_", "").title()

def seed_facility_mons():
    print("Loading constants...")
    
    species_map = load_defines(FILES["species_consts"], "SPECIES_")
    move_map = load_defines(FILES["moves_consts"], "MOVE_")
    item_map = load_defines(FILES["item_consts"], "ITEM_")
    
    frontier_mon_ids = load_defines(FILES["frontier_consts"], "FRONTIER_MON_")
    
    # BF Item Defines: BATTLE_FRONTIER_ITEM_X -> Val
    bf_item_defines = load_defines(FILES["bf_consts"], "BATTLE_FRONTIER_ITEM_")
    
    # Resolve Item IDs
    # Map: BF_ITEM_VALUE -> GAME_ITEM_ID
    item_resolver = resolve_item_map(bf_item_defines, item_map)
    print(f"Resolved {len(item_resolver)} item mappings.")
    print(f"Loaded {len(move_map)} moves from constants.")

    print("Parsing mons file...")
    with open(FILES["frontier_mons"], 'r') as f:
        content = f.read()

    # Robust parsing: Split by "[FRONTIER_MON_"
    # The file starts with "const struct ... = {" so the first split might be garbage or the start.
    chunks = content.split("[FRONTIER_MON_")
    
    data_list = []
    
    count = 0
    # Skip the first chunk as it contains preamble
    for chunk in chunks[1:]:
        # format: "NAME] = {\n ... body ... \n    },\n    ..."
        # Extract name
        end_of_name = chunk.find("]")
        if end_of_name == -1: continue
        
        f_mon_suffix = chunk[:end_of_name]
        f_mon_key = f"FRONTIER_MON_{f_mon_suffix}"
        
        body = chunk[end_of_name:] # Everything after name
        
        if f_mon_key not in frontier_mon_ids:
            continue
            
        f_id = frontier_mon_ids[f_mon_key]
        
        # Defaults
        species_id = 0
        moves = [0, 0, 0, 0]
        item_id = 0
        nature = "Hardy"
        
        # 1. Species
        m_spec = re.search(r'\.species\s*=\s*(SPECIES_\w+)', body)
        if m_spec:
            s_key = m_spec.group(1)
            species_id = species_map.get(s_key, 0)
            
        # 2. Moves
        # .moves = {MOVE_A, MOVE_B, ...}
        m_moves = re.search(r'\.moves\s*=\s*\{([^}]+)\}', body)
        if m_moves:
            raw_moves = m_moves.group(1).split(',')
            for i, rm in enumerate(raw_moves):
                rm = rm.strip()
                if i < 4:
                    moves[i] = move_map.get(rm, 0)
        
        # 3. Item
        # .itemTableId = BATTLE_FRONTIER_ITEM_X
        m_item = re.search(r'\.itemTableId\s*=\s*(BATTLE_FRONTIER_ITEM_\w+)', body)
        if m_item:
            bf_item_key = m_item.group(1)
            # Get the define value
            bf_val = bf_item_defines.get(bf_item_key, 0)
            # Resolve to real ID
            item_id = item_resolver.get(bf_val, 0)
            
        # 4. Nature
        # .nature = NATURE_X
        m_nat = re.search(r'\.nature\s*=\s*(NATURE_\w+)', body)
        if m_nat:
            nature = parse_nature_name(m_nat.group(1))
            
        # 5. EV Spread
        # .evSpread = F_EV_SPREAD_SP_ATTACK | ...
        m_ev = re.search(r'\.evSpread\s*=\s*([^,]+),', body)
        ev_spread_str = "0"
        if m_ev:
            ev_spread_str = m_ev.group(1).strip()
        
        data_list.append({
            'id': f_id,
            'species_id': species_id,
            'move1': moves[0],
            'move2': moves[1],
            'move3': moves[2],
            'move4': moves[3],
            'item_id': item_id,
            'nature': nature,
            'ev_spread_str': ev_spread_str
        })
        count += 1

    # Resolve EV Spreads properly
    # Load F_EV constants
    ev_consts = load_defines(FILES["bf_consts"], "F_EV_SPREAD_")
    
    final_rows = []
    for row in data_list:
        ev_val = 0
        parts = [p.strip() for p in row['ev_spread_str'].split('|')]
        for p in parts:
            if p in ev_consts:
                ev_val |= ev_consts[p]
        
        final_rows.append((
            row['id'],
            row['species_id'],
            row['move1'],
            row['move2'],
            row['move3'],
            row['move4'],
            row['item_id'],
            row['nature'],
            ev_val
        ))

    print(f"Parsed {len(final_rows)} mons.")
    
    # DB Insert
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.executemany("""
        INSERT OR REPLACE INTO battle_frontier_mons 
        (id, species_id, move1_id, move2_id, move3_id, move4_id, item_id, nature, ev_spread)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, final_rows)
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    seed_facility_mons()
