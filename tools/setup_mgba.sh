#!/bin/bash
# Install mGBA on Ubuntu/Debian

echo "=== Installing mGBA ==="
sudo apt update
sudo apt install -y mgba-qt lua-socket

echo ""
echo "=== Installation Complete ==="
echo "Run mGBA with: mgba-qt"
echo ""
echo "To use with the debugger:"
echo "  1. mgba-qt /path/to/your/rom.gba"
echo "  2. Tools -> Scripting -> File -> Load Script"
echo "  3. Select: src/backends/emerald/connector.lua"
echo "  4. python3 tools/live_debugger.py --backend mgba"
