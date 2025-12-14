import sys
import os
import argparse

try:
    import pygame
except ImportError:
    print("Error: PyGame is not installed. Please run 'pip install pygame'.")
    sys.exit(1)

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backends.emerald.mock import MockEmeraldBackend
from src.backends.emerald.constants import PLAYER_PARTY_OFFSET, FACTORY_ROOT
from src.core.knowledge import get_frontier_mon, format_frontier_mon, get_frontier_mon_count

# Constants
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 30

# Colors
BG_COLOR = (25, 25, 35)
TEXT_COLOR = (220, 220, 220)
HIGHLIGHT_COLOR = (100, 200, 255)
SUCCESS_COLOR = (100, 255, 100)
ERROR_COLOR = (255, 100, 100)
MENU_BG = (40, 40, 55)

# Menu Items
MENU_ITEMS = [
    ("1", "Test Button A", "send_a"),
    ("2", "Test Button B", "send_b"),
    ("3", "Test D-Pad Up", "send_up"),
    ("4", "Test D-Pad Down", "send_down"),
    ("5", "Advance 1 Frame", "frame_1"),
    ("6", "Advance 60 Frames", "frame_60"),
    ("7", "Read Party Memory", "read_party"),
    ("8", "Test PING", "ping"),
    ("9", "Reset Emulator", "reset"),
    ("0", "Clear Log", "clear"),
    ("R", "Read Rental Pokemon (scan)", "read_rental"),
    ("F", "Scan Factory Memory", "scan_factory"),
]

class DebuggerUI:
    def __init__(self, backend, backend_name):
        self.backend = backend
        self.backend_name = backend_name
        self.log_lines = []
        self.max_log_lines = 15
        self.font = None
        self.font_small = None
        
    def init_fonts(self):
        self.font = pygame.font.SysFont("monospace", 18)
        self.font_small = pygame.font.SysFont("monospace", 14)
        
    def log(self, msg, color=TEXT_COLOR):
        self.log_lines.append((msg, color))
        if len(self.log_lines) > self.max_log_lines:
            self.log_lines.pop(0)
            
    def clear_log(self):
        self.log_lines = []
        
    def execute_action(self, action):
        try:
            if action == "send_a":
                self.backend.inject_action(1)
                self.log("Sent: Button A (mask=1)", SUCCESS_COLOR)
            elif action == "send_b":
                self.backend.inject_action(2)
                self.log("Sent: Button B (mask=2)", SUCCESS_COLOR)
            elif action == "send_up":
                self.backend.inject_action(7)
                self.log("Sent: D-Pad Up (mask=64)", SUCCESS_COLOR)
            elif action == "send_down":
                self.backend.inject_action(8)
                self.log("Sent: D-Pad Down (mask=128)", SUCCESS_COLOR)
            elif action == "frame_1":
                self.backend.advance_frame(1)
                self.log("Advanced 1 frame", SUCCESS_COLOR)
            elif action == "frame_60":
                self.backend.advance_frame(60)
                self.log("Advanced 60 frames (~1 second)", SUCCESS_COLOR)
            elif action == "read_party":
                resp = self.backend._send_command(f"READ_BLOCK {PLAYER_PARTY_OFFSET:X} 64")
                if resp.startswith("ERROR"):
                    self.log(f"Read failed: {resp}", ERROR_COLOR)
                else:
                    self.log(f"Read {len(resp)//2} bytes from 0x{PLAYER_PARTY_OFFSET:X}", SUCCESS_COLOR)
                    # Show first 32 hex chars
                    self.log(f"  Data: {resp[:32]}...", TEXT_COLOR)
            elif action == "ping":
                resp = self.backend._send_command("PING")
                if resp == "PONG":
                    self.log("PING -> PONG (connection OK)", SUCCESS_COLOR)
                else:
                    self.log(f"PING -> {resp} (unexpected)", ERROR_COLOR)
            elif action == "reset":
                self.backend.reset()
                self.log("Sent RESET command", SUCCESS_COLOR)
            elif action == "clear":
                self.clear_log()
            elif action == "read_rental":
                # Read from potential rental Pokemon memory locations
                # The FRONTIER_MON ID is typically 2 bytes (u16)
                # Try reading from various Factory-related offsets
                scan_addr = 0x0203CF30  # Approximate rental display cursor area
                resp = self.backend._send_command(f"READ_BLOCK {scan_addr:X} 10")
                if not resp.startswith("ERROR") and resp != "TIMEOUT":
                    self.log(f"Rental area @ 0x{scan_addr:X}:", HIGHLIGHT_COLOR)
                    # Parse as u16 values
                    for i in range(0, min(len(resp), 20), 4):
                        val = int(resp[i:i+4], 16) if len(resp) >= i+4 else 0
                        # Swap bytes for little endian
                        val_le = ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)
                        mon = get_frontier_mon(val_le) if val_le < 900 else None
                        name = mon['species_name'] if mon else "???"
                        self.log(f"  [{i//4}] ID={val_le:3d} -> {name}", TEXT_COLOR)
                else:
                    self.log(f"Read failed: {resp}", ERROR_COLOR)
            elif action == "scan_factory":
                # Scan Factory root area for interesting values
                self.log(f"Scanning Factory @ 0x{FACTORY_ROOT:X}...", HIGHLIGHT_COLOR)
                resp = self.backend._send_command(f"READ_BLOCK {FACTORY_ROOT:X} 20")
                if not resp.startswith("ERROR") and resp != "TIMEOUT":
                    self.log(f"  Raw: {resp[:40]}", TEXT_COLOR)
                    # Parse first few bytes
                    if len(resp) >= 8:
                        round_num = int(resp[0:2], 16)
                        self.log(f"  Round?: {round_num}", TEXT_COLOR)
                else:
                    self.log(f"Read failed: {resp}", ERROR_COLOR)
        except Exception as e:
            self.log(f"Error: {e}", ERROR_COLOR)
            
    def draw(self, screen):
        screen.fill(BG_COLOR)
        
        # Title
        title = self.font.render(f"mGBA Backend Tester - {self.backend_name}", True, HIGHLIGHT_COLOR)
        screen.blit(title, (20, 15))
        
        # Menu Box
        menu_rect = pygame.Rect(20, 50, 350, 300)
        pygame.draw.rect(screen, MENU_BG, menu_rect, border_radius=8)
        pygame.draw.rect(screen, HIGHLIGHT_COLOR, menu_rect, 2, border_radius=8)
        
        menu_title = self.font.render("Test Menu (Press Key)", True, TEXT_COLOR)
        screen.blit(menu_title, (30, 60))
        
        y = 90
        for key, label, _ in MENU_ITEMS:
            text = self.font_small.render(f"[{key}] {label}", True, TEXT_COLOR)
            screen.blit(text, (40, y))
            y += 25
            
        # Log Box
        log_rect = pygame.Rect(390, 50, 390, 530)
        pygame.draw.rect(screen, MENU_BG, log_rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 120), log_rect, 2, border_radius=8)
        
        log_title = self.font.render("Output Log", True, TEXT_COLOR)
        screen.blit(log_title, (400, 60))
        
        y = 90
        for msg, color in self.log_lines:
            # Truncate long messages
            display_msg = msg[:45] + "..." if len(msg) > 45 else msg
            text = self.font_small.render(display_msg, True, color)
            screen.blit(text, (400, y))
            y += 22
            
        # Controls Help
        help_text = self.font_small.render("ESC=Quit | Keys 0-9 = Run Test", True, (120, 120, 140))
        screen.blit(help_text, (20, WINDOW_HEIGHT - 25))
        
        # Connection Status
        status = self.font_small.render(f"Backend: {self.backend_name} | Connected", True, SUCCESS_COLOR)
        screen.blit(status, (WINDOW_WIDTH - 280, WINDOW_HEIGHT - 25))


def main():
    parser = argparse.ArgumentParser(description="Pokemon Live Debugger")
    parser.add_argument("--rom", type=str, default="test.gba", help="Path to ROM file")
    parser.add_argument("--mock", action="store_true", help="Force use of Mock Backend")
    parser.add_argument("--backend", type=str, choices=["mock", "bizhawk", "mgba"], default="mgba",
                        help="Backend to use: mock, bizhawk, or mgba (default: mgba)")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Pokemon Battle Factory - Backend Tester")
    clock = pygame.time.Clock()

    # Backend Selection
    backend = None
    backend_name = "Unknown"
    use_mock = args.mock or args.backend == "mock"
    
    if use_mock:
        print("Using MOCK Backend.")
        backend = MockEmeraldBackend(args.rom)
        backend_name = "Mock"
    elif args.backend == "mgba":
        print("Using mGBA Backend.")
        try:
            from src.backends.mgba.backend import MGBABackend
            backend = MGBABackend(args.rom)
            backend_name = "mGBA"
        except ImportError as e:
            print(f"Failed to import MGBABackend: {e}")
            use_mock = True
    elif args.backend == "bizhawk":
        print("Using BizHawk Backend.")
        from src.backends.bizhawk.backend import BizHawkBackend
        backend = BizHawkBackend(args.rom)
        backend_name = "BizHawk"
    
    if use_mock and backend is None:
        backend = MockEmeraldBackend(args.rom)
        backend_name = "Mock"

    try:
        backend.connect(args.rom)
    except Exception as e:
        print(f"Failed to connect: {e}")
        if not use_mock:
            print("Falling back to Mock Backend...")
            backend = MockEmeraldBackend(args.rom)
            backend_name = "Mock (fallback)"
            backend.connect(args.rom)

    # Create UI
    ui = DebuggerUI(backend, backend_name)
    ui.init_fonts()
    ui.log(f"Connected to {backend_name} backend", SUCCESS_COLOR)
    ui.log("Press number keys to run tests", TEXT_COLOR)

    # Key to action mapping
    key_actions = {
        pygame.K_1: "send_a",
        pygame.K_2: "send_b",
        pygame.K_3: "send_up",
        pygame.K_4: "send_down",
        pygame.K_5: "frame_1",
        pygame.K_6: "frame_60",
        pygame.K_7: "read_party",
        pygame.K_8: "ping",
        pygame.K_9: "reset",
        pygame.K_0: "clear",
        pygame.K_r: "read_rental",
        pygame.K_f: "scan_factory",
    }

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in key_actions:
                    ui.execute_action(key_actions[event.key])
        
        ui.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()

if __name__ == "__main__":
    main()
