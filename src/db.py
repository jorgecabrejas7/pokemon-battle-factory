import sqlite3
import os
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

class PokemonDatabase:
    """Handles interactions with the SQLite knowledge base.

    This class provides read-only access to static game data such as move details,
    species base stats, and item effects.

    Attributes:
        db_path (str): Path to the SQLite database file.
        conn (sqlite3.Connection): Active database connection or None.
    """

    def __init__(self, db_path: str = "src/data/knowledge_base.db"):
        """Initializes the database handler.

        Args:
            db_path (str): Relative or absolute path to the .db file.
        """
        self.db_path = db_path
        self.conn = None
        
    def connect(self) -> None:
        """Establishes a connection to the SQLite database.

        Sets the row_factory to sqlite3.Row for name-based access.
        Logs an error if the database file does not exist or connection fails.
        """
        if not os.path.exists(self.db_path):
            logger.error(f"Database not found at {self.db_path}")
            return
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")

    def close(self) -> None:
        """Closes the current database connection if active."""
        if self.conn:
            self.conn.close()
            self.conn = None


    def get_move_details(self, move_id: int) -> Optional[Dict[str, Any]]: # Forward ref or import if needed, assuming dynamic typing in db layer mostly
        """Retrieves detailed information for a specific move.

        Args:
            move_id (int): The internal game ID of the move.

        Returns:
            Optional[Dict[str, Any]]: A dictionary containing move attributes (power, accuracy, etc.),
                                      or None if the move ID is not found.
        """
        # We need to return an object matching the Move dataclass structure. 
        # Since db.py doesn't depend on models.py (circular import risk?), we return dict or simple object?
        # Ideally models.py depends on db.py or neither. memory.py depends on both.
        # Let's import inside method if needed or return Dict and let memory.py instantiate?
        # Better: let models.py NOT depend on db.py. logic.py/memory.py uses both.
        # But here I am constructing Move objects?
        # Let's return dictionaries here to keep db.py decoupled from models.py if possible, OR
        # Just return the Row and let caller handle.
        # Existing code returns strings.
        # Let's return dictionaries for now to be safe.
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM moves WHERE id = ?", (move_id,))
        row = cursor.fetchone()
        if not row: return None
        
        # Parse flags
        flags_str = row['flags'] or ""
        flags = [f.strip() for f in flags_str.split('|') if f.strip()]
        
        return {
            "id": row['id'],
            "name": row['name'],
            "type": row['type'],
            "power": row['power'],
            "accuracy": row['accuracy'],
            "pp": row['pp'],
            "effect": row['effect'],
            "target": row['target'],
            "priority": row['priority'],
            "flags": flags,
            "split": row['split']
        }

    def get_species_details(self, species_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves base stats and types for a Pokémon species.

        Args:
            species_id (int): The internal species ID.

        Returns:
            Optional[Dict[str, Any]]: Dictionary with keys 'base_stats', 'types', 'abilities',
                                      or None if not found.
        """
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM species WHERE id = ?", (species_id,))
        row = cursor.fetchone()
        if not row: return None
        
        return {
            "id": row['id'],
            "name": row['name'],
            "type1": row['type1'],
            "type2": row['type2'],
            "base_stats": {
                "hp": row['base_hp'],
                "atk": row['base_atk'],
                "def": row['base_def'],
                "spa": row['base_sp_atk'],
                "spd": row['base_sp_def'],
                "spe": row['base_speed']
            },
            "abilities": [row['ability1'], row['ability2']]
        }

    def get_item_details(self, item_id: int) -> Dict[str, Any]:
        """Retrieves details for an item.

        Args:
            item_id (int): The internal item ID.

        Returns:
            Dict[str, Any]: Item details including hold effects. Returns a placeholder dict
                            if the item is not found in the database.
        """
        if not self.conn: return None
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        if not row: 
            # Fallback for empty item
            return {
                "id": item_id,
                "name": f"Item {item_id}",
                "description": "",
                "hold_effect": "None",
                "hold_effect_param": 0
            }

        return {
            "id": row['id'],
            "name": row['name'],
            "description": row['description'],
            "hold_effect": row['hold_effect'],
            "hold_effect_param": row['hold_effect_param']
        }
        
    def get_move_name(self, move_id: int) -> str:
        """Helper to get just the name of a move."""
        d = self.get_move_details(move_id)
        return d['name'] if d else f"Move {move_id}"
        
    def get_species_name(self, species_id: int) -> str:
        """Helper to get just the name of a species."""
        d = self.get_species_details(species_id)
        return d['name'] if d else f"Species {species_id}"
        
    def get_item_name(self, item_id: int) -> str:
        """Helper to get just the name of an item."""
        d = self.get_item_details(item_id)
        return d['name'] if d else f"Item {item_id}"
    
    def get_rental_mon_species_name(self, facility_mon_id: int) -> str:
        """Resolves the species name for a Battle Factory rental Pokémon ID.

        Factory rental mons are identified by a unique 'facility_mon_id' which maps
        to a specific species and moveset in the `battle_frontier_mons` table.

        Args:
            facility_mon_id (int): The ID from the rental array.

        Returns:
            str: The species name.
        """
        # Keep existing for backward compat if anyone uses it directly
        if not self.conn: return f"Mon {facility_mon_id}"
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT s.name 
            FROM battle_frontier_mons bfm
            JOIN species s ON bfm.species_id = s.id
            WHERE bfm.id = ?
        """, (facility_mon_id,))
        result = cursor.fetchone()
        return result[0] if result else f"Mon {facility_mon_id}"
