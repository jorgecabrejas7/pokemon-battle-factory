#!/bin/bash
# Launches BizHawk from the local install

WORK_DIR=$(pwd)
BIZHAWK_DIR="$WORK_DIR/third_party/bizhawk"

if [ ! -d "$BIZHAWK_DIR" ]; then
    echo "BizHawk not found. Run './tools/setup_bizhawk.sh' first."
    exit 1
fi

cd "$BIZHAWK_DIR"
./EmuHawkMono.sh
