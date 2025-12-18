import sqlite3
import re
import os
from typing import List, Tuple

"""
Item Seeder.

Reads `item_constants.h` to populate the `items` table in the database with basic
identifier/name mapping. This often acts as a fallback or pre-fill step.

Usage:
    python3 scripts/seed_items.py
"""

DB_PATH = "src/data/knowledge_base.db"
HEADER_PATH = "data/raw/item_constants.h"

def parse_header(path: str) -> List[Tuple[int, str]]:
    """Parses item constants into ID/Name pairs.

    Args:
        path (str): Path to `item_constants.h`.

    Returns:
        List[Tuple[int, str]]: List of (id, name) tuples.
    """
    items = []
    with open(path, 'r') as f:
        for line in f:
            match = re.match(r'#define\s+ITEM_(\w+)\s+(\d+)', line)
            if match:
                raw_name = match.group(1)
                item_id = int(match.group(2))
                # Convert ITEM_NAME -> Item Name
                name = raw_name.replace('_', ' ').title()
                items.append((item_id, name))
    return items

def seed_db(items: List[Tuple[int, str]]) -> None:
    """Inserts item data into the database.

    Args:
        items (List[Tuple[int, str]]): List of item data to insert.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print(f"Seeding {len(items)} items...")
    for item_id, name in items:
        try:
            cursor.execute("INSERT OR REPLACE INTO items (id, identifier, name) VALUES (?, ?, ?)", 
                           (item_id, name.lower().replace(' ', '-'), name))
        except Exception as e:
            print(f"Error seeding {name}: {e}")
            
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
    elif not os.path.exists(HEADER_PATH):
        print(f"Header not found at {HEADER_PATH}")
    else:
        items = parse_header(HEADER_PATH)
        seed_db(items)
