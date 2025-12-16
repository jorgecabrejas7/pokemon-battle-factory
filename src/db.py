import sqlite3
import os
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class PokemonDatabase:
    def __init__(self, db_path: str = "src/data/knowledge_base.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        if not os.path.exists(self.db_path):
            logger.error(f"Database not found at {self.db_path}")
            return
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def get_move_name(self, move_id: int) -> str:
        if not self.conn: return f"Move {move_id}"
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM moves WHERE id = ?", (move_id,))
        row = cursor.fetchone()
        return row['name'] if row else f"Move {move_id}"

    def get_species_name(self, species_id: int) -> str:
        if not self.conn: return f"Species {species_id}"
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM species WHERE id = ?", (species_id,))
        row = cursor.fetchone()
        return row['name'] if row else f"Species {species_id}"

    def get_item_name(self, item_id: int) -> str:
        if not self.conn: return f"Item {item_id}"
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM items WHERE id = ?", (item_id,))
        result = cursor.fetchone()
        return result[0] if result else f"Item {item_id}"

    def get_rental_mon_species_name(self, facility_mon_id: int) -> str:
        if not self.conn: return f"Mon {facility_mon_id}"
        cursor = self.conn.cursor()
        # Join battle_frontier_mons with species to get the name directly
        cursor.execute("""
            SELECT s.name 
            FROM battle_frontier_mons bfm
            JOIN species s ON bfm.species_id = s.id
            WHERE bfm.id = ?
        """, (facility_mon_id,))
        result = cursor.fetchone()
        return result[0] if result else f"Mon {facility_mon_id}"
