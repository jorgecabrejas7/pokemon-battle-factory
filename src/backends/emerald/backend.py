import socket
import logging
import time
from typing import Optional, Set
from ...core.protocols import BattleBackend
from ...core.dataclasses import BattleState, FactoryState, PlayerPokemon, EnemyPokemon, Move
from ...core.enums import BattleOutcome, StatusCondition, MoveCategory
from ...core.knowledge import get_species_base_stats, get_move_data
from .decoder import EmeraldDecoder
from .memory_reader import MemoryReader

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("EmeraldBackend")

HOST = '127.0.0.1'
PORT = 7777

class EmeraldBackend(BattleBackend):
    """mGBA Backend using socket connection."""
    
    def __init__(self, rom_path: str = ""):
        self.sock = None
        self.decoder = EmeraldDecoder()
        self.memory = None # Set after connection
        self.ACTION_MAP = {
            1: 1,    # A
            2: 2,    # B
            3: 4,    # Select
            4: 8,    # Start
            5: 16,   # Right
            6: 32,   # Left
            7: 64,   # Up
            8: 128,  # Down
        }
        
        # Battle Knowledge Tracking
        self.current_enemy_species_id: int = 0
        self.revealed_enemy_moves: Set[int] = set()

    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        logger.info(f"Connecting to {HOST}:{PORT}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        
        try:
            self.sock.connect((HOST, PORT))
            logger.info("Socket connected, testing with PING...")
            self.memory = MemoryReader(self)
            resp = self._send_command("PING")
            if resp == "PONG":
                logger.info("Connected successfully.")
            else:
                logger.error(f"Unexpected response: {resp}")
                raise ConnectionError(f"Unexpected response from mGBA: {resp}")
        except ConnectionRefusedError as e:
            logger.error(f"Connection refused: {e}")
            raise ConnectionError(
                "Could not connect to mGBA (connection refused).\n"
                "1. Open mGBA with your ROM\n"
                "2. Tools -> Scripting -> File -> Load Script\n"
                "3. Select 'src/backends/emerald/connector.lua'\n"
                "4. Check console says 'Listening on port 7777'"
            )
        except socket.timeout as e:
            logger.error(f"Connection timed out: {e}")
            raise ConnectionError(
                "Could not connect to mGBA (timeout).\n"
                "The Lua script may be loaded but not accepting connections.\n"
                "Make sure the game is NOT PAUSED - the script runs in the frame callback."
            )
        except Exception as e:
            logger.error(f"Connection failed with unexpected error: {type(e).__name__}: {e}")
            raise ConnectionError(f"Connection failed: {e}")

    def _send_command(self, cmd: str) -> str:
        if not self.sock:
            raise ConnectionError("Not connected to mGBA")
        try:
            # logger.debug(f"Sending: {cmd}")
            self.sock.sendall((cmd + "\n").encode('utf-8'))
            data = self.sock.recv(4096).decode('utf-8').strip()
            # logger.debug(f"Received: {data}")
            return data
        except socket.timeout:
            logger.warning(f"Command timed out: {cmd}")
            return "ERROR"

    def read_battle_state(self) -> BattleState:
        if not self.memory:
            return BattleState()
            
        outcome = self.memory.read_battle_outcome()
        move_id, move_user = self.memory.read_last_move()
        is_input = self.memory.read_input_status()
        
        # Read Battle Mons
        battle_mons = self.memory.read_battle_mons()
        
        # Default empty
        player_mon = None
        enemy_mon = None
        
        if len(battle_mons) >= 2:
            # Player is usually slot 0, Enemy is slot 1 in Singles
            p_data = battle_mons[0]
            e_data = battle_mons[1]
            
            # --- Populate Player Pokemon ---
            p_moves = []
            for mid in p_data.moves:
                 if mid > 0:
                     mdata = get_move_data(mid)
                     p_moves.append(Move(
                         move_id=mid,
                         name=mdata['name'],
                         type_id=0, # TODO: Map string type to ID if needed
                         base_power=mdata['power'],
                         accuracy=mdata['accuracy'],
                         current_pp=p_data.pp[p_data.moves.index(mid)] # Approximation
                     ))

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
                status_condition=StatusCondition(0), # TODO: Map status bits
                moves=p_moves,
                stat_stages=p_data.stat_stages
            )
            
            # --- Populate Enemy Pokemon ---
            # 1. Get Base Stats from Knowledge Base
            base_stats = get_species_base_stats(e_data.species_id)
            
            # 2. Get Revealed Moves
            e_moves = []
            for mid in self.revealed_enemy_moves:
                mdata = get_move_data(mid)
                e_moves.append(Move(
                    move_id=mid,
                    name=mdata['name'],
                    base_power=mdata['power'],
                    accuracy=mdata['accuracy']
                ))
            
            enemy_mon = EnemyPokemon(
                species_id=e_data.species_id,
                nickname=base_stats['name'],
                level=e_data.level,
                hp_percentage=(e_data.current_hp / e_data.max_hp * 100.0) if e_data.max_hp > 0 else 0.0,
                revealed_moves=e_moves
            )
            
            # Inject Base Stats into the Enemy Object (for agent reference)
            # Note: EnemyPokemon dataclass doesn't have fields for base stats directly,
            # but we can add them dynamically or use the knowledge base in the agent.
            # For now, let's attach them as metadata if needed, but the plan says
            # "its hp and the base stats of its species".
            # The BasePokemon class has species_id, so the Agent can look it up.
            
        return BattleState(
            active_pokemon=player_mon,
            enemy_active_pokemon=enemy_mon,
            battle_outcome=outcome,
            last_move_used=move_id,
            last_move_user=move_user,
            is_waiting_for_input=is_input
        )

    def inject_action(self, action_id: int) -> None:
        """Inject a button press."""
        mask = self.ACTION_MAP.get(action_id, 0)
        if mask == 0:
            return
        self._send_command(f"SET_INPUT {mask}")
        time.sleep(0.05) 
        self._send_command("SET_INPUT 0")

    def advance_frame(self, frames: int = 1) -> None:
        self._send_command(f"FRAME_ADVANCE {frames}")

    def run_until_input_required(self) -> BattleState:
        """
        Run the emulator until player input is required or battle ends.
        Tracks the last move used during the execution period.
        """
        if not self.memory:
             return BattleState()

        max_frames = 60 * 60  # Timeout after 60 seconds (approx)
        frames_run = 0
        
        last_move_id = 0
        last_move_user = -1
        
        while frames_run < max_frames:
            # Check status
            outcome = self.memory.read_battle_outcome()
            is_input = self.memory.read_input_status()
            
            # Update move info if changed (and not zero)
            curr_move_id, curr_user = self.memory.read_last_move()
            if curr_move_id != 0:
                 last_move_id = curr_move_id
                 last_move_user = curr_user
                 
                 # Track Enemy Moves
                 # User 1 = Enemy Slot 1, User 3 = Enemy Slot 2
                 if curr_user in [1, 3]:
                     self.revealed_enemy_moves.add(curr_move_id)
            
            # Track Enemy Switch (Simple check: if enemy species changes)
            # We can't do this every frame efficiently without overhead, 
            # but checking every 60 frames or so might be okay.
            # For now, let's just do it at the end or use the read_battle_mons inside here?
            # Reading battle mons is expensive (block read).
            # Better to rely on the Agent to observe the switch in the next state observation.
            # However, we must CLEAR revealed moves if the enemy switches.
            # This requires knowing if the enemy switched.
            
            # Stop conditions
            if outcome != BattleOutcome.ONGOING:
                break
            if is_input:
                break
                
            # Advance
            self.advance_frame(5) # Run 5 frames at a time
            frames_run += 5
            
        # Check for Species Change to clear revealed moves
        # We do this AFTER the run loop to prepare the state for the Agent
        try:
            mons = self.memory.read_battle_mons()
            if len(mons) >= 2:
                enemy_mon = mons[1]
                if enemy_mon.species_id != self.current_enemy_species_id:
                    # Enemy Switched!
                    self.current_enemy_species_id = enemy_mon.species_id
                    self.revealed_enemy_moves.clear()
        except:
            pass # Ignore read errors during transition

        # Return final state with tracked move info
        final_state = self.read_battle_state()
        final_state.last_move_used = last_move_id
        final_state.last_move_user = last_move_user
        
        return final_state

    def read_factory_state(self) -> FactoryState:
        if not self.memory:
            return FactoryState()
            
        frontier = self.memory.read_frontier_state()
        if not frontier:
            return FactoryState()
            
        return FactoryState(
            win_streak=frontier.win_streak
        )

    def save_state(self) -> bytes:
        return b""

    def load_state(self, state: bytes) -> None:
        pass

    def reset(self) -> None:
        self._send_command("RESET")
        self.current_enemy_species_id = 0
        self.revealed_enemy_moves.clear()

    def get_game_version(self) -> str:
        return "emerald"
