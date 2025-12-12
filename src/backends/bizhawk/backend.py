import socket
import time
from typing import Optional, List
from ...core.protocols import BattleBackend, BattleState, FactoryState
from ..emerald.decoder import EmeraldDecoder

# Constants
HOST = '127.0.0.1'
PORT = 7777

class BizHawkBackend(BattleBackend):
    def __init__(self, rom_path: str = ""):
        self.sock = None
        self.decoder = EmeraldDecoder() # Reuse our existing decoder!
        
        # Mapping matching the Lua script bitmask
        self.ACTION_MAP = {
            # Action ID -> Bitmask
            # 0: No Op
            1: 1, # A
            2: 2, # B
            3: 4, # Select
            4: 8, # Start
            5: 16, # Right
            6: 32, # Left
            7: 64, # Up
            8: 128, # Down
        }

    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        """Connects to the BizHawk Lua Server."""
        print(f"[BizHawk] Connecting to {HOST}:{PORT}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0) # 5s timeout
        
        try:
            self.sock.connect((HOST, PORT))
            print("[BizHawk] Connected successfully.")
        except ConnectionRefusedError:
            raise ConnectionError(
                "Could not connect to BizHawk. \n"
                "1. Open BizHawk.\n"
                "2. Drag-and-drop 'src/backends/bizhawk/connector.lua' into the window.\n"
                "3. Ensure the Lua console says 'Listening on port 7777'."
            )

    def _send_command(self, cmd: str) -> str:
        if not self.sock:
            raise ConnectionError("Not connected to BizHawk")
            
        try:
            self.sock.sendall((cmd + "\n").encode('utf-8'))
            data = self.sock.recv(4096).decode('utf-8').strip()
            return data
        except socket.timeout:
            print(f"[BizHawk] Command '{cmd}' timed out.")
            return "ERROR"

    def read_battle_state(self) -> BattleState:
        # Example Usage: Read valid memory range for Player Party
        # Party Offset: 0x020244EC (100 bytes * 6) = 600 bytes
        # We need to reuse 'constants.py' from emerald
        
        # For now, let's just test connectivity by reading a small chunk
        # response = self._send_command("READ_BLOCK 020244EC 64") # 100 bytes hex size? No, hex val for size
        # 100 decimal = 0x64
        # self.decoder.decode_pokemon(bytes.fromhex(response))
        
        return BattleState() # Return empty for now until integrated with Decoder

    def inject_action(self, action_id: int) -> None:
        mask = self.ACTION_MAP.get(action_id, 0)
        resp = self._send_command(f"SET_INPUT {mask}")
        if resp != "OK":
            print(f"[BizHawk] Warning: Input injection failed: {resp}")

    def advance_frame(self, frames: int = 1) -> None:
        self._send_command(f"FRAME_ADVANCE {frames}")

    def run_until_input_required(self) -> BattleState:
        # Simple placeholder: just advance 1 frame
        self.advance_frame(1)
        return self.read_battle_state()

    def read_factory_state(self) -> FactoryState:
        # TODO: Implement factory state reading
        return FactoryState()

    def save_state(self) -> bytes:
        # TODO: Implement save state via BizHawk
        return b""

    def load_state(self, state: bytes) -> None:
        # TODO: Implement load state via BizHawk
        pass

    def reset(self) -> None:
        self._send_command("RESET")

    def get_game_version(self) -> str:
        return "emerald"
