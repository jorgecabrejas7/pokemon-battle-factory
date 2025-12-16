"""
Knowledge Base - Optimized Pokemon data access with connection pooling.

This module provides a singleton KnowledgeBase class that maintains
a persistent database connection for efficient data access during
training and inference.

Usage:
    from src.core.knowledge_base import KnowledgeBase, kb
    
    # Using the singleton
    species = kb.get_species(25)  # Pikachu
    move = kb.get_move(85)  # Thunderbolt
    
    # Or get the instance explicitly
    kb = KnowledgeBase.get()
    kb.get_type_effectiveness("Electric", "Water")  # 2.0
"""

from __future__ import annotations

import sqlite3
import os
import threading
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
from functools import lru_cache
from pathlib import Path

from .exceptions import KnowledgeBaseError, EntityNotFoundError


# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "knowledge_base.db"


@dataclass(frozen=True)
class Species:
    """Pokemon species data."""
    id: int
    name: str
    type1: str
    type2: Optional[str]
    base_hp: int
    base_attack: int
    base_defense: int
    base_sp_attack: int
    base_sp_defense: int
    base_speed: int
    ability1_id: Optional[int] = None
    ability2_id: Optional[int] = None
    
    @property
    def base_stat_total(self) -> int:
        return (self.base_hp + self.base_attack + self.base_defense + 
                self.base_sp_attack + self.base_sp_defense + self.base_speed)
    
    @property
    def types(self) -> tuple[str, ...]:
        if self.type2 and self.type2 != self.type1:
            return (self.type1, self.type2)
        return (self.type1,)


@dataclass(frozen=True)
class Move:
    """Pokemon move data."""
    id: int
    name: str
    type: str
    power: int
    accuracy: int
    pp: int
    category: str  # Physical, Special, Status
    effect: Optional[str] = None
    effect_chance: int = 0
    priority: int = 0
    target: str = "single"
    
    @property
    def is_damaging(self) -> bool:
        return self.category in ("Physical", "Special") and self.power > 0


@dataclass(frozen=True)
class Item:
    """Held item data."""
    id: int
    name: str
    description: Optional[str] = None


@dataclass(frozen=True)
class FrontierMon:
    """Battle Frontier rental Pokemon set."""
    id: int
    species_id: int
    species_name: str
    move1_id: int
    move2_id: int
    move3_id: int
    move4_id: int
    item_id: int
    nature: str
    ev_spread: int
    
    @property
    def move_ids(self) -> tuple[int, ...]:
        return (self.move1_id, self.move2_id, self.move3_id, self.move4_id)


class KnowledgeBase:
    """
    Singleton knowledge base with connection pooling and caching.
    
    Maintains a persistent database connection and uses LRU caching
    to minimize database queries during training.
    
    Thread-safe for use in multi-threaded RL training.
    """
    
    _instance: Optional[KnowledgeBase] = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize knowledge base with database connection.
        
        Args:
            db_path: Path to SQLite database. Uses default if None.
        """
        self._db_path = db_path or DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self._local = threading.local()
        self._connect()
    
    @classmethod
    def get(cls, db_path: Optional[Path] = None) -> KnowledgeBase:
        """
        Get the singleton instance.
        
        Args:
            db_path: Optional database path (only used on first call)
            
        Returns:
            KnowledgeBase singleton instance
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance
    
    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None
    
    def _connect(self) -> None:
        """Establish database connection."""
        if not self._db_path.exists():
            raise KnowledgeBaseError(
                f"Database not found: {self._db_path}",
                query="connect"
            )
        
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,  # Allow multi-threaded access
        )
        self._conn.row_factory = sqlite3.Row
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self._db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def close(self) -> None:
        """Close database connections."""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    # =========================================================================
    # Species Queries
    # =========================================================================
    
    @lru_cache(maxsize=512)
    def get_species(self, species_id: int) -> Species:
        """
        Get species data by ID.
        
        Args:
            species_id: Pokemon species ID
            
        Returns:
            Species dataclass
            
        Raises:
            EntityNotFoundError: If species not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, type1, type2, 
                   base_hp, base_atk, base_def, 
                   base_sp_atk, base_sp_def, base_speed,
                   ability1_id, ability2_id
            FROM species WHERE id = ?
        ''', (species_id,))
        
        row = cursor.fetchone()
        if not row:
            raise EntityNotFoundError("Species", species_id)
        
        return Species(
            id=row['id'],
            name=row['name'],
            type1=row['type1'],
            type2=row['type2'],
            base_hp=row['base_hp'],
            base_attack=row['base_atk'],
            base_defense=row['base_def'],
            base_sp_attack=row['base_sp_atk'],
            base_sp_defense=row['base_sp_def'],
            base_speed=row['base_speed'],
            ability1_id=row['ability1_id'] if 'ability1_id' in row.keys() else None,
            ability2_id=row['ability2_id'] if 'ability2_id' in row.keys() else None,
        )
    
    def get_species_name(self, species_id: int) -> str:
        """Get species name by ID."""
        try:
            return self.get_species(species_id).name
        except EntityNotFoundError:
            return f"Species#{species_id}"
    
    def get_species_by_name(self, name: str) -> Optional[Species]:
        """Get species by name (case-insensitive)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM species 
            WHERE LOWER(name) = LOWER(?)
        ''', (name,))
        
        row = cursor.fetchone()
        if row:
            return self.get_species(row['id'])
        return None
    
    # =========================================================================
    # Move Queries
    # =========================================================================
    
    @lru_cache(maxsize=512)
    def get_move(self, move_id: int) -> Move:
        """
        Get move data by ID.
        
        Args:
            move_id: Move ID
            
        Returns:
            Move dataclass
            
        Raises:
            EntityNotFoundError: If move not found
        """
        if move_id == 0:
            return Move(id=0, name="---", type="Normal", power=0, 
                       accuracy=0, pp=0, category="Status")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM moves WHERE id = ?
        ''', (move_id,))
        
        row = cursor.fetchone()
        if not row:
            raise EntityNotFoundError("Move", move_id)
        
        return Move(
            id=row['id'],
            name=row['name'],
            type=row['type'] if 'type' in row.keys() else 'Normal',
            power=row['power'] if row['power'] else 0,
            accuracy=row['accuracy'] if row['accuracy'] else 0,
            pp=row['pp'] if 'pp' in row.keys() else 0,
            category=row['category'] if 'category' in row.keys() else 'Status',
            effect=row['effect'] if 'effect' in row.keys() else None,
            effect_chance=row['effect_chance'] if 'effect_chance' in row.keys() else 0,
            priority=row['priority'] if 'priority' in row.keys() else 0,
        )
    
    def get_move_name(self, move_id: int) -> str:
        """Get move name by ID."""
        if move_id == 0:
            return "---"
        try:
            return self.get_move(move_id).name
        except EntityNotFoundError:
            return f"Move#{move_id}"
    
    # =========================================================================
    # Item Queries
    # =========================================================================
    
    @lru_cache(maxsize=512)
    def get_item(self, item_id: int) -> Item:
        """Get item data by ID."""
        if item_id == 0:
            return Item(id=0, name="None")
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM items WHERE id = ?', (item_id,))
        row = cursor.fetchone()
        
        if not row:
            raise EntityNotFoundError("Item", item_id)
        
        return Item(
            id=row['id'],
            name=row['name'],
            description=row['description'] if 'description' in row.keys() else None,
        )
    
    def get_item_name(self, item_id: int) -> str:
        """Get item name by ID."""
        if item_id == 0:
            return "None"
        try:
            return self.get_item(item_id).name
        except EntityNotFoundError:
            return f"Item#{item_id}"
    
    # =========================================================================
    # Frontier Mon Queries
    # =========================================================================
    
    @lru_cache(maxsize=1024)
    def get_frontier_mon(self, mon_id: int) -> FrontierMon:
        """
        Get Battle Frontier rental Pokemon set by ID.
        
        Args:
            mon_id: Frontier mon ID (1-882)
            
        Returns:
            FrontierMon dataclass
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                bfm.id, bfm.species_id, s.name as species_name,
                bfm.move1_id, bfm.move2_id, bfm.move3_id, bfm.move4_id,
                bfm.item_id, bfm.nature, bfm.ev_spread
            FROM battle_frontier_mons bfm
            LEFT JOIN species s ON bfm.species_id = s.id
            WHERE bfm.id = ?
        ''', (mon_id,))
        
        row = cursor.fetchone()
        if not row:
            raise EntityNotFoundError("FrontierMon", mon_id)
        
        return FrontierMon(
            id=row['id'],
            species_id=row['species_id'],
            species_name=row['species_name'] or f"Species#{row['species_id']}",
            move1_id=row['move1_id'],
            move2_id=row['move2_id'],
            move3_id=row['move3_id'],
            move4_id=row['move4_id'],
            item_id=row['item_id'],
            nature=row['nature'],
            ev_spread=row['ev_spread'],
        )
    
    def get_frontier_mon_with_details(self, mon_id: int) -> Dict[str, Any]:
        """
        Get frontier mon with resolved names for display.
        
        Returns dict with species_name, move names, item name, etc.
        """
        fm = self.get_frontier_mon(mon_id)
        
        return {
            'id': fm.id,
            'species_id': fm.species_id,
            'species_name': fm.species_name,
            'moves': [
                self.get_move_name(fm.move1_id),
                self.get_move_name(fm.move2_id),
                self.get_move_name(fm.move3_id),
                self.get_move_name(fm.move4_id),
            ],
            'item_name': self.get_item_name(fm.item_id),
            'nature': fm.nature,
            'ev_spread': fm.ev_spread,
        }
    
    def get_frontier_mon_count(self) -> int:
        """Get total number of frontier mons in database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM battle_frontier_mons')
        return cursor.fetchone()[0]
    
    # =========================================================================
    # Type Effectiveness
    # =========================================================================
    
    @lru_cache(maxsize=400)
    def get_type_effectiveness(
        self, 
        attacking_type: str, 
        defending_type: str
    ) -> float:
        """
        Get type effectiveness multiplier.
        
        Args:
            attacking_type: Attacking move type
            defending_type: Defending Pokemon type
            
        Returns:
            Effectiveness multiplier (0.0, 0.5, 1.0, or 2.0)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT effectiveness FROM type_efficacy
            WHERE attacking_type = ? AND defending_type = ?
        ''', (attacking_type, defending_type))
        
        row = cursor.fetchone()
        if row:
            return row['effectiveness']
        return 1.0  # Default neutral
    
    def get_type_matchup(
        self, 
        attacking_type: str, 
        defender_types: tuple[str, ...]
    ) -> float:
        """
        Get combined type effectiveness against a Pokemon.
        
        Args:
            attacking_type: Attacking move type
            defender_types: Tuple of defender's types
            
        Returns:
            Combined effectiveness multiplier
        """
        multiplier = 1.0
        for def_type in defender_types:
            multiplier *= self.get_type_effectiveness(attacking_type, def_type)
        return multiplier
    
    # =========================================================================
    # Batch Queries
    # =========================================================================
    
    def get_species_batch(self, species_ids: List[int]) -> Dict[int, Species]:
        """Get multiple species in one query (more efficient)."""
        result = {}
        for sid in species_ids:
            try:
                result[sid] = self.get_species(sid)
            except EntityNotFoundError:
                pass
        return result
    
    def get_moves_batch(self, move_ids: List[int]) -> Dict[int, Move]:
        """Get multiple moves in one query."""
        result = {}
        for mid in move_ids:
            try:
                result[mid] = self.get_move(mid)
            except EntityNotFoundError:
                pass
        return result
    
    # =========================================================================
    # Cache Management
    # =========================================================================
    
    def clear_cache(self) -> None:
        """Clear all LRU caches."""
        self.get_species.cache_clear()
        self.get_move.cache_clear()
        self.get_item.cache_clear()
        self.get_frontier_mon.cache_clear()
        self.get_type_effectiveness.cache_clear()
    
    def cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "species": self.get_species.cache_info(),
            "move": self.get_move.cache_info(),
            "item": self.get_item.cache_info(),
            "frontier_mon": self.get_frontier_mon.cache_info(),
            "type_effectiveness": self.get_type_effectiveness.cache_info(),
        }


# Global singleton instance for convenience
kb = KnowledgeBase.get() if DB_PATH.exists() else None


def get_kb() -> KnowledgeBase:
    """Get the knowledge base singleton, initializing if needed."""
    global kb
    if kb is None:
        kb = KnowledgeBase.get()
    return kb

