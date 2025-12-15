"""
Emerald Backend - mGBA emulator communication via socket.

This module provides the EmeraldBackend class that implements the
BattleBackend protocol for Pokemon Emerald via mGBA's Lua scripting.

Usage:
    # Context manager (recommended)
    with EmeraldBackend() as backend:
        backend.connect()
        state = backend.read_battle_state()
    
    # Manual management
    backend = EmeraldBackend()
    try:
        backend.connect()
        state = backend.read_battle_state()
    finally:
        backend.disconnect()
"""

from __future__ import annotations

import socket
import logging
import time
from typing import Optional, Set, TYPE_CHECKING

from ...core.protocols import BattleBackend
from ...core.dataclasses import BattleState, FactoryState, PlayerPokemon, EnemyPokemon, Move
from ...core.enums import BattleOutcome, StatusCondition
from ...core.exceptions import (
    ConnectionError, DisconnectedError, CommandTimeoutError, MemoryReadError
)
from ...config import config, Buttons

from .decoder import EmeraldDecoder
from .memory_reader import MemoryReader

if TYPE_CHECKING:
    from ...core.knowledge_base import KnowledgeBase

logger = logging.getLogger(__name__)


class EmeraldBackend(BattleBackend):
    """
    mGBA Backend using socket connection.
    
    Connects to mGBA via the connector.lua TCP server to:
    - Read game memory (battle state, party data, frontier state)
    - Send button inputs
    - Control frame advancement
    
    Implements context manager protocol for safe resource cleanup.
    
    Attributes:
        sock: TCP socket connection to mGBA
        memory: MemoryReader for high-level memory access
        decoder: Character decoder for Pokemon names
    """
    
    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize backend.
        
        Args:
            host: mGBA host address (default from config)
            port: mGBA port (default from config)
            timeout: Socket timeout in seconds (default from config)
        """
        self._host = host or config.network.host
        self._port = port or config.network.port
        self._timeout = timeout or config.timing.connection_timeout
        
        self.sock: Optional[socket.socket] = None
        self.decoder = EmeraldDecoder()
        self.memory: Optional[MemoryReader] = None
        self._connected = False
        
        # Battle Knowledge Tracking
        self.current_enemy_species_id: int = 0
        self.revealed_enemy_moves: Set[int] = set()
        
        # Knowledge base (lazy loaded)
        self._kb: Optional[KnowledgeBase] = None
    
    # =========================================================================
    # Context Manager Protocol
    # =========================================================================
    
    def __enter__(self) -> EmeraldBackend:
        """Enter context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, ensuring cleanup."""
        self.disconnect()
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to emulator."""
        return self._connected and self.sock is not None
    
    def connect(self, rom_path: str = "", save_state: Optional[str] = None) -> None:
        """
        Connect to mGBA emulator.
        
        Args:
            rom_path: Unused (ROM loaded in mGBA)
            save_state: Unused (save states managed by mGBA)
            
        Raises:
            ConnectionError: If connection fails
        """
        if self._connected:
            logger.debug("Already connected")
            return
        
        logger.info(f"Connecting to {self._host}:{self._port}...")
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(self._timeout)
        
        try:
            self.sock.connect((self._host, self._port))
            logger.debug("Socket connected, testing with PING...")
            
            self.memory = MemoryReader(self)
            resp = self._send_command("PING")
            
            if resp == "PONG":
                self._connected = True
                logger.info("Connected successfully to mGBA")
            else:
                raise ConnectionError(
                    "Unexpected response from mGBA",
                    host=self._host,
                    port=self._port,
                    reason=f"Expected PONG, got: {resp}"
                )
                
        except socket.error as e:
            self._cleanup_socket()
            
            if isinstance(e, ConnectionRefusedError):
                raise ConnectionError(
                    "Could not connect to mGBA (connection refused)",
                    host=self._host,
                    port=self._port,
                    reason=(
                        "Make sure:\n"
                        "1. mGBA is running with Pokemon Emerald loaded\n"
                        "2. connector.lua is loaded (Tools -> Scripting -> Load)\n"
                        "3. Console shows 'Listening on port 7777'"
                    )
                )
            elif isinstance(e, socket.timeout):
                raise ConnectionError(
                    "Connection to mGBA timed out",
                    host=self._host,
                    port=self._port,
                    reason="The game may be paused - script only runs during gameplay"
                )
            else:
                raise ConnectionError(
                    f"Connection failed: {e}",
                    host=self._host,
                    port=self._port,
                )
    
    def disconnect(self) -> None:
        """Disconnect from emulator and cleanup resources."""
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self._cleanup_socket()
        logger.info("Disconnected from mGBA")
    
    def _cleanup_socket(self) -> None:
        """Clean up socket state."""
        self.sock = None
        self.memory = None
        self._connected = False
    
    def _ensure_connected(self) -> None:
        """Raise if not connected."""
        if not self._connected:
            raise DisconnectedError()
    
    # =========================================================================
    # Command Interface
    # =========================================================================
    
    def _send_command(self, cmd: str) -> str:
        """
        Send command to mGBA and get response.
        
        Args:
            cmd: Command string
            
        Returns:
            Response string
            
        Raises:
            DisconnectedError: If not connected
            CommandTimeoutError: If command times out
        """
        if not self.sock:
            raise DisconnectedError()
        
        try:
            self.sock.sendall((cmd + "\n").encode('utf-8'))
            data = self.sock.recv(config.network.buffer_size).decode('utf-8').strip()
            return data
        except socket.timeout:
            logger.warning(f"Command timed out: {cmd}")
            raise CommandTimeoutError(cmd, self._timeout)
        except socket.error as e:
            logger.error(f"Socket error during command: {e}")
            self._connected = False
            raise DisconnectedError(f"Lost connection: {e}")
    
    # =========================================================================
    # Knowledge Base Access
    # =========================================================================
    
    @property
    def kb(self) -> KnowledgeBase:
        """Get knowledge base (lazy loaded)."""
        if self._kb is None:
            from ...core.knowledge_base import get_kb
            self._kb = get_kb()
        return self._kb
    
    # =========================================================================
    # BattleBackend Protocol Implementation
    # =========================================================================
    
    def read_battle_state(self) -> BattleState:
        """Read current battle state from memory."""
        if not self.memory:
            return BattleState()
        
        outcome = self.memory.read_battle_outcome()
        move_id, move_user = self.memory.read_last_move()
        is_input = self.memory.read_input_status()
        
        # Read Battle Mons
        battle_mons = self.memory.read_battle_mons()
        
        player_mon = None
        enemy_mon = None
        
        if len(battle_mons) >= 2:
            p_data = battle_mons[0]  # Player slot 0
            e_data = battle_mons[1]  # Enemy slot 1 (singles)
            
            # Populate Player Pokemon
            p_moves = []
            for i, mid in enumerate(p_data.moves):
                if mid > 0:
                    try:
                        mdata = self.kb.get_move(mid)
                        p_moves.append(Move(
                            move_id=mid,
                            name=mdata.name,
                            type_id=0,
                            base_power=mdata.power,
                            accuracy=mdata.accuracy,
                            current_pp=p_data.pp[i] if i < len(p_data.pp) else 0
                        ))
                    except Exception:
                        p_moves.append(Move(move_id=mid, name=f"Move#{mid}"))
            
            player_mon = PlayerPokemon(
                species_id=p_data.species_id,
                level=p_data.level,
                current_hp=p_data.current_hp,
                hp=p_data.max_hp,
                attack=p_data.attack,
                defense=p_data.defense,
                sp_attack=p_data.sp_attack,
                sp_defense=p_data.sp_defense,
                speed=p_data.speed,
                status_condition=StatusCondition(0),
                moves=p_moves,
                stat_stages=p_data.stat_stages
            )
            
            # Populate Enemy Pokemon
            try:
                species = self.kb.get_species(e_data.species_id)
                species_name = species.name
            except Exception:
                species_name = f"Species#{e_data.species_id}"
            
            # Get revealed moves
            e_moves = []
            for mid in self.revealed_enemy_moves:
                try:
                    mdata = self.kb.get_move(mid)
                    e_moves.append(Move(
                        move_id=mid,
                        name=mdata.name,
                        base_power=mdata.power,
                        accuracy=mdata.accuracy
                    ))
                except Exception:
                    e_moves.append(Move(move_id=mid, name=f"Move#{mid}"))
            
            enemy_mon = EnemyPokemon(
                species_id=e_data.species_id,
                nickname=species_name,
                level=e_data.level,
                hp_percentage=(e_data.current_hp / e_data.max_hp * 100.0) 
                              if e_data.max_hp > 0 else 0.0,
                revealed_moves=e_moves
            )
        
        return BattleState(
            active_pokemon=player_mon,
            enemy_active_pokemon=enemy_mon,
            battle_outcome=outcome,
            last_move_used=move_id,
            last_move_user=move_user,
            is_waiting_for_input=is_input
        )
    
    def inject_action(self, action_id: int) -> None:
        """
        Inject a button press.
        
        Args:
            action_id: Action ID (1=A, 2=B, etc.)
        """
        self._ensure_connected()
        
        # Map action IDs to button masks
        action_map = {
            1: Buttons.A,
            2: Buttons.B,
            3: Buttons.SELECT,
            4: Buttons.START,
            5: Buttons.RIGHT,
            6: Buttons.LEFT,
            7: Buttons.UP,
            8: Buttons.DOWN,
        }
        
        mask = action_map.get(action_id, 0)
        if mask == 0:
            return
        
        self._send_command(f"SET_INPUT {mask}")
        time.sleep(config.timing.button_hold_time)
        self._send_command("SET_INPUT 0")
    
    def advance_frame(self, frames: int = 1) -> None:
        """Advance emulator by N frames."""
        self._ensure_connected()
        self._send_command(f"FRAME_ADVANCE {frames}")
    
    def run_until_input_required(self) -> BattleState:
        """
        Run emulator until player input is required or battle ends.
        
        Tracks the last move used during execution for reward calculation.
        
        Returns:
            Final BattleState when input is needed or battle ends
        """
        if not self.memory:
            return BattleState()
        
        max_frames = int(config.timing.input_timeout * config.timing.fps)
        frames_run = 0
        
        last_move_id = 0
        last_move_user = -1
        
        while frames_run < max_frames:
            # Check status
            outcome = self.memory.read_battle_outcome()
            is_input = self.memory.read_input_status()
            
            # Update move info if changed
            curr_move_id, curr_user = self.memory.read_last_move()
            if curr_move_id != 0:
                last_move_id = curr_move_id
                last_move_user = curr_user
                
                # Track enemy moves (users 1 and 3 are enemy slots)
                if curr_user in [1, 3]:
                    self.revealed_enemy_moves.add(curr_move_id)
            
            # Stop conditions
            if outcome != BattleOutcome.ONGOING:
                break
            if is_input:
                break
            
            # Advance (5 frames at a time for efficiency)
            self.advance_frame(5)
            frames_run += 5
        
        # Check for enemy switch (species change)
        try:
            mons = self.memory.read_battle_mons()
            if len(mons) >= 2:
                enemy_mon = mons[1]
                if enemy_mon.species_id != self.current_enemy_species_id:
                    self.current_enemy_species_id = enemy_mon.species_id
                    self.revealed_enemy_moves.clear()
        except Exception as e:
            logger.debug(f"Error checking enemy switch: {e}")
        
        # Build final state
        final_state = self.read_battle_state()
        final_state.last_move_used = last_move_id
        final_state.last_move_user = last_move_user
        
        return final_state
    
    def read_factory_state(self) -> FactoryState:
        """Read Battle Factory specific state."""
        if not self.memory:
            return FactoryState()
        
        frontier = self.memory.read_frontier_state()
        if not frontier:
            return FactoryState()
        
        return FactoryState(win_streak=frontier.win_streak)
    
    def save_state(self) -> bytes:
        """Save emulator state (not implemented for socket backend)."""
        # Would require mGBA savestate support in connector.lua
        return b""
    
    def load_state(self, state: bytes) -> None:
        """Load emulator state (not implemented for socket backend)."""
        pass
    
    def reset(self) -> None:
        """Reset emulator and tracking state."""
        self._ensure_connected()
        self._send_command("RESET")
        self.current_enemy_species_id = 0
        self.revealed_enemy_moves.clear()
    
    def get_game_version(self) -> str:
        """Get game version identifier."""
        return "emerald"
    
    # =========================================================================
    # Additional Utility Methods
    # =========================================================================
    
    def press_button(self, button: int, hold_time: float | None = None) -> None:
        """
        Press and release a button.
        
        Args:
            button: Button mask from Buttons class
            hold_time: How long to hold (default from config)
        """
        self._ensure_connected()
        hold = hold_time or config.timing.button_hold_time
        
        self._send_command(f"SET_INPUT {button}")
        time.sleep(hold)
        self._send_command("SET_INPUT 0")
    
    def is_waiting_for_input(self) -> bool:
        """Check if game is waiting for player input."""
        response = self._send_command("IS_WAITING_INPUT")
        return response == "YES"
    
    def get_battle_outcome(self) -> BattleOutcome:
        """Get current battle outcome."""
        response = self._send_command("GET_BATTLE_OUTCOME")
        try:
            val = int(response)
            return BattleOutcome(val) if val in range(5) else BattleOutcome.ONGOING
        except ValueError:
            return BattleOutcome.ONGOING
    
    def ping(self) -> bool:
        """Test connection with PING command."""
        try:
            return self._send_command("PING") == "PONG"
        except Exception:
            return False
