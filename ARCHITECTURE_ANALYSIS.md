# Architecture Analysis: Pokémon Battle Factory Observer

This document provides a comprehensive analysis of the architecture found in the `pokemon-battle-factory` repository. The system is designed to interface with a running Pokémon Emerald instance via mGBA, reading raw memory to reconstruct the game state for observation and eventually reinforcement learning agents.

## 1. High-Level Architecture

The system follows a typical **Observer pattern** where a Python client polls a Lua socket server running inside the mGBA emulator. The application is layered into:

1.  **Communication Layer**: Raw socket TCP communication with mGBA.
2.  **Memory Abstraction Layer**: Converts raw hex addresses/blocks into Python objects.
3.  **Data Models**: Structured representations of game entities (Pokémon, Move, Battle State).
4.  **Database/Knowledge Layer**: Static game data (names of moves, items, species) retrieved from a SQLite database.
5.  **Application Entry**: A main loop that orchestrates the polling and display of data.

## 2. Component Chaining & Data Flow

The data flows from the Emulator to the User/Agent in the following chain:

```mermaid
graph TD
    A[mGBA Emulator (Lua Server)] -->|TCP Socket| B[MgbaClient (src/client.py)]
    B -->|Raw Bytes| C[MemoryReader (src/memory.py)]
    D[SQLite Database (src/db.py)] -->|Static Metadata| C
    E[Decryption Utils (src/decryption.py)] -->|Logic| C
    C -->|Constructs| F[BattleFactorySnapshot (src/models.py)]
    F -->|Consumed By| G[Main App (src/main.py)]
    G -->|Display| H[Console Output / Agent]
```

1.  **`MgbaClient`** establishes the connection.
2.  **`MemoryReader`** uses the client to request specific memory blocks (e.g., Party RAM, Battle Buffers).
3.  **`MemoryReader`** decrypts the raw data using `src/decryption.py` logic (Gen 3 Pokémon data encryption).
4.  **`MemoryReader`** enriches the data (resolving IDs to Names) using **`PokemonDatabase`**.
5.  **`MemoryReader`** bundles everything into a **`BattleFactorySnapshot`**.
6.  **`main.py`** continuously loops, calling `read_snapshot()` and displaying the result.

---

## 3. Detailed Class & Module Analysis

### 3.1 Data Models (`src/models.py`)
These are pure data containers (dataclasses) representing the game state. They have no dependecies other than standard libraries.

*   **`PartyPokemon`**
    *   **Role**: Represents a Pokémon in the player's party (bench).
    *   **Attributes**: `pid`, `species_id`, `species_name`, `moves` (list), `pp` (list), `hp`, `max_hp`, `level`, `nickname`, `status`, `item_name`.
    *   **Methods**:
        *   `is_fainted`: Property checking if HP == 0.

*   **`BattlePokemon`**
    *   **Role**: Represents a Pokémon currently on the field (active battler). Note: Emerald stores active battlers in a different memory location than the party.
    *   **Attributes**: `slot` (0-3), `species_id`, `hp`, `max_hp`, `level`, `status`, `moves`.
    *   **Methods**:
        *   `pct_hp`: Returns HP percentage (0.0 - 1.0).

*   **`RentalPokemon`**
    *   **Role**: Represents a rental selection or swap option.
    *   **Attributes**: `slot`, `species_id`, `ivs`, `ability_num`, `personality`.

*   **`BattleFactorySnapshot`**
    *   **Role**: The "Single Source of Truth" for the game state at any given frame.
    *   **Attributes**: `phase` (RENTAL/BATTLE), `player_party`, `enemy_party`, `active_battlers`, `rental_candidates`, `last_move_player`, `last_move_enemy`, `outcome`, `input_wait`.

### 3.2 Communication Layer (`src/client.py`)
Handles the low-level IO.

*   **`MgbaClient`**
    *   **Role**: Wrapper around Python's `socket` module to talk to `connector.lua`.
    *   **Attributes**: `host`, `port`, `sock`.
    *   **Methods**:
        *   `connect()` / `disconnect()`: Lifecycle management.
        *   `read_u8`, `read_u16`, `read_u32`: Reads integers of specific widths.
        *   `read_block(addr, size)`: Reads a chunk of memory (returns `bytes`).
        *   `read_ptr*`: Helpers to read pointers (dereferencing addresses).
        *   `input_waiting()`: Checks if the emulator is ready for input.

### 3.3 Memory Logic Layer (`src/memory.py`)
The heaviest module, containing the business logic for interpreting Gen 3 internals.

*   **`MemoryReader`**
    *   **Role**: The bridge between raw bytes and high-level Models.
    *   **Attributes**: 
        *   `client`: Reference to `MgbaClient`.
        *   `db`: Reference to `PokemonDatabase`.
    *   **Methods**:
        *   `read_snapshot()`: **Primary Entry Point**. Calls internal methods to build the full object.
        *   `read_party(address, count)`: Reads 100-byte * Pokemon structs. Handles the complex Personality Substructure shuffling (Growth, Attacks, EVs, Misc).
        *   `read_battle_mons()`: Reads the active battle globals (different offsets than party data).
        *   `read_rental_mons()`: Reads the array of 3 or 6 rental choices.
        *   `_get_status_string()`: Helper to decode bitmasked status conditions (Sleep, Poison, etc.).

### 3.4 Database Layer (`src/db.py`)
Handles static data lookup.

*   **`PokemonDatabase`**
    *   **Role**: Read-only interface to `knowledge_base.db`.
    *   **Methods**:
        *   `get_move_name(id)`: Returns string name (e.g., "Thunderbolt").
        *   `get_species_name(id)`: Returns string name (e.g., "Pikachu").
        *   `get_item_name(id)`: Returns string name (e.g., "Leftovers").

### 3.5 Utilities (`src/decryption.py`)
State-less functional module.

*   **Key Functions**:
    *   `decrypt_data(data, key)`: XOR decryption used by Gen 3 Pokémon data.
    *   `unshuffle_substructures(data, pid)`: Reorders the data blocks (Growth, Attacks, EVs, Misc) based on the Pokémon's PID modulo 24.
    *   `verify_checksum()`: Validates data integrity.

## 4. Execution Entry (`src/main.py`)

The orchestration script that ties it all together:
1.  Instantiates `MgbaClient`.
2.  Instantiates `MemoryReader`.
3.  Enters a `while True` loop.
4.  Calls `memory.read_snapshot()`.
5.  Clears the screen and prints the formatted state.
