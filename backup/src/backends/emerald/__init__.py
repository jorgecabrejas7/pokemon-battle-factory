"""
Emerald Backend - mGBA emulator communication.

Provides:
- EmeraldBackend: Main backend class with context manager support
- MemoryReader: High-level memory reading utilities
- Constants: Memory addresses and offsets
"""

from __future__ import annotations

from .backend import EmeraldBackend
from .memory_reader import MemoryReader, BattleMon, PartyPokemon, RentalMon, FrontierState
__all__ = [
    "EmeraldBackend",
    "MemoryReader",
    "BattleMon",
    "PartyPokemon", 
    "RentalMon",
    "FrontierState",
]
