import sqlite3
import argparse
import os

DB_PATH = "src/data/knowledge_base.db"

def inspect_db(limit=10, search=None):
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
    SELECT 
        bfm.id, 
        s.name AS species, 
        m1.name AS move1, 
        m2.name AS move2, 
        m3.name AS move3, 
        m4.name AS move4, 
        i.name AS item, 
        bfm.nature, 
        bfm.ev_spread 
    FROM battle_frontier_mons bfm
    LEFT JOIN species s ON bfm.species_id = s.id
    LEFT JOIN moves m1 ON bfm.move1_id = m1.id
    LEFT JOIN moves m2 ON bfm.move2_id = m2.id
    LEFT JOIN moves m3 ON bfm.move3_id = m3.id
    LEFT JOIN moves m4 ON bfm.move4_id = m4.id
    LEFT JOIN items i ON bfm.item_id = i.id
    """
    
    params = []
    if search:
        # Search by Species Name or ID
        if search.isdigit():
            query += " WHERE bfm.id = ?"
            params.append(int(search))
        else:
            query += " WHERE s.name LIKE ?"
            params.append(f"%{search}%")
            
    query += f" LIMIT {limit}"
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        # Formatting
        headers = ["ID", "Species", "Move 1", "Move 2", "Move 3", "Move 4", "Item", "Nature", "EVs"]
        col_widths = [5, 15, 15, 15, 15, 15, 20, 10, 5]
        
        header_row = "".join(h.ljust(w) for h, w in zip(headers, col_widths))
        print("-" * len(header_row))
        print(header_row)
        print("-" * len(header_row))
        
        for row in rows:
            # Handle None values
            cleaned_row = [str(x) if x is not None else "" for x in row]
            print("".join(val[:w-1].ljust(w) for val, w in zip(cleaned_row, col_widths)))
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect Battle Frontier Pokémon in human-readable format.")
    parser.add_argument("--limit", type=int, default=20, help="Number of records to show")
    parser.add_argument("search", nargs="?", help="Search term (Species Name or ID)")
    
    args = parser.parse_args()
    inspect_db(limit=args.limit, search=args.search)
