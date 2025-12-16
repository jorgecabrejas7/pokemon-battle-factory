import struct

def decrypt_data(data: bytes, key: int) -> bytes:
    """
    Decrypts data using a 32-bit key (XOR).
    Data length must be a multiple of 4.
    """
    decrypted = bytearray()
    for i in range(0, len(data), 4):
        chunk = struct.unpack('<I', data[i:i+4])[0]
        decrypted_chunk = chunk ^ key
        decrypted.extend(struct.pack('<I', decrypted_chunk))
    return bytes(decrypted)

def get_substructure_order(pid: int) -> list:
    """
    Returns the order of substructures (G, A, E, M) based on PID % 24.
    0 = Growth, 1 = Attacks, 2 = EVs, 3 = Misc
    """
    orders = [
        [0, 1, 2, 3], [0, 1, 3, 2], [0, 2, 1, 3], [0, 2, 3, 1], [0, 3, 1, 2], [0, 3, 2, 1],
        [1, 0, 2, 3], [1, 0, 3, 2], [1, 2, 0, 3], [1, 2, 3, 0], [1, 3, 0, 2], [1, 3, 2, 0],
        [2, 0, 1, 3], [2, 0, 3, 1], [2, 1, 0, 3], [2, 1, 3, 0], [2, 3, 0, 1], [2, 3, 1, 0],
        [3, 0, 1, 2], [3, 0, 2, 1], [3, 1, 0, 2], [3, 1, 2, 0], [3, 2, 0, 1], [3, 2, 1, 0],
    ]
    return orders[pid % 24]

def unshuffle_substructures(data: bytes, pid: int) -> bytes:
    """
    Unshuffles the 48 bytes of substructure data into standard GAEM order.
    Input data must be 48 bytes (4 blocks * 12 bytes).
    Standard Order: Growth (0), Attacks (1), EVs (2), Misc (3).
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
    
    # We want to arrange them such that result is [Block 0][Block 1][Block 2][Block 3]
    # 'order' tells us which block type is at which position in the *source*
    # order[0] is the type of the first block in 'data'.
    
    ordered_blocks = [b'', b'', b'', b'']
    
    for i, block_type in enumerate(order):
        ordered_blocks[block_type] = blocks[i]
        
    return b''.join(ordered_blocks)

def verify_checksum(substructures: bytes, original_checksum: int) -> bool:
    """
    Verifies the checksum of the decrypted substructures.
    Sum of all 16-bit words (24 words) must match the checksum.
    """
    total = 0
    for i in range(0, len(substructures), 2):
        word = struct.unpack('<H', substructures[i:i+2])[0]
        total = (total + word) & 0xFFFF
    
    return total == original_checksum
