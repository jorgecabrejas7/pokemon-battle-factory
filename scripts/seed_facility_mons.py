import sqlite3
import re
import os

DB_PATH = "src/data/knowledge_base.db"
frontier_mons_h = "backup/src/data/raw/battle_frontier_mons.h"
frontier_consts_h = "backup/src/data/raw/battle_frontier_mons_constants.h"
species_consts_h = "backup/src/data/raw/species_constants.h"

def load_map(path, pattern):
    """Parses a header file with a regex pattern to build a name->id map."""
    mapping = {}
    with open(path, 'r') as f:
        for line in f:
            match = re.search(pattern, line)
            if match:
                name = match.group(1)
                val = int(match.group(2))
                mapping[name] = val
    return mapping

def seed_facility_mons():
    # 1. Load Constants Maps
    print("Loading constants...")
    species_map = load_map(species_consts_h, r'#define\s+(SPECIES_\w+)\s+(\d+)')
    frontier_idx_map = load_map(frontier_consts_h, r'#define\s+(FRONTIER_MON_\w+)\s+(\d+)')
    
    print(f"Loaded {len(species_map)} species constants.")
    print(f"Loaded {len(frontier_idx_map)} frontier mon constants.")
    
    # 2. Parse Data File
    # Format: [FRONTIER_MON_NAME] = { .species = SPECIES_NAME, ... }
    # We will read the file and look for occurrences.
    # Since it's multi-line, we can read the whole file content.
    with open(frontier_mons_h, 'r') as f:
        content = f.read()
    
    # Regex to find blocks. Note: The content has newlines.
    # We look for [FRONTIER_MON_...] ... .species = SPECIES_...
    # This is a bit fragile with regex but should work for this C struct.
    
    # Pattern: [FRONTIER_MON_NAME] ... .species = SPECIES_NAME
    matches = re.findall(r'\[(FRONTIER_MON_\w+)\]\s*=\s*{[^}]*\.species\s*=\s*(SPECIES_\w+)', content, re.DOTALL)
    
    print(f"Found {len(matches)} matches in battle_frontier_mons.h")
    
    data_to_insert = []
    
    for f_mon_name, s_name in matches:
        if f_mon_name not in frontier_idx_map:
            print(f"Warning: Unknown frontier mon constant {f_mon_name}")
            continue
        if s_name not in species_map:
            print(f"Warning: Unknown species constant {s_name}")
            # Try removing _1, _2 suffixes if they exist in species map? 
            # No, usually SPECIES_NAME is standard.
            continue
            
        f_id = frontier_idx_map[f_mon_name]
        s_id = species_map[s_name]
        
        # We only have species_id for now. 
        # We fill other required columns with dummy 0 values or defaults to satisfy NOT NULL constraints if any.
        # Schema: id, species_id, move1..4, item, nature, ev.
        # We'll set moves/item to 0 for now.
        data_to_insert.append((f_id, s_id, 0, 0, 0, 0, 0, "Hardy", 0))

    if not data_to_insert:
        print("No data parsed. Exiting.")
        return

    # 3. Insert into DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Inserting {len(data_to_insert)} records...")
    cursor.executemany("""
        INSERT OR REPLACE INTO battle_frontier_mons 
        (id, species_id, move1_id, move2_id, move3_id, move4_id, item_id, nature, ev_spread)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_to_insert)
    
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    seed_facility_mons()
