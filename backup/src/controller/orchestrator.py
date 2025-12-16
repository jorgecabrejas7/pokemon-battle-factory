import logging
import time
from typing import Optional

from ..backends.emerald.backend import EmeraldBackend
from ..core.dataclasses import BattleState
from ..config import config, Buttons

logger = logging.getLogger(__name__)

class GameOrchestrator:
    """
    Orchestrates the game loop for Reinforcement Learning.
    
    Implements a strict Step -> Observe architecture:
    1. Receive Action (Button Press)
    2. execute Action (Advance Frames)
    3. Observe State (Fetch all variables)
    """
    
    def __init__(self, backend: Optional[EmeraldBackend] = None):
        self.backend = backend or EmeraldBackend()
        self._connected = False
        
    def connect(self) -> None:
        """Connect to the backend."""
        if not self._connected:
            self.backend.connect()
            self._connected = True
            
    def step(self, action_id: int) -> BattleState:
        """
        Execute a single game step.
        
        Args:
            action_id: Button mask to press (or index mapped to buttons).
                       If using direct button masks:
                       1=A, 2=B, etc. or specific bitmasks.
                       For now accepting direct button ID 1-8 logic or bitmask.
                       Assuming mapping 1-8 for consistency with env.
        
        Returns:
            The complete game state after the step.
        """
        self.connect()
        
        # 1. Inject Input
        if action_id > 0:
            self.backend.inject_action(action_id)
            
        # 2. Advance Game (Wait for processing)
        # We need a consistent frame advance or wait logic.
        # Ideally: Wait for input to be processed or frame gap.
        # For full observability, we might just sleep small amount or advance N frames.
        # Configurable wait time from config.
        time.sleep(config.timing.wait_short) 
        
        # 3. Fetch Full State
        state = self.backend.read_battle_state()
        
        return state
        
    def reset(self) -> BattleState:
        """Reset environment (or just reconnect/read state)."""
        self.connect()
        return self.backend.read_battle_state()
    
    def cleanup(self):
        self.backend.disconnect()
