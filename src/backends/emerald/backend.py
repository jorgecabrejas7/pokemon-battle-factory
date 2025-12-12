from typing import Optional
import sys
from ...core.protocols import BattleBackend
from ...core.dataclasses import BattleState, FactoryState

try:
    import mgba.core
    import mgba.image
    import mgba.log
    MGBA_AVAILABLE = True
except ImportError as e:
    print(f"DEBUG: backend.py failed to import mgba: {e}")
    MGBA_AVAILABLE = False

class EmeraldBackend(BattleBackend):
    """
    Real Interface for Pokemon Emerald using LibMGBA.
    """
    
    def __init__(self, rom_path: str):
        if not MGBA_AVAILABLE:
            raise ImportError(
                "The 'mgba' python module is not installed.\n"
                "Please install it using your system package manager or build it from source."
            )
        self.core = None
        self.rom_path = rom_path

    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        self.core = mgba.core.loadPath(rom_path)
        if not self.core:
             raise RuntimeError(f"Failed to load ROM: {rom_path}")
        
        self.core.reset()
        if save_state:
             self.core.loadState(save_state)
             
    def read_battle_state(self) -> BattleState:
        # TODO: Implement RAM reading logic here (Phase 2.2)
        # For now return empty state
        return BattleState()

    def read_factory_state(self) -> FactoryState:
        # TODO: Implement RAM reading logic here
        return FactoryState()

    def inject_action(self, action_id: int) -> None:
        # TODO: Implement key press injection
        pass

    def advance_frame(self, frames: int = 1) -> None:
        if self.core:
            for _ in range(frames):
                self.core.runFrame()

    def save_state(self) -> bytes:
        # TODO: Implement state serialization
        return b""

    def load_state(self, state: bytes) -> None:
        # TODO: Implement state deserialization
        pass

    def reset(self) -> None:
        if self.core:
            self.core.reset()

    def run_until_input_required(self) -> BattleState:
        # TODO: Implement fast forward logic reading 'is_waiting_for_input' flag from RAM
        return self.read_battle_state()

    def get_game_version(self) -> str:
        return "emerald"
