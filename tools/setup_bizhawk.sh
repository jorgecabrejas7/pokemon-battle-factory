#!/bin/bash
# Installs BizHawk into ./third_party/bizhawk

set -e
WORK_DIR=$(pwd)
BIZHAWK_DIR="$WORK_DIR/third_party/bizhawk"
VERSION="2.9.1"

echo "=== Setting up BizHawk ==="

# 1. Create directory
mkdir -p "$WORK_DIR/third_party"

# 2. Download if not exists
if [ ! -d "$BIZHAWK_DIR" ]; then
    echo "Downloading BizHawk $VERSION..."
    cd "$WORK_DIR/third_party"
    wget -q --show-progress "https://github.com/TASEmulators/BizHawk/releases/download/$VERSION/BizHawk-$VERSION-linux-x64.tar.gz"
    tar -xzf "BizHawk-$VERSION-linux-x64.tar.gz"
    mv "BizHawk-$VERSION-linux-x64" bizhawk
    rm "BizHawk-$VERSION-linux-x64.tar.gz"
    chmod +x "$BIZHAWK_DIR/EmuHawkMono.sh"
    echo "BizHawk installed to: $BIZHAWK_DIR"
else
    echo "BizHawk already installed at $BIZHAWK_DIR"
fi

echo ""
echo "=== Setup Complete ==="
echo "Next steps:"
echo "  1. Run BizHawk:  ./tools/run_bizhawk.sh"
echo "  2. Load your ROM in BizHawk"
echo "  3. In BizHawk: Tools -> Lua Console -> Open 'src/backends/bizhawk/connector.lua'"
echo "  4. Run debugger: python3 tools/live_debugger.py"
