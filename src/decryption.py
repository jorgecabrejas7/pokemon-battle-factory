import struct

"""
Gen 3 Pokémon Encryption Logic.

Ref: https://bulbapedia.bulbagarden.net/wiki/Pok%C3%A9mon_data_structure_(Generation_III)

Key components:
1. Data shuffling based on Personality Value (PID).
2. XOR Encryption with a 32-bit key.
3. Checksum verification.
"""

def decrypt_data(data: bytes, key: int) -> bytes:
    """Decrypts a block of Pokémon data using a 32-bit XOR key.

    Args:
        data (bytes): The encrypted byte buffer (length must be multiple of 4).
        key (int): The 32-bit decryption key.

    Returns:
        bytes: The decrypted data.
    """
    decrypted = bytearray()
    for i in range(0, len(data), 4):
        chunk = struct.unpack('<I', data[i:i+4])[0]
        decrypted_chunk = chunk ^ key
        decrypted.extend(struct.pack('<I', decrypted_chunk))
    return bytes(decrypted)

def get_substructure_order(pid: int) -> list:
    """Determines the permutation order of substructures.

    The 48-byte data block is divided into 4 substructures (G, A, E, M) of 12 bytes.
    The order depends on PID % 24.

    Args:
        pid (int): Personality Value.

    Returns:
        list: A list of 4 integers representing the order (0=Growth, 1=Attacks, 2=EVs, 3=Misc).
    """
    # 0 = Growth, 1 = Attacks, 2 = EVs, 3 = Misc
    orders = [
        [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 2, 3, 1], [0, 3, 1, 2], [0, 3, 2, 1],
        [1, 0, 2, 3], [1, 0, 3, 2], [1, 2, 0, 3], [1, 2, 3, 0], [1, 3, 0, 2], [1, 3, 2, 0],
        [2, 0, 1, 3], [2, 0, 3, 1], [2, 1, 0, 3], [2, 1, 3, 0], [2, 3, 0, 1], [2, 3, 1, 0],
        [3, 0, 1, 2], [3, 0, 2, 1], [3, 1, 0, 2], [3, 1, 2, 0], [3, 2, 0, 1], [3, 2, 1, 0],
    ]
    return orders[pid % 24]

def unshuffle_substructures(data: bytes, pid: int) -> bytes:
    """Reorders the shuffled substructures into the standard 'GAEM' order.

    Standard Order (after unshuffling):
    - Block 0: Growth (Species, EXP, etc.)
    - Block 1: Attacks (Moves, PP)
    - Block 2: EVs & Condition
    - Block 3: Misc (Pokerus, Met Location, IVs)

    Args:
        data (bytes): The 48-byte decrypted data block.
        pid (int): Personality Value used to determine shuffle order.

    Returns:
        bytes: The 48-byte data block in standard order.

    Raises:
        ValueError: If data length is not 48 bytes.
    """
    if len(data) != 48:
        raise ValueError(f"Substructure data must be 48 bytes, got {len(data)}")

    order = get_substructure_order(pid)
    blocks = [
        data[0:12],
        data[12:24],
        data[24:36],
        data[36:48]
    ]
    
    ordered_blocks = [b'', b'', b'', b'']
    
    for i, block_type in enumerate(order):
        ordered_blocks[block_type] = blocks[i]
        
    return b''.join(ordered_blocks)

def verify_checksum(substructures: bytes, original_checksum: int) -> bool:
    """Verifies that the decrypted data matches its checksum.

    The checksum is the sum of all 16-bit words in the unencrypted substructures.

    Args:
        substructures (bytes): The 48-byte decrypted substructure data.
        original_checksum (int): The 16-bit checksum read from the Pokémon struct.

    Returns:
        bool: True if checksum calculates correctly.
    """
    total = 0
    for i in range(0, len(substructures), 2):
        word = struct.unpack('<H', substructures[i:i+2])[0]
        total = (total + word) & 0xFFFF
    
    return total == original_checksum
