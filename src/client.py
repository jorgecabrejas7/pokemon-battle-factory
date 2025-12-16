import socket
import time
import logging

logger = logging.getLogger(__name__)

class MgbaClient:
    """Client for communicating with the mGBA Lua connector."""

    def __init__(self, host='localhost', port=7777):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        """Establishes connection to the mGBA server."""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to mGBA at {self.host}:{self.port}")
            # Clear any initial banner message
            self.sock.settimeout(0.1)
            try:
                while self.sock.recv(1024): pass
            except socket.timeout:
                pass
            self.sock.settimeout(2.0) # Set reasonable timeout for commands
        except ConnectionRefusedError:
            logger.error("Connection refused. Is mGBA running with connector.lua?")
            raise

    def disconnect(self):
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Disconnected from mGBA")

    def _send(self, cmd: str) -> str:
        if not self.sock:
            raise RuntimeError("Not connected to mGBA")
        
        try:
            self.sock.sendall((cmd + "\n").encode('utf-8'))
            response = self.sock.recv(4096).decode('utf-8').strip()
            # Handle multi-line responses? usage suggests single line responses mostly
            return response
        except socket.timeout:
            logger.error(f"Timeout waiting for response to: {cmd}")
            return "ERROR: Timeout"
        except Exception as e:
            logger.error(f"Socket error: {e}")
            self.disconnect()
            raise

    def ping(self) -> bool:
        resp = self._send("PING")
        return resp == "PONG"

    def read_u8(self, addr: int) -> int:
        # Client side implementation using READ_BLOCK for single byte since lua might not have READ_U8
        # Actually connector.lua has READ_BLOCK, READ_U16, READ_U32. 
        # READ_BLOCK is easiest for arbitrary size. 
        # But wait, connector.lua has a command list: PING, READ_BLOCK, READ_U16, READ_U32...
        # It does NOT have READ_U8. We can use READ_BLOCK addr 1
        resp = self._send(f"READ_BLOCK {addr:X} 1")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp, 16)

    def read_u16(self, addr: int) -> int:
        resp = self._send(f"READ_U16 {addr:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp)

    def read_u32(self, addr: int) -> int:
        resp = self._send(f"READ_U32 {addr:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp)

    def read_block(self, addr: int, size: int) -> bytes:
        resp = self._send(f"READ_BLOCK {addr:X} {size:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return bytes.fromhex(resp)

    def read_ptr(self, ptr_addr: int, offset: int, size: int) -> bytes:
        resp = self._send(f"READ_PTR {ptr_addr:X} {offset:X} {size:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at ptr {ptr_addr:X} + {offset:X}: {resp}")
        return bytes.fromhex(resp)

    def read_ptr_u16(self, ptr_addr: int, offset: int) -> int:
        resp = self._send(f"READ_PTR_U16 {ptr_addr:X} {offset:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at ptr {ptr_addr:X} + {offset:X}: {resp}")
        return int(resp)

    def input_waiting(self) -> bool:
        resp = self._send("IS_WAITING_INPUT")
        return resp == "YES"

    def get_battle_outcome(self) -> int:
        resp = self._send("GET_BATTLE_OUTCOME")
        return int(resp)
