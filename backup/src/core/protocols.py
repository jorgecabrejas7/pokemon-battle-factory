from abc import ABC, abstractmethod
from typing import Optional
from .dataclasses import BattleState, FactoryState

class BattleBackend(ABC):
    """Abstract interface for emulator communication."""
    
    @abstractmethod
    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        """Initialize emulator with ROM and optional save state."""
        pass
    
    @abstractmethod
    def read_battle_state(self) -> BattleState:
        """Extract current battle state from RAM."""
        pass
    
    @abstractmethod
    def read_factory_state(self) -> FactoryState:
        """Extract Factory-specific state (draft pool, hints, etc.)."""
        pass
    
    @abstractmethod
    def inject_action(self, action_id: int) -> None:
        """Send button press to emulator."""
        pass
    
    @abstractmethod
    def advance_frame(self, frames: int = 1) -> None:
        """Step emulator forward N frames."""
        pass
    
    @abstractmethod
    def save_state(self) -> bytes:
        """Serialize current emulator state."""
        pass
    
    @abstractmethod
    def load_state(self, state: bytes) -> None:
        """Restore emulator to saved state."""
        pass
    
    @abstractmethod
    def reset(self) -> None:
        """Reset to initial Factory challenge state."""
        pass

    @abstractmethod
    def run_until_input_required(self) -> BattleState:
        """Fast-forwards emulator, skipping text/animations until agent decision is needed."""
        pass
    
    @abstractmethod
    def get_game_version(self) -> str:
        """Return 'emerald' or 'platinum'."""
        pass
