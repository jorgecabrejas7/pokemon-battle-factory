import re
import sqlite3
import os
import sys

"""
Data Ingestion Script for Pokémon Battle Factory Knowledge Base.

This script parses raw C header files (from the decompilation project) relating to
Moves, Species, and Items, and populates the SQLite `knowledge_base.db`.

It handles:
1. Database schema creation/reset.
2. Parsing `moves_constants.h`, `battle_moves.h` for Move data.
3. Parsing `species_constants.h`, `species_info.h` for Pokémon stats and types.
4. Parsing `item_constants.h`, `items.h` for Item data.

Usage:
    python3 scripts/ingest_data.py
"""

# Constants
DB_PATH = "src/data/knowledge_base.db"
RAW_DATA_PATH = "data/raw"

def setup_database(conn: sqlite3.Connection) -> None:
    """Initializes the SQLite database schema.

    Drops existing tables and recreates them with proper constraints/Foreign Keys.

    Args:
        conn (sqlite3.Connection): Active database connection.
    """
    cursor = conn.cursor()
    
    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Drop existing tables to ensure fresh schema
    cursor.execute("DROP TABLE IF EXISTS battle_frontier_mons;")
    cursor.execute("DROP TABLE IF EXISTS moves;")
    cursor.execute("DROP TABLE IF EXISTS species;")
    cursor.execute("DROP TABLE IF EXISTS items;")

    # Create Tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS species (
        id INTEGER PRIMARY KEY,
        identifier TEXT NOT NULL,
        name TEXT NOT NULL,
        type1 TEXT NOT NULL,
        type2 TEXT NOT NULL,
        base_hp INTEGER NOT NULL,
        base_atk INTEGER NOT NULL,
        base_def INTEGER NOT NULL,
        base_sp_atk INTEGER NOT NULL,
        base_sp_def INTEGER NOT NULL,
        base_speed INTEGER NOT NULL,
        ability1 TEXT,
        ability2 TEXT,
        UNIQUE(identifier)
    );""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS moves (
        id INTEGER PRIMARY KEY,
        identifier TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        power INTEGER NOT NULL,
        accuracy INTEGER NOT NULL,
        pp INTEGER NOT NULL,
        effect TEXT NOT NULL,
        target TEXT,
        priority INTEGER,
        flags TEXT,
        secondary_effect_chance INTEGER,
        split TEXT,
        UNIQUE(identifier)
    );""")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY,
        identifier TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        hold_effect TEXT,
        hold_effect_param INTEGER,
        price INTEGER,
        UNIQUE(identifier)
    );""")
    
    # Re-create battle_frontier_mons as it depends on others
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battle_frontier_mons (
        id INTEGER PRIMARY KEY,
        species_id INTEGER NOT NULL,
        move1_id INTEGER NOT NULL,
        move2_id INTEGER NOT NULL,
        move3_id INTEGER NOT NULL,
        move4_id INTEGER NOT NULL,
        item_id INTEGER NOT NULL,
        nature TEXT NOT NULL,
        ev_spread INTEGER NOT NULL,
        FOREIGN KEY(species_id) REFERENCES species(id),
        FOREIGN KEY(move1_id) REFERENCES moves(id),
        FOREIGN KEY(move2_id) REFERENCES moves(id),
        FOREIGN KEY(move3_id) REFERENCES moves(id),
        FOREIGN KEY(move4_id) REFERENCES moves(id),
        FOREIGN KEY(item_id) REFERENCES items(id)
    );""")

    conn.commit()
    print("Database schema initialized.")

def parse_value(line: str, key: str) -> str:
    """Helper to extract value after = in a struct definition line."""
    match = re.search(fr"\.{key}\s*=\s*([^,]+),", line)
    if match:
        val = match.group(1).strip()
        # Remove comments if any
        val = re.sub(r'//.*', '', val).strip()
        return val
    return None


def parse_constants(filename: str) -> dict:
    """Parses a C header file for #define CONSTANT_NAME ID mappings."""
    filepath = os.path.join(RAW_DATA_PATH, filename)
    mapping = {}
    with open(filepath, 'r') as f:
        for line in f:
            # #define MOVE_POUND 1
            match = re.match(r'#define\s+(\w+)\s+(\d+)', line)
            if match:
                key, val = match.groups()
                mapping[key] = int(val)
            # Handle hex? #define FLAG 0x1
            match_hex = re.match(r'#define\s+(\w+)\s+(0x[0-9A-Fa-f]+)', line)
            if match_hex:
                 key, val = match_hex.groups()
                 mapping[key] = int(val, 16)
    return mapping

def ingest_moves(conn: sqlite3.Connection) -> None:
    """Reads `battle_moves.h` and populates the `moves` table."""
    print("Ingesting Moves...")
    cursor = conn.cursor()
    
    # 1. Load Constants
    move_ids = parse_constants("moves_constants.h")
    
    filepath = os.path.join(RAW_DATA_PATH, "battle_moves.h")
    with open(filepath, 'r') as f:
        content = f.read()

    pattern = re.compile(r'\[(MOVE_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)
    
    moves_processed = 0
    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        move_id = move_ids.get(identifier)
        if move_id is None:
            # Maybe it is MOVE_NONE or not in constants?
            if identifier == "MOVE_NONE": move_id = 0
            else:
                print(f"Warning: ID not found for {identifier}")
                continue

        # Defaults
        name = identifier.replace("MOVE_", "").replace("_", " ").title()
        power = 0
        accuracy = 0
        pp = 0
        effect = ""
        target = "MOVE_TARGET_SELECTED"
        priority = 0
        flags = ""
        sec_chance = 0
        move_type = "TYPE_NORMAL"
        
        # Parse fields
        for line in body.split('\n'):
            line = line.strip()
            if not line: continue
            
            if line.startswith('.power'):
                power = int(parse_value(line, 'power') or 0)
            elif line.startswith('.accuracy'):
                accuracy = int(parse_value(line, 'accuracy') or 0)
            elif line.startswith('.pp'):
                pp = int(parse_value(line, 'pp') or 0)
            elif line.startswith('.effect'):
                effect = parse_value(line, 'effect')
            elif line.startswith('.target'):
                target = parse_value(line, 'target')
            elif line.startswith('.priority'):
                priority = int(parse_value(line, 'priority') or 0)
            elif line.startswith('.secondaryEffectChance'):
                sec_chance = int(parse_value(line, 'secondaryEffectChance') or 0)
            elif line.startswith('.type'):
                move_type = parse_value(line, 'type')
            elif line.startswith('.flags'):
                flags_val = parse_value(line, 'flags')
                if flags_val:
                    flags = flags_val
        
        # Determine Split (Physical/Special) based on Type for Gen 3
        special_types = [
            "TYPE_FIRE", "TYPE_WATER", "TYPE_GRASS", "TYPE_ELECTRIC", 
            "TYPE_ICE", "TYPE_PSYCHIC", "TYPE_DRAGON", "TYPE_DARK"
        ]
        split = "Special" if move_type in special_types else "Physical"
        if move_type == "TYPE_MYSTERY": split = "Physical"
        
        clean_type = move_type.replace("TYPE_", "").title()

        cursor.execute("""
            INSERT OR REPLACE INTO moves 
            (id, identifier, name, type, power, accuracy, pp, effect, target, priority, flags, secondary_effect_chance, split)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (move_id, identifier, name, clean_type, power, accuracy, pp, effect, target, priority, flags, sec_chance, split))
        moves_processed += 1

    conn.commit()
    print(f"Processed {moves_processed} moves.")

def ingest_species(conn: sqlite3.Connection) -> None:
    """Reads `species_info.h` and populates the `species` table."""
    print("Ingesting Species...")
    cursor = conn.cursor()
    
    species_ids = parse_constants("species_constants.h")
    
    filepath = os.path.join(RAW_DATA_PATH, "species_info.h")
    with open(filepath, 'r') as f:
        content = f.read()

    pattern = re.compile(r'\[(SPECIES_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)
    
    species_processed = 0
    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        species_id = species_ids.get(identifier)
        if species_id is None:
            if identifier == "SPECIES_NONE": species_id = 0
            else: continue

        name = identifier.replace("SPECIES_", "").replace("_", " ").title()
        hp = atk = defense = sp_atk = sp_def = speed = 0
        type1 = type2 = "TYPE_NORMAL"
        ability1 = ability2 = "ABILITY_NONE"
        
        # Parse
        types_match = re.search(r'\.types\s*=\s*\{\s*(TYPE_\w+)\s*,\s*(TYPE_\w+)\s*\}', body)
        if types_match:
            type1 = types_match.group(1)
            type2 = types_match.group(2)
        
        abilities_match = re.search(r'\.abilities\s*=\s*\{\s*(ABILITY_\w+)\s*,\s*(ABILITY_\w+)\s*\}', body)
        if abilities_match:
            ability1 = abilities_match.group(1)
            ability2 = abilities_match.group(2)

        for line in body.split('\n'):
            line = line.strip()
            if '.baseHP' in line: hp = int(parse_value(line, 'baseHP') or 0)
            if '.baseAttack' in line: atk = int(parse_value(line, 'baseAttack') or 0)
            if '.baseDefense' in line: defense = int(parse_value(line, 'baseDefense') or 0)
            if '.baseSpeed' in line: speed = int(parse_value(line, 'baseSpeed') or 0)
            if '.baseSpAttack' in line: sp_atk = int(parse_value(line, 'baseSpAttack') or 0)
            if '.baseSpDefense' in line: sp_def = int(parse_value(line, 'baseSpDefense') or 0)

        clean_t1 = type1.replace("TYPE_", "").title()
        clean_t2 = type2.replace("TYPE_", "").title()
        
        cursor.execute("""
            INSERT OR REPLACE INTO species
            (id, identifier, name, type1, type2, base_hp, base_atk, base_def, base_sp_atk, base_sp_def, base_speed, ability1, ability2)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (species_id, identifier, name, clean_t1, clean_t2, hp, atk, defense, sp_atk, sp_def, speed, ability1, ability2))
        species_processed += 1

    conn.commit()
    print(f"Processed {species_processed} species.")

def ingest_items(conn: sqlite3.Connection) -> None:
    """Reads `items.h` and populates the `items` table."""
    print("Ingesting Items...")
    cursor = conn.cursor()
    
    item_ids = parse_constants("item_constants.h")
    
    filepath = os.path.join(RAW_DATA_PATH, "items.h")
    with open(filepath, 'r') as f:
        content = f.read()

    pattern = re.compile(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)
    
    items_processed = 0
    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        item_id = item_ids.get(identifier)
        if item_id is None:
             if identifier == "ITEM_NONE": item_id = 0
             else: continue # Skip if no ID found (might be special or alias)
        
        name = identifier.replace("ITEM_", "").replace("_", " ").title()
        desc = ""
        hold_effect = ""
        hold_param = 0
        price = 0
        
        for line in body.split('\n'):
            line = line.strip()
            if '.name' in line: 
                m = re.search(r'\.name\s*=\s*_\("([^"]+)"\)', line)
                if m: name = m.group(1)
            if '.price' in line: price = int(parse_value(line, 'price') or 0)
            if '.holdEffect' in line and 'holdEffectParam' not in line: 
                 hold_effect = parse_value(line, 'holdEffect')
            if '.holdEffectParam' in line:
                 hold_param = int(parse_value(line, 'holdEffectParam') or 0)
        
        cursor.execute("""
            INSERT OR REPLACE INTO items
            (id, identifier, name, description, hold_effect, hold_effect_param, price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (item_id, identifier, name, desc, hold_effect, hold_param, price))
        items_processed += 1

    conn.commit()
    print(f"Processed {items_processed} items.")


def main():
    if not os.path.exists(DB_PATH):
        # Ensure dir exists
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        setup_database(conn)
        ingest_moves(conn)
        ingest_species(conn)
        ingest_items(conn)
        
        print("Done.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
