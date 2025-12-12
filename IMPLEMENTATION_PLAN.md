# Pokémon Battle Factory: Hierarchical RL Implementation Plan

> **Primary Target:** Pokémon Emerald (Gen 3)  
> **Secondary Target:** Pokémon Platinum (Gen 4)  
> **Architecture:** Abstraction-First Hierarchical RL solving a POMDP

---

## Phase 1: Core Abstraction Layer (The "Bridge")

*Define Python protocols that decouple agents from ROM-specific implementation.*

### 1.1 Data Structures `[DEV]`


#### 1.1.1 Pokemon Dataclasses
- **RentalPokemon:** Represents a rental selection (Initial Draft).
  - Concrete/Fixed Stats: `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`, `speed` (Values are known).
  - Inheritance: `BasePokemon` + Concrete Stats + Moves.
- **PlayerPokemon:** Represents a party member.
  - Dynamic State: `current_hp`, `status_condition`, `is_confused`, `stat_stages`, `volatile_status`.
  - Inheritance: Extends `RentalPokemon`.
- **EnemyPokemon:** Represents an opponent or Swap Candidate.
  - Partial Info: relying on Species Base Stats for estimation.
  - Visible: `species_id`, `nickname`, `level`
  - Estimates: `hp_percentage`, `predicted_item`, `revealed_moves`.


#### 1.1.2 Move Dataclass
- **Fields:** `move_id`, `name`, `type_id`, `category` (Physical/Special/Status)
- **Power:** `base_power`, `accuracy`, `priority`
- **Effects:** `effect_id`, `effect_chance`, `target_type`

#### 1.1.3 BattleState Dataclass
- **Player Side:** `active_pokemon: Pokemon`, `party: List[Pokemon]`, `side_conditions`
- **Enemy Side:** `active_pokemon: Pokemon`, `revealed_party: List[Pokemon]`, `side_conditions`
- **Field:** `weather`, `terrain`, `turn_count`
- **Flags:** `is_waiting_for_input`, `available_actions: List[int]`

#### 1.1.4 FactoryState Dataclass
- **Context:** `current_round`, `current_battle`, `win_streak`
- **Draft Info:** `rental_pool: List[Pokemon]`, `current_team: List[Pokemon]`
- **Hints:** `scientist_hint_id`, `hint_payload` (varies by round)
- **Screen:** `screen_type` enum (DRAFT, SWAP, BATTLE, RESULT)

### `src/backends/bizhawk`
#### [NEW] [backend.py](file:///home/apollo/Dev/pokemon-battle-factory/src/backends/bizhawk/backend.lua)
- Implement `BizHawkBackend` class inheriting from `BattleBackend`.
- **Communication:** Uses Python `socket` to connect to localhost port (default: 9999).
- **Protocol:** JSON-based or simple text protocol.
    - `READ <ADDR> <LEN>` -> Returns bytes.
    - `WRITE <ADDR> <VAL>` -> Writes bytes.
    - `FRAME <COUNT>` -> Advances emulator.
    - `INPUT <BUTTONS>` -> Sets input state.

#### [NEW] [connector.lua](file:///home/apollo/Dev/pokemon-battle-factory/src/backends/bizhawk/connector.lua)
- Lua script to be loaded in BizHawk.
- Opens a TCP server.
- Loops waiting for commands, executes them (reading memory/setting input), and responds.

### `src/core`
#### [MODIFY] [factory.py](file:///home/apollo/Dev/pokemon-battle-factory/src/core/factory.py)
- Update factory to interpret `backend_type="bizhawk"`.

### 1.2 Abstract Backend Protocol `[DEV]`
*Interface for emulator communication.*
- `connect(rom_path, save_state)`
- `read_state() -> BattleState`
- `inject_action(action_id)`
- `reset()`
- **Synchronization:** `run_until_input_required() -> BattleState` (Crucial: Fast-forwards emulator, skipping text/animations until agent decision is needed).

```python
# protocols/backend.py
from abc import ABC, abstractmethod
from typing import List, Optional
from .dataclasses import Pokemon, BattleState, FactoryState

class BattleBackend(ABC):
    """Abstract interface for emulator communication."""
    
    @abstractmethod
    def connect(self, rom_path: str, save_state: Optional[str] = None) -> None:
        """Initialize emulator with ROM and optional save state."""
    
    @abstractmethod
    def read_battle_state(self) -> BattleState:
        """Extract current battle state from RAM."""
    
    @abstractmethod
    def read_factory_state(self) -> FactoryState:
        """Extract Factory-specific state (draft pool, hints, etc.)."""
    
    @abstractmethod
    def inject_action(self, action_id: int) -> None:
        """Send button press to emulator."""
    
    @abstractmethod
    def advance_frame(self, frames: int = 1) -> None:
        """Step emulator forward N frames."""
    
    @abstractmethod
    def save_state(self) -> bytes:
        """Serialize current emulator state."""
    
    @abstractmethod
    def load_state(self, state: bytes) -> None:
        """Restore emulator to saved state."""
    
    @abstractmethod
    def reset(self) -> None:
        """Reset to initial Factory challenge state."""
    
    @abstractmethod
    def get_game_version(self) -> str:
        """Return 'emerald' or 'platinum'."""
```

### 1.3 Knowledge Base (Static Data) `[DEV]`

- `[DEV]` **Source of Truth:** Write parsers for `pret/pokeemerald` (C source files) to extract Base Stats and Move Data directly from the decompilation rather than web scraping.
- `[DEV]` **Database Schema:** SQLite tables for `species`, `moves`, `type_chart`, and `factory_sets`.
- `[DEV]` **Gen 4 Compat:** Ensure schema supports "Physical/Special Split" (Gen 4) vs "Type-based Categories" (Gen 3).

---

## Phase 2: Gen 3 (Emerald) Backend Implementation

### 2.1 Headless Emulator Setup `[DEV]`

### 2.1 Headless Emulator Setup `[DEV]`
- `[RESEARCH]` Evaluate `mgba-py` vs `gym-retro`. Select one that supports direct memory access without a GUI.
- `[DEV]` Implement `EmeraldBackend(BattleBackend)`.
- `[DEV]` Implement `InputHandler`: Map `ACTION_MOVE_1` -> `[PRESS_A, PRESS_A]` logic.

#### 2.1.2 Input Mapping
```python
BUTTONS = {
    'A': 0x001, 'B': 0x002, 'SELECT': 0x004, 'START': 0x008,
    'RIGHT': 0x010, 'LEFT': 0x020, 'UP': 0x040, 'DOWN': 0x080,
    'R': 0x100, 'L': 0x200
}
```

### 2.2 Memory Map (RAM Forensics) `[RESEARCH]`
*Verify offsets against pokeemerald symbol files.*
- `0x020244EC`: Player Party (600 bytes).
- `0x0202402C`: Enemy Party (Generated pre-battle).
- `0x02023E4C`: Battle Flags (Input waiting).
- `TBD`: Factory Rental Pool location (for Drafting Agent).
- `TBD`: Scientist Hint ID location (for Gen 4 logic).

| Data | Offset | Size | Notes |
|------|--------|------|-------|
| Player Party | `0x020244EC` | 600 bytes | 6 Pokemon × 100 bytes |
| Enemy Party | `0x0202402C` | 600 bytes | Generated pre-battle |
| Battle Data | `0x02023BE4` | ~1KB | Active stats/stages |
| Current HP (Player) | `0x02023BF0` | 2 bytes | Per slot |
| Current HP (Enemy) | `0x02023C40` | 2 bytes | Per slot |
| Weather | `0x02023F1C` | 1 byte | 0=None, 1=Rain, etc. |
| Turn Counter | `0x02023E82` | 1 byte | Current turn |
| Factory Round | `0x02039A00` | 1 byte | `[RESEARCH]` Verify |
| Factory Streak | `0x02039A04` | 2 bytes | `[RESEARCH]` Verify |
| Rental Pool | `TBD` | ~600 bytes | `[RESEARCH]` Find |
| Scientist Hint | `TBD` | Variable | `[RESEARCH]` Find |
| Input Wait Flag | `0x030030F0` | 1 byte | `[RESEARCH]` Verify |

#### 2.2.1 Research Tasks
- `[RESEARCH]` Verify offsets against pret/pokeemerald decompilation
- `[RESEARCH]` Map 100-byte Pokemon data structure (PV, encryption, sub-blocks)
- `[RESEARCH]` Find "awaiting player input" flag
- `[RESEARCH]` Locate Factory rental pool generation

### 2.3 State Decoder `[DEV]`

- `[DEV]` Pokemon decoder: PV extraction, data block decryption, stat parsing
- `[DEV]` Battle state decoder: stat stages, status, PP
- `[DEV]` Factory context decoder: screen detection, rental pool parsing

---

## Phase 3: Feature Engineering (State Space)

### 3.1 Feature Extractor Class `[DEV]`

#### 3.1.1 Embedding Vocabularies
```python
VOCAB_SIZES = {
    'species': 494, 'moves': 468, 'abilities': 124,
    'items': 377, 'types': 18, 'natures': 25, 'status': 7
}
EMBEDDING_DIM = 64
```

#### 3.1.2 Pokemon Feature Vector (~400 dims)
- Categorical embeddings: species, ability, item, 4 moves
- Numerical: normalized stats, HP ratio, status one-hot, stat stages

### 3.2 History Tracker `[DEV]`

- `[DEV]` Move history buffer: `{species_id: {move_id: count}}`
- `[DEV]` Battle history encoder: sliding window of N turns
- `[DEV]` Recurrent format: `[batch, seq_len, features]`

### 3.3 Hint Encoder `[DEV]`

| Round | Hint Level | Encoding |
|-------|-----------|----------|
| 1-2 | None | Uniform prior |
| 3-4 | Type Hint | Type probability mask |
| 5-6 | Pokemon Hint | Species one-hot |
| 7+ | Full Reveal | Complete team encoding |

---

## Phase 4: Model & Agent Implementation

### 4.1 Drafting Network (Transformer) `[DEV]`

```
Input: Candidates [N×dim] + Team [3×dim] + Hint [hint_dim]
  → Pokemon Encoder MLP [256]
  → Set Transformer (4 heads, permutation invariant)
  → Cross-Attention (Team ↔ Candidates)
  → Pointer Network Head
Output: Selection probabilities
```

- `[DEV]` Implement `PokemonEncoder`, `SetTransformer`, `PointerHead`
- `[DEV]` Action masking for valid selections

### 4.2 Battle Network (LSTM) `[DEV]`

```
Input: Self [dim] + Enemy [dim] + Field + Action Mask
  → State Encoder MLP [512]
  → LSTM (2 layers, 512 hidden)
  → Actor Head: π(a|s) [6 outputs]
  → Critic Head: V(s) [1 output]
```

- `[DEV]` Implement `RecurrentPPOAgent`
- `[DEV]` Hidden state management, action masking

### 4.3 Orchestrator `[DEV]`

```python
class FactoryOrchestrator:
    def step(self):
        state = self.backend.read_factory_state()
        if state.screen_type == DRAFT:
            action = self.draft_agent.select_team(...)
        elif state.screen_type == BATTLE:
            action, hidden = self.battle_agent.act(...)
        # ...
```

---

## Phase 5: Training Pipeline & DevOps

### 5.1 Gymnasium Environment `[DEV]`

```python
class EmeraldFactoryEnv(gym.Env):
    observation_space = spaces.Dict({
        'phase': spaces.Discrete(4),
        'team': spaces.Box(0, 1, shape=(3, 400)),
        'candidates': spaces.Box(0, 1, shape=(6, 400)),
        'battle_state': spaces.Box(0, 1, shape=(1024,)),
        'action_mask': spaces.MultiBinary(6)
    })
    action_space = spaces.Discrete(10)
```

#### Reward Functions
- **Battle:** `+damage_dealt`, `-damage_taken`, `+faint_enemy`, `-faint_self`, `+win`
- **Draft:** `+1 + 0.1*streak` for win, `-1` for loss

### 5.2 Vectorization `[DEV]`

- `[DEV]` `SubprocVecEnv` with 16+ parallel emulators
- `[DEV]` Memory optimization, serialization
- Target: 1000+ steps/sec

### 5.3 Curriculum Learning `[DEV]`

| Stage | Objective | Setup | Success Metric |
|-------|-----------|-------|----------------|
| 1 | Battle fundamentals | Random teams, no draft | 80% win rate |
| 2 | Team synergy | Frozen battle agent | Avg streak > 14 |
| 3 | Joint training | Both agents trainable | Beat Factory Brain (streak 21+) |

### 5.4 Logging `[DEV]`

- TensorBoard/W&B integration
- Checkpoint management
- Replay buffer for analysis

---

## Phase 6: Gen 4 (Platinum) Migration Path

### 6.1 Backend Updates

| Task | Type | Description |
|------|------|-------------|
| NDS Emulator | `[RESEARCH]` | Evaluate DeSmuME/melonDS bindings |
| PRNG Decryption | `[RESEARCH]` | Gen 4 encrypted party data |
| Memory Map | `[RESEARCH]` | Platinum RAM offsets |
| PlatinumBackend | `[DEV]` | Implement `BattleBackend` |

### 6.2 Knowledge Base Updates `[DEV]`

- Add 107 new species (387-493)
- Add 113 new moves (355-467)
- New abilities, Platinum Factory sets

### 6.3 Physical/Special Split `[DEV]`

> Gen 4 introduced per-move categories (Gen 3 was type-based)

- Update move encoding with category flag
- Retrain models for new damage patterns

---

## Appendix A: File Structure

```
pokemon-battle-factory/
├── src/
│   ├── core/           # Dataclasses, protocols, enums
│   ├── backends/       # EmeraldBackend, memory decoders
│   ├── features/       # Extractor, embeddings, history
│   ├── agents/         # DraftAgent, BattleAgent, networks
│   ├── envs/           # Gymnasium environments
│   └── training/       # Training scripts, curriculum
├── data/               # SQLite KB, JSON data
├── tests/
└── scripts/            # Memory verification, benchmarks
```

## Appendix B: Dependencies

```
torch>=2.0, gymnasium>=0.29, stable-baselines3>=2.0
sqlalchemy, pydantic>=2.0, numpy, tensorboard, wandb
pytest, black, mypy
```

## Appendix C: Research References

- [pret/pokeemerald](https://github.com/pret/pokeemerald) - Decompilation
- [Bulbapedia RAM Map](https://bulbapedia.bulbagarden.net/wiki/Pokémon_data_structure_(Generation_III))
- Set Transformer, Pointer Networks, Recurrent PPO papers

## Appendix D: Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| RAM offsets incorrect | Medium | High | Cross-reference sources; runtime validation |
| Headless FPS too slow | Low | High | Profile bottlenecks |
| Reward too sparse | Medium | Medium | Curriculum + shaping |
| Gen 4 encryption complex | Medium | Medium | Defer; focus Gen 3 |
