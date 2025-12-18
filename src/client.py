import socket
import time
import logging

logger = logging.getLogger(__name__)

class MgbaClient:
    """Client for communicating with the mGBA Lua connector.
    
    This client communicates with a running instance of mGBA that has the `connector.lua`
    script loaded. It sends text-based commands over a TCP socket and receives results.
    """

    def __init__(self, host='localhost', port=7777):
        """Initializes the mGBA client configuration.

        Args:
            host (str): Hostname of the mGBA instance (default: 'localhost').
            port (int): Port number (default: 7777).
        """
        self.host = host
        self.port = port
        self.sock = None

    def connect(self) -> None:
        """Establishes functionality connection to the mGBA server.
        
        Raises:
            ConnectionRefusedError: If the connection fails (e.g. emulator not running).
        """
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

    def disconnect(self) -> None:
        """Closes the active connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
            logger.info("Disconnected from mGBA")

    def _send(self, cmd: str) -> str:
        """Sends a raw text command to the Lua script and awaits a response.

        Args:
            cmd (str): The command string (e.g., "READ_U16 020244EC").

        Returns:
            str: The raw response string, trimmed of whitespace.

        Raises:
            RuntimeError: If not connected.
            socket.error: On I/O failure.
        """
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
        """Checks connection vitality."""
        resp = self._send("PING")
        return resp == "PONG"

    def read_u8(self, addr: int) -> int:
        """Reads an unsigned 8-bit integer from memory."""
        # Client side implementation using READ_BLOCK for single byte since lua might not have READ_U8
        resp = self._send(f"READ_BLOCK {addr:X} 1")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp, 16)

    def read_u16(self, addr: int) -> int:
        """Reads an unsigned 16-bit integer from memory."""
        resp = self._send(f"READ_U16 {addr:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp)

    def read_u32(self, addr: int) -> int:
        """Reads an unsigned 32-bit integer from memory."""
        resp = self._send(f"READ_U32 {addr:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return int(resp)

    def read_block(self, addr: int, size: int) -> bytes:
        """Reads a contiguous block of memory.

        Args:
            addr (int): Start address.
            size (int): Number of bytes to read.

        Returns:
            bytes: The read byte data.
        """
        resp = self._send(f"READ_BLOCK {addr:X} {size:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at {addr:X}: {resp}")
        return bytes.fromhex(resp)

    def read_ptr(self, ptr_addr: int, offset: int, size: int) -> bytes:
        """Reads data from a pointer plus offset.

        Logic: Target Address = dereference(ptr_addr) + offset.

        Args:
            ptr_addr (int): Address of the pointer itself.
            offset (int): Offset to add to the dereferenced pointer.
            size (int): Number of bytes to read.
        """
        resp = self._send(f"READ_PTR {ptr_addr:X} {offset:X} {size:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at ptr {ptr_addr:X} + {offset:X}: {resp}")
        return bytes.fromhex(resp)

    def read_ptr_u16(self, ptr_addr: int, offset: int) -> int:
        """Reads a u16 from a pointer plus offset."""
        resp = self._send(f"READ_PTR_U16 {ptr_addr:X} {offset:X}")
        if "ERROR" in resp: raise ValueError(f"Read error at ptr {ptr_addr:X} + {offset:X}: {resp}")
        return int(resp)

    def input_waiting(self) -> bool:
        """Checks if the emulator is waiting for input (WaitFrame)."""
        resp = self._send("IS_WAITING_INPUT")
        return resp == "YES"

    def get_battle_outcome(self) -> int:
        """Specific command to check battle outcome status."""
        resp = self._send("GET_BATTLE_OUTCOME")
        return int(resp)
