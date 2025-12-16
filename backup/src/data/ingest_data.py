import sqlite3
import re
import os
import sys

# Paths to raw data files
DATA_DIR = os.path.join(os.path.dirname(__file__), 'raw')
DB_PATH = os.path.join(os.path.dirname(__file__), 'knowledge_base.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def load_constants(filename):
    """Parses a C header file for #define constants."""
    constants = {}
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
         print(f"Warning: {filename} not found.")
         return constants

    with open(path, 'r') as f:
        for line in f:
            match = re.match(r'#define\s+(\w+)\s+(\d+)', line)
            if match:
                key, value = match.groups()
                constants[key] = int(value)
            
            # Handle Hex values
            match_hex = re.match(r'#define\s+(\w+)\s+(0x[0-9A-Fa-f]+)', line)
            if match_hex:
                 key, value = match_hex.groups()
                 constants[key] = int(value, 16)

    return constants

def parse_species_info(constants):
    """Parses species_info.h to extract Pokemon stats."""
    species = []
    path = os.path.join(DATA_DIR, 'species_info.h')
    
    with open(path, 'r') as f:
        content = f.read()

    # Matches [SPECIES_NAME] = { ... } blocks
    # We use a non-greedy dot match to capture the struct body
    pattern = re.compile(r'\[(SPECIES_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)
    
    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        if identifier == "SPECIES_NONE":
             continue
        
        # Get ID from constants
        species_id = constants.get(identifier)
        if species_id is None:
            continue

        # Extract Name (Infer from identifier)
        name = identifier.replace('SPECIES_', '').replace('_', ' ').title()
        
        # Helper to extract integer fields
        def get_int(key):
             m = re.search(fr'\.{key}\s*=\s*(\d+)', body)
             return int(m.group(1)) if m else 0
        
        # Extract Types
        types_match = re.search(r'\.types\s*=\s*\{\s*(TYPE_\w+)\s*,\s*(TYPE_\w+)\s*\}', body)
        type1 = types_match.group(1).replace('TYPE_', '').title() if types_match else 'Normal'
        type2 = types_match.group(2).replace('TYPE_', '').title() if types_match else 'Normal'

        # Extract Abilities
        # .abilities = {ABILITY_OVERGROW, ABILITY_NONE},
        abilities_match = re.search(r'\.abilities\s*=\s*\{\s*(ABILITY_\w+)\s*,\s*(ABILITY_\w+)\s*\}', body)
        abi1 = abilities_match.group(1) if abilities_match else None
        abi2 = abilities_match.group(2) if abilities_match else None

        data = {
            'id': species_id,
            'identifier': identifier,
            'name': name,
            'type1': type1,
            'type2': type2,
            'base_hp': get_int('baseHP'),
            'base_atk': get_int('baseAttack'),
            'base_def': get_int('baseDefense'),
            'base_sp_atk': get_int('baseSpAttack'),
            'base_sp_def': get_int('baseSpDefense'),
            'base_speed': get_int('baseSpeed'),
            'ability1': abi1,
            'ability2': abi2
        }
        species.append(data)
        
    return species

def parse_moves(constants):
    """Parses battle_moves.h."""
    moves = []
    path = os.path.join(DATA_DIR, 'battle_moves.h')
    
    with open(path, 'r') as f:
         content = f.read()

    pattern = re.compile(r'\[(MOVE_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)

    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        if identifier == "MOVE_NONE": 
            continue

        move_id = constants.get(identifier)
        if move_id is None:
             continue
        
        name = identifier.replace('MOVE_', '').replace('_', ' ').title()
        
        def get_val(key):
            m = re.search(fr'\.{key}\s*=\s*(\w+)', body)
            return m.group(1) if m else None
        
        # Special handling for Type (it's a constant name like TYPE_NORMAL)
        type_str = get_val('type')
        if type_str:
             type_str = type_str.replace('TYPE_', '').title()
        
        data = {
            'id': move_id,
            'identifier': identifier,
            'name': name,
            'type': type_str,
            'power': int(get_val('power') or 0),
            'accuracy': int(get_val('accuracy') or 0),
            'pp': int(get_val('pp') or 0),
            'effect': get_val('effect')
        }
        moves.append(data)
    
    return moves

def parse_items(constants):
    """Parses items.h."""
    items = []
    path = os.path.join(DATA_DIR, 'items.h')
    
    with open(path, 'r') as f:
         content = f.read()

    pattern = re.compile(r'\[(ITEM_\w+)\]\s*=\s*\{(.*?)\},', re.DOTALL)

    for match in pattern.finditer(content):
        identifier = match.group(1)
        body = match.group(2)
        
        item_id = constants.get(identifier)
        if item_id is None:
             continue
             
        # Extract Name from .name = _("TEXT")
        name_match = re.search(r'\.name\s*=\s*_\("(.*?)"\)', body)
        name = name_match.group(1) if name_match else identifier
        
        desc_match = re.search(r'\.description\s*=\s*(\w+)', body)
        desc = desc_match.group(1) if desc_match else None

        data = {
            'id': item_id,
            'identifier': identifier,
            'name': name,
            'description': desc
        }
        items.append(data)
        
    return items

def parse_frontier_mons(constants, species_map, moves_map, items_map, nature_map):
    """Parses battle_frontier_mons.h."""
    mons = []
    path = os.path.join(DATA_DIR, 'battle_frontier_mons.h')
    
    with open(path, 'r') as f:
         lines = f.readlines()
         
    current_mon_id = 0
    current_body_lines = []
    in_mon = False
    
    # Simple state machine to handle nested braces
    for line in lines:
        match_start = re.match(r'\s*\[(FRONTIER_MON_\w+)\]\s*=\s*\{', line)
        if match_start:
            in_mon = True
            current_id_symbol = match_start.group(1)
            # Try to resolve ID, else use counter (fallback, though imperfect if gaps exist)
            # Since we traverse in order, counter is generally safe for contiguous arrays.
            if current_id_symbol in constants:
                 current_mon_id = constants[current_id_symbol]
            # else: keep current_mon_id as is (incremented from previous)
            
            current_body_lines = []
            continue
            
        if in_mon:
            # Check for end of struct: "    }," or just "},"
            # Be careful not to match "        .moves = { ... },"
            # The closing brace for the mon should be less indented or just look like "    },"
            if re.match(r'\s*\},', line):
                in_mon = False
                body = "".join(current_body_lines)
                
                def get_val(key):
                     m = re.search(fr'\.{key}\s*=\s*(\w+)', body)
                     return m.group(1) if m else None

                species = get_val('species')
                item = get_val('itemTableId')
                nature = get_val('nature')
                ev_spread = get_val('evSpread')

                # Moves
                moves_match = re.search(r'\.moves\s*=\s*\{(.*?)\}', body, re.DOTALL)
                moves = [0, 0, 0, 0]
                if moves_match:
                    move_strs = [m.strip() for m in moves_match.group(1).split(',')]
                    for i, m_str in enumerate(move_strs[:4]):
                        moves[i] = moves_map.get(m_str, 0)

                item_const = item.replace('BATTLE_FRONTIER_ITEM_', 'ITEM_') if item else 'ITEM_NONE'
                item_id = items_map.get(item_const, 0)
                
                data = {
                    'id': current_mon_id,
                    'species_id': species_map.get(species, 0),
                    'move1_id': moves[0],
                    'move2_id': moves[1],
                    'move3_id': moves[2],
                    'move4_id': moves[3],
                    'item_id': item_id,
                    'nature': nature.replace('NATURE_', '').title() if nature else 'Hardy',
                    'ev_spread': ev_spread or "0"
                }
                mons.append(data)
                current_mon_id += 1
            else:
                current_body_lines.append(line)
    
    return mons

def create_db_schema(cursor):
    """Executes schema.sql."""
    with open(SCHEMA_PATH, 'r') as f:
        cursor.executescript(f.read())

def get_type_efficacy():
    """Returns Gen 3 Type Chart (Attacker, Defender) -> Factor"""
    # 0 = Normal, 0.5 = Not effective, 1.0 = Normal, 2.0 = Super effective
    # 0.5 is represented as 0.5
    
    types = [
        'Normal', 'Fire', 'Water', 'Grass', 'Electric', 'Ice', 'Fighting', 'Poison', 
        'Ground', 'Flying', 'Psychic', 'Bug', 'Rock', 'Ghost', 'Dragon', 'Steel', 'Dark'
    ]
    
    # Init with 1.0
    chart = {}
    for t1 in types:
        for t2 in types:
            chart[(t1, t2)] = 1.0
            
    # Define exceptions (Super effective / Not effective / Immune)
    # This is a large list. I will implement a subset or the full standard table.
    # For brevity in this script, I'll add the most critical ones.
    # Ideally this should be complete.
    
    effs = [
        # Normal
        ('Normal', 'Rock', 0.5), ('Normal', 'Ghost', 0.0), ('Normal', 'Steel', 0.5),
        # Fire
        ('Fire', 'Fire', 0.5), ('Fire', 'Water', 0.5), ('Fire', 'Grass', 2.0), ('Fire', 'Ice', 2.0),
        ('Fire', 'Bug', 2.0), ('Fire', 'Rock', 0.5), ('Fire', 'Dragon', 0.5), ('Fire', 'Steel', 2.0),
        # Water
        ('Water', 'Fire', 2.0), ('Water', 'Water', 0.5), ('Water', 'Grass', 0.5), ('Water', 'Ground', 2.0),
        ('Water', 'Rock', 2.0), ('Water', 'Dragon', 0.5),
        # Electric
        ('Electric', 'Water', 2.0), ('Electric', 'Electric', 0.5), ('Electric', 'Grass', 0.5),
        ('Electric', 'Ground', 0.0), ('Electric', 'Flying', 2.0), ('Electric', 'Dragon', 0.5),
        # Grass
        ('Grass', 'Fire', 0.5), ('Grass', 'Water', 2.0), ('Grass', 'Grass', 0.5), ('Grass', 'Poison', 0.5),
        ('Grass', 'Ground', 2.0), ('Grass', 'Flying', 0.5), ('Grass', 'Bug', 0.5), ('Grass', 'Rock', 2.0),
        ('Grass', 'Dragon', 0.5), ('Grass', 'Steel', 0.5),
        # Ice
        ('Ice', 'Fire', 0.5), ('Ice', 'Water', 0.5), ('Ice', 'Grass', 2.0), ('Ice', 'Ice', 0.5),
        ('Ice', 'Ground', 2.0), ('Ice', 'Flying', 2.0), ('Ice', 'Dragon', 2.0), ('Ice', 'Steel', 0.5),
        # Fighting
        ('Fighting', 'Normal', 2.0), ('Fighting', 'Ice', 2.0), ('Fighting', 'Poison', 0.5),
        ('Fighting', 'Flying', 0.5), ('Fighting', 'Psychic', 0.5), ('Fighting', 'Bug', 0.5),
        ('Fighting', 'Rock', 2.0), ('Fighting', 'Ghost', 0.0), ('Fighting', 'Dark', 2.0), ('Fighting', 'Steel', 2.0),
        # Poison
        ('Poison', 'Grass', 2.0), ('Poison', 'Poison', 0.5), ('Poison', 'Ground', 0.5), ('Poison', 'Rock', 0.5),
        ('Poison', 'Ghost', 0.5), ('Poison', 'Steel', 0.0),
        # Ground
        ('Ground', 'Fire', 2.0), ('Ground', 'Electric', 2.0), ('Ground', 'Grass', 0.5), ('Ground', 'Poison', 2.0),
        ('Ground', 'Flying', 0.0), ('Ground', 'Bug', 0.5), ('Ground', 'Rock', 2.0), ('Ground', 'Steel', 2.0),
        # Flying
        ('Flying', 'Electric', 0.5), ('Flying', 'Grass', 2.0), ('Flying', 'Fighting', 2.0), 
        ('Flying', 'Bug', 2.0), ('Flying', 'Rock', 0.5), ('Flying', 'Steel', 0.5),
        # Psychic
        ('Psychic', 'Fighting', 2.0), ('Psychic', 'Poison', 2.0), ('Psychic', 'Psychic', 0.5), 
        ('Psychic', 'Dark', 0.0), ('Psychic', 'Steel', 0.5),
        # Bug
        ('Bug', 'Fire', 0.5), ('Bug', 'Grass', 2.0), ('Bug', 'Fighting', 0.5), ('Bug', 'Poison', 0.5),
        ('Bug', 'Flying', 0.5), ('Bug', 'Psychic', 2.0), ('Bug', 'Ghost', 0.5), ('Bug', 'Dark', 2.0),
        ('Bug', 'Steel', 0.5),
        # Rock
        ('Rock', 'Fire', 2.0), ('Rock', 'Ice', 2.0), ('Rock', 'Fighting', 0.5), ('Rock', 'Ground', 0.5),
        ('Rock', 'Flying', 2.0), ('Rock', 'Bug', 2.0), ('Rock', 'Steel', 0.5),
        # Ghost
        ('Ghost', 'Normal', 0.0), ('Ghost', 'Psychic', 2.0), ('Ghost', 'Ghost', 2.0), ('Ghost', 'Dark', 0.5),
        ('Ghost', 'Steel', 0.5),
        # Dragon
        ('Dragon', 'Dragon', 2.0), ('Dragon', 'Steel', 0.5),
        # Steel
        ('Steel', 'Fire', 0.5), ('Steel', 'Water', 0.5), ('Steel', 'Electric', 0.5), ('Steel', 'Ice', 2.0),
        ('Steel', 'Rock', 2.0), ('Steel', 'Steel', 0.5),
        # Dark
        ('Dark', 'Fighting', 0.5), ('Dark', 'Psychic', 2.0), ('Dark', 'Ghost', 2.0), ('Dark', 'Dark', 0.5),
        ('Dark', 'Steel', 0.5)
    ]
    
    for atk, defe, factor in effs:
        if (atk in types) and (defe in types):
             chart[(atk, defe)] = factor
             
    return chart

def main():
    if not os.path.exists(DB_PATH):
        # Create new DB
        pass
    else:
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    create_db_schema(cursor)
    
    print("Parsing Constants...")
    species_const = load_constants('species_constants.h')
    moves_const = load_constants('moves_constants.h')
    items_const = load_constants('item_constants.h')
    # frontier_const = load_constants('battle_frontier_mons_constants.h') # Optional
    
    print(f"Loaded {len(species_const)} species, {len(moves_const)} moves, {len(items_const)} items.")
    
    print("Parsing Data Structures...")
    species_data = parse_species_info(species_const)
    moves_data = parse_moves(moves_const)
    items_data = parse_items(items_const)
    
    # Invert maps for lookups by identifier
    species_map = {s['identifier']: s['id'] for s in species_data}
    moves_map = {m['identifier']: m['id'] for m in moves_data}
    items_map = {i['identifier']: i['id'] for i in items_data}
    
    frontier_data = parse_frontier_mons(species_const, species_map, moves_map, items_map, None)
    
    print(f"Parsed {len(species_data)} species info entries.")
    print(f"Parsed {len(moves_data)} moves.")
    print(f"Parsed {len(items_data)} items.")
    print(f"Parsed {len(frontier_data)} frontier mons.")
    
    print("Populating Database...")
    
    # Species
    cursor.executemany('''
        INSERT OR IGNORE INTO species (id, identifier, name, type1, type2, base_hp, base_atk, base_def, base_sp_atk, base_sp_def, base_speed, ability1, ability2)
        VALUES (:id, :identifier, :name, :type1, :type2, :base_hp, :base_atk, :base_def, :base_sp_atk, :base_sp_def, :base_speed, :ability1, :ability2)
    ''', species_data)
    
    # Moves
    cursor.executemany('''
        INSERT OR IGNORE INTO moves (id, identifier, name, type, power, accuracy, pp, effect)
        VALUES (:id, :identifier, :name, :type, :power, :accuracy, :pp, :effect)
    ''', moves_data)
    
    # Items
    cursor.executemany('''
        INSERT OR IGNORE INTO items (id, identifier, name, description)
        VALUES (:id, :identifier, :name, :description)
    ''', items_data)
    
    # Frontier Mons
    cursor.executemany('''
        INSERT INTO battle_frontier_mons (id, species_id, move1_id, move2_id, move3_id, move4_id, item_id, nature, ev_spread)
        VALUES (:id, :species_id, :move1_id, :move2_id, :move3_id, :move4_id, :item_id, :nature, :ev_spread)
    ''', frontier_data)
    
    # Type Efficacy
    chart = get_type_efficacy()
    chart_data = [{'attacker_type': k[0], 'defender_type': k[1], 'damage_factor': v} for k, v in chart.items()]
    cursor.executemany('''
        INSERT INTO type_efficacy (attacker_type, defender_type, damage_factor)
        VALUES (:attacker_type, :defender_type, :damage_factor)
    ''', chart_data)
    
    conn.commit()
    conn.close()
    print("Database population complete.")

if __name__ == '__main__':
    main()
