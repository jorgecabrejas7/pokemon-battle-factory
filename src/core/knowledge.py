"""
Knowledge Base queries for Battle Frontier Pokemon data.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'knowledge_base.db')

def get_frontier_mon(mon_id: int) -> dict:
    """
    Get a Battle Frontier Pokemon by its ID.
    Returns a dict with species, moves, item, nature, ev_spread.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get the frontier mon
    cursor.execute('''
        SELECT 
            bfm.id,
            bfm.species_id,
            s.name as species_name,
            bfm.move1_id,
            bfm.move2_id,
            bfm.move3_id,
            bfm.move4_id,
            bfm.item_id,
            bfm.nature,
            bfm.ev_spread
        FROM battle_frontier_mons bfm
        LEFT JOIN species s ON bfm.species_id = s.id
        WHERE bfm.id = ?
    ''', (mon_id,))
    
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    
    # Get move names
    move_ids = [row['move1_id'], row['move2_id'], row['move3_id'], row['move4_id']]
    moves = []
    for mid in move_ids:
        if mid and mid > 0:
            cursor.execute('SELECT name FROM moves WHERE id = ?', (mid,))
            m = cursor.fetchone()
            moves.append(m['name'] if m else f"Move#{mid}")
        else:
            moves.append("---")
    
    # Get item name
    item_name = "None"
    if row['item_id']:
        cursor.execute('SELECT name FROM items WHERE id = ?', (row['item_id'],))
        item = cursor.fetchone()
        if item:
            item_name = item['name']
    
    conn.close()
    
    return {
        'id': row['id'],
        'species_id': row['species_id'],
        'species_name': row['species_name'] or f"Species#{row['species_id']}",
        'moves': moves,
        'item_name': item_name,
        'nature': row['nature'],
        'ev_spread': row['ev_spread']
    }

def get_frontier_mon_count() -> int:
    """Get total number of frontier mons in the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM battle_frontier_mons')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def format_frontier_mon(mon: dict) -> str:
    """Format a frontier mon dict as a readable string."""
    if not mon:
        return "Not found"
    
    lines = [
        f"#{mon['id']}: {mon['species_name']}",
        f"  Nature: {mon['nature']}",
        f"  Item: {mon['item_name']}",
        f"  Moves: {', '.join(mon['moves'])}",
        f"  EVs: {mon['ev_spread']}"
    ]
    return "\n".join(lines)


def get_species_name(species_id: int) -> str:
    """Get species name by ID."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM species WHERE id = ?', (species_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else f"Species#{species_id}"


def get_move_name(move_id: int) -> str:
    """Get move name by ID."""
    if move_id == 0:
        return "---"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM moves WHERE id = ?', (move_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else f"Move#{move_id}"


def get_item_name(item_id: int) -> str:
    """Get item name by ID."""
    if item_id == 0:
        return "None"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT name FROM items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else f"Item#{item_id}"
