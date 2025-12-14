import socket
import logging
from typing import Optional
from ...core.protocols import BattleBackend
from ...core.dataclasses import BattleState, FactoryState
from .decoder import EmeraldDecoder

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

    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        logger.info(f"Connecting to {HOST}:{PORT}...")
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        
        try:
            self.sock.connect((HOST, PORT))
            logger.info("Socket connected, testing with PING...")
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
            logger.debug(f"Sending: {cmd}")
            self.sock.sendall((cmd + "\n").encode('utf-8'))
            data = self.sock.recv(4096).decode('utf-8').strip()
            logger.debug(f"Received: {data}")
            return data
        except socket.timeout:
            logger.warning(f"Command timed out: {cmd}")
            return "ERROR"

    def read_battle_state(self) -> BattleState:
        return BattleState()

    def inject_action(self, action_id: int) -> None:
        """Inject a button press."""
        import time
        mask = self.ACTION_MAP.get(action_id, 0)
        if mask == 0:
            return
        self._send_command(f"SET_INPUT {mask}")
        time.sleep(0.1)  # Hold for ~6 frames
        self._send_command("SET_INPUT 0")

    def advance_frame(self, frames: int = 1) -> None:
        self._send_command(f"FRAME_ADVANCE {frames}")

    def run_until_input_required(self) -> BattleState:
        self.advance_frame(1)
        return self.read_battle_state()

    def read_factory_state(self) -> FactoryState:
        return FactoryState()

    def save_state(self) -> bytes:
        return b""

    def load_state(self, state: bytes) -> None:
        pass

    def reset(self) -> None:
        self._send_command("RESET")

    def get_game_version(self) -> str:
        return "emerald"
