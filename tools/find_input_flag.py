#!/usr/bin/env python3
"""
Tool to find the 'Input Needed' memory flag in Pokemon Emerald.

Usage:
    1. Start the script: python tools/find_input_flag.py
    2. In the emulator:
       - State A: Wait at the 'Fight/Run' menu (Input IS needed).
       - Press Enter in this script to capture State A.
    3. In the emulator:
       - State B: Select a move and watch an animation (Input IS NOT needed).
       - Press Enter in this script to capture State B.
    4. The script will output memory addresses that changed from [Non-Zero] to [Zero] (or specific patterns).
"""
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.backends.emerald.backend import EmeraldBackend

def scan_memory():
    print("Initializing Backend...")
    try:
        backend = EmeraldBackend()
        backend.connect('/home/apollo/Dev/pokemon-battle-factory/roms/Pokemon Emerald (USA).gba')
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    # Range to scan: Around known battle flags (0x02023E00 - 0x02024000)
    START_ADDR = 0x02023E00
    SIZE = 0x200 # 512 bytes

    print(f"\nScanning range: 0x{START_ADDR:X} - 0x{START_ADDR+SIZE:X}")

    input("1. Go to 'Fight/Run' menu in game (Input Needed). Press Enter when ready...")
    state_a = backend.memory._read_block(START_ADDR, SIZE)
    print("Captured State A.")

    input("2. Select a move so animation plays (Input NOT Needed). Press Enter IMMEDIATELY...")
    state_b = backend.memory._read_block(START_ADDR, SIZE)
    print("Captured State B.")

    print("\n--- Candidates for 'Input Needed' Flag ---")
    print("(Looking for values that are Non-Zero in State A and Zero in State B)")

    candidates = []
    
    for i in range(SIZE):
        val_a = state_a[i]
        val_b = state_b[i]
        
        addr = START_ADDR + i
        
        # Criteria: High in A, Low in B
        if val_a != 0 and val_b == 0:
            print(f"Address 0x{addr:X}: {val_a} -> {val_b} (Potential Match)")
            candidates.append(addr)
        elif val_a != val_b:
            # Just changed
            # print(f"Address 0x{addr:X}: {val_a} -> {val_b} (Changed)")
            pass

    print(f"\nFound {len(candidates)} candidates.")
    
    # 0x02023E4C check
    known_offset = 0x02023E4C
    idx = known_offset - START_ADDR
    if 0 <= idx < SIZE:
        print(f"\nCheck Known Offset 0x{known_offset:X}: {state_a[idx]} -> {state_b[idx]}")

if __name__ == "__main__":
    scan_memory()
