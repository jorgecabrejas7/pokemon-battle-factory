# Pokémon Battle Factory: Hierarchical RL Implementation Plan

> **Primary Target:** Pokémon Emerald (Gen 3)  
> **Secondary Target:** Pokémon Platinum (Gen 4)  
> **Architecture:** Abstraction-First Hierarchical RL solving a POMDP  
> **RL Library:** Ray RLlib (preferred over stable-baselines3 for scalability)

---

## Implementation Status

| Component | Status | File |
|-----------|--------|------|
| Lua Connector | ✅ Complete | `src/backends/emerald/connector.lua` |
| Memory Constants | ✅ Complete | `src/backends/emerald/constants.py` |
| Memory Reader | ✅ Complete | `src/backends/emerald/memory_reader.py` |
| Attribute Embedder | ✅ Complete | `src/models/embeddings.py` |
| Tactician Model | ✅ Complete | `src/models/tactician.py` |
| Drafter Model | ✅ Complete | `src/models/drafter.py` |
| System Orchestrator | ✅ Complete | `src/system.py` |
| Gymnasium Environments | ✅ Complete | `src/env.py` |

---

## Phase 1: Core Abstraction Layer (The "Bridge")

*Define Python protocols that decouple agents from ROM-specific implementation.*

### 1.1 Data Structures ✅ `[COMPLETE]`

#### 1.1.1 Pokemon Dataclasses
Located in `src/core/dataclasses.py`:

- **RentalPokemon:** Represents a rental selection (Initial Draft).
  - Concrete/Fixed Stats: `hp`, `attack`, `defense`, `sp_attack`, `sp_defense`, `speed`
  - Inheritance: `BasePokemon` + Concrete Stats + Moves
  
- **PlayerPokemon:** Represents a party member.
  - Dynamic State: `current_hp`, `status_condition`, `is_confused`, `stat_stages`, `volatile_status`
  - Inheritance: Extends `RentalPokemon`
  
- **EnemyPokemon:** Represents an opponent or Swap Candidate.
  - Partial Info: relying on Species Base Stats for estimation
  - Visible: `species_id`, `nickname`, `level`
  - Estimates: `hp_percentage`, `predicted_item`, `revealed_moves`

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

### 1.2 mGBA Connector ✅ `[COMPLETE]`

**File:** `src/backends/emerald/connector.lua`

The Lua script creates a TCP server inside mGBA for Python communication:

```
┌─────────────────┐         TCP Socket         ┌──────────────────┐
│  Python Agent   │ ◄──────────────────────► │  mGBA Emulator    │
│  (RL Training)  │     Port 7777             │  (connector.lua) │
└─────────────────┘                           └──────────────────┘
```

#### Supported Commands

| Category | Command | Description |
|----------|---------|-------------|
| Memory | `READ_BLOCK <addr> <size>` | Read raw bytes as hex |
| Memory | `READ_U16 <addr>` | Read 16-bit unsigned |
| Memory | `READ_U32 <addr>` | Read 32-bit unsigned |
| Memory | `READ_PTR <ptr> <off> <size>` | Read through pointer |
| Memory | `WRITE_BYTE <addr> <val>` | Write single byte |
| Control | `SET_INPUT <mask>` | Set button state |
| Control | `FRAME_ADVANCE <count>` | Run N frames |
| Control | `RESET` | Reset emulator |
| **RL** | `IS_WAITING_INPUT` | Check if battle awaits input → YES/NO |
| **RL** | `GET_BATTLE_OUTCOME` | Get result → 0/1/2 (Ongoing/Win/Loss) |
| **RL** | `READ_LAST_MOVES` | Get last move → "move_id,attacker" |
| **RL** | `READ_RNG` | Get PRNG state |

#### Button Bitmask
```
A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512
```

### 1.3 Memory Map ✅ `[COMPLETE]`

**File:** `src/backends/emerald/constants.py`

All addresses verified against pret/pokeemerald decompilation:

| Data | Address | Size | Notes |
|------|---------|------|-------|
| Player Party | `0x020244EC` | 600 bytes | 6 Pokemon × 100 bytes |
| Enemy Party | `0x02024744` | 600 bytes | Generated pre-battle |
| gBattleMons | `0x02024084` | 352 bytes | 4 × 88 bytes (active battlers) |
| gBattlersCount | `0x0202406C` | 1 byte | 2 for singles, 4 for doubles |
| gBattleWeather | `0x020243CC` | 2 bytes | Weather bitfield |
| **gBattleControllerExecFlags** | `0x02023E4C` | 4 bytes | 0 = waiting for input |
| **gBattleOutcome** | `0x02023EAC` | 1 byte | 0=ongoing, 1=win, 2=loss |
| **gLastUsedMove** | `0x02023E6C` | 2 bytes | Last move ID |
| **gBattlerAttacker** | `0x02023D6C` | 1 byte | Who used last move |
| **gRngValue** | `0x03005D80` | 4 bytes | PRNG state (IWRAM) |
| gSaveBlock2Ptr | `0x03005D90` | 4 bytes | Pointer to SaveBlock2 |
| Factory Streak | SaveBlock2 + `0xDE2` | 2 bytes | Win streak array |
| Rental Mons | SaveBlock2 + `0xE70` | 72 bytes | 6 × 12 bytes |

### 1.4 Knowledge Base ✅ `[COMPLETE]`

**Files:** `src/data/schema.sql`, `src/data/knowledge_base.db`

SQLite database with tables:
- `species`: Base stats, types, abilities (386 Pokemon)
- `moves`: Power, accuracy, type, effect (354 moves)
- `items`: Held items (377 items)
- `battle_frontier_mons`: Factory rental sets (882 sets)
- `type_efficacy`: Type matchup chart

---

## Phase 2: Neural Network Models

### 2.1 Attribute Embedder ✅ `[COMPLETE]`

**File:** `src/models/embeddings.py`

Rich feature extraction that goes beyond simple ID embeddings:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MoveEmbedder                                  │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ ┌──────────────────┐ │
│  │Embed(ID) │+│Embed(Type│+│Power/250│+│Acc/100  │+│OneHot(Category)  │ │
│  │  [32]    │ │   [16]   │ │   [1]   │ │   [1]   │ │     [3]          │ │
│  └──────────┘ └──────────┘ └─────────┘ └─────────┘ └──────────────────┘ │
│                              ↓                                          │
│                     Projection Layer → [32]                             │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         PokemonEmbedder                                 │
│  ┌────────────┐ ┌────────────┐ ┌────────┐ ┌─────────┐ ┌──────────────┐  │
│  │Embed(Spec) │+│Embed(Types)│+│Stats/255│+│Context  │+│Sum(MoveEmbs)│  │
│  │   [32]     │ │   [32]     │ │  [6]    │ │  [11]   │ │    [32]     │  │
│  └────────────┘ └────────────┘ └─────────┘ └─────────┘ └─────────────┘  │
│                              ↓                                          │
│                   Two-Layer Projection → [32]                           │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Vocabulary Sizes (Gen 3)
```python
VOCAB_SIZES = {
    'species': 440,    # 386 Pokemon + buffer
    'moves': 470,      # 354 moves + buffer
    'types': 18,       # All Gen 3 types
    'abilities': 80,   # 77 abilities + buffer
    'items': 400,      # 377 items + buffer
    'categories': 3,   # Physical, Special, Status
}
```

### 2.2 Tactician Model (Battle Agent) ✅ `[COMPLETE]`

**File:** `src/models/tactician.py`

LSTM-based PPO for turn-by-turn battle decisions:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     RecurrentTacticianModel                             │
│                                                                         │
│  Observation ─────► Encoder MLP ─────► LSTM ─────┬──► Actor (Policy)   │
│  [64 features]        [128]          [256×2]     │      [6 actions]     │
│                                                  │                      │
│                                                  └──► Critic (Value)   │
│                                                         [1 scalar]      │
│                                                                         │
│  Hidden State (h, c) ◄────────────────────────────────────────────────  │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Why LSTM?
- Remembers enemy move patterns
- Tracks PP depletion
- Anticipates switches
- Accounts for status duration

#### Action Space
```
0: Move 1    3: Move 4
1: Move 2    4: Switch to Pokemon 1
2: Move 3    5: Switch to Pokemon 2
```

#### RLlib Integration
- Implements `RecurrentNetwork` interface
- `get_initial_state()`: Zero-initialized LSTM states
- `forward_rnn()`: Sequence processing for training
- Action masking for invalid moves (0 PP, fainted Pokemon)

### 2.3 Drafter Model (Selection Agent) ✅ `[COMPLETE]`

**File:** `src/models/drafter.py`

Transformer-based PPO for team selection and swaps:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     TransformerDrafterModel                             │
│                                                                         │
│  Candidates ──► Self-Attention ──┐                                      │
│  [6 Pokemon]      (Synergy)      │                                      │
│                                  ├──► Cross-Attention ──► Pointer Net  │
│  Current Team ─► Self-Attention ─┘      (Compare)           (Select)    │
│  [0-3 Pokemon]                                                          │
│                                                                         │
│  Context ─────────────────────────────────────────────► Value Head     │
│  [streak, round]                                           [1 scalar]   │
└─────────────────────────────────────────────────────────────────────────┘
```

#### Components
- **SetTransformerEncoder**: Permutation-invariant set encoding
- **CrossAttention**: Team↔Candidates comparison
- **PointerNetwork**: Selection probability head

#### Action Space
- Initial Draft: `MultiDiscrete([6, 6, 6])` - Select 3 Pokemon
- Swap Phase: `Discrete(4)` - Keep or swap with offered Pokemon

---

## Phase 3: System Orchestration

### 3.1 BattleFactorySystem ✅ `[COMPLETE]`

**File:** `src/system.py`

Manages the complete game loop for a single emulator instance:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         Game Loop Phases                                 │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────┐      ┌───────────┐      ┌─────────────┐      ┌─────────┐  │
│   │  DRAFT  │ ───► │ PRE_BATTLE │ ───► │   BATTLE    │ ───► │  POST   │  │
│   │ (Select │      │  (Navigate │      │ (Tactician  │      │ BATTLE  │  │
│   │ 3 mons) │      │   menus)   │      │   acting)   │      │ (Result)│  │
│   └─────────┘      └───────────┘      └─────────────┘      └────┬────┘  │
│        ▲                                                        │       │
│        │            ┌─────────┐                                 │       │
│        │            │  SWAP   │ ◄───────────────────────────────┘       │
│        │            │ (Choose │           (if win)                      │
│        │            │ 0 or 1) │                                         │
│        │            └────┬────┘                                         │
│        │                 │                                              │
│        └─────────────────┴──── (next battle or run complete) ──────────►│
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Reward Structure

**Tactician (per action):**
```python
# Battle outcome
if outcome == WIN:
    reward = +10.0 * (1.0 + streak * 0.1)  # Streak multiplier
elif outcome == LOSS:
    reward = -10.0 * (1.0 + streak * 0.2)  # Higher penalty at high streak

# Damage shaping
reward += (damage_dealt) * 0.01
reward -= (damage_taken) * 0.0005

# Faint bonuses
if enemy_fainted:
    reward += 1.0
if player_fainted:
    reward -= 0.5
```

**Drafter (per battle):**
```python
if battle_won:
    reward = +1.0  # Delayed credit for team selection
else:
    reward = -1.0
```

### 3.2 Gymnasium Environments ✅ `[COMPLETE]`

**File:** `src/env.py`

Three RLlib-compatible environments:

#### TacticianEnv
- **Observation**: Battle state + action mask
- **Action**: `Discrete(6)` - Move 1-4, Switch 1-2
- **Purpose**: Training battle decisions only

#### DrafterEnv
- **Observation**: Rental candidates + context
- **Action**: `MultiDiscrete([6,6,6])` or `Discrete(4)`
- **Purpose**: Training team selection only

#### BattleFactoryEnv
- **Observation**: Combined battle + draft state
- **Action**: `Discrete(16)` - All possible actions
- **Purpose**: Full hierarchical training

---

## Phase 4: Training Pipeline

### 4.1 RLlib Configuration

```python
from ray.rllib.algorithms.ppo import PPOConfig

# Tactician training config
tactician_config = (
    PPOConfig()
    .environment("BattleFactory-Tactician-v0")
    .framework("torch")
    .training(
        model={
            "custom_model": "RecurrentTacticianModel",
            "max_seq_len": 100,
            "lstm_cell_size": 256,
        },
        lr=3e-4,
        gamma=0.99,
        lambda_=0.95,
        clip_param=0.2,
        entropy_coeff=0.01,
    )
    .rollouts(num_rollout_workers=0)  # Single emulator
)

# Drafter training config
drafter_config = (
    PPOConfig()
    .environment("BattleFactory-Drafter-v0")
    .framework("torch")
    .training(
        model={
            "custom_model": "TransformerDrafterModel",
        },
        lr=1e-4,
        gamma=0.99,
    )
)
```

### 4.2 Curriculum Learning

| Stage | Objective | Setup | Success Metric |
|-------|-----------|-------|----------------|
| 1 | Battle fundamentals | Random teams, no draft | 80% win rate |
| 2 | Team synergy | Frozen battle agent | Avg streak > 14 |
| 3 | Joint training | Both agents trainable | Beat Factory Brain (21+) |

---

## Phase 5: Dependencies

**File:** `requirements.txt`

```
# Core RL & ML
torch>=2.0.0
ray[rllib]>=2.9.0
gymnasium>=0.29.0
numpy>=1.24.0

# Data & Utilities
pydantic>=2.0.0
pandas

# TUI & Display
rich>=13.0.0
textual>=0.41.0

# Testing
pytest
```

---

## Appendix A: File Structure (Current)

```
pokemon-battle-factory/
├── src/
│   ├── backends/
│   │   └── emerald/
│   │       ├── backend.py         # EmeraldBackend class
│   │       ├── connector.lua      # mGBA TCP server ✅
│   │       ├── constants.py       # Memory addresses ✅
│   │       ├── decoder.py         # Character encoding
│   │       ├── decryption.py      # Pokemon data decryption
│   │       ├── memory_reader.py   # High-level memory access
│   │       └── mock.py            # Mock backend for testing
│   ├── core/
│   │   ├── dataclasses.py         # Pokemon, Move, State classes
│   │   ├── db.py                  # Database utilities
│   │   ├── enums.py               # StatusCondition, Weather, etc.
│   │   ├── knowledge.py           # KB query functions
│   │   └── protocols.py           # BattleBackend protocol
│   ├── data/
│   │   ├── knowledge_base.db      # SQLite database
│   │   ├── schema.sql             # DB schema
│   │   └── ingest_data.py         # Data import scripts
│   ├── models/                    # ✅ NEW
│   │   ├── __init__.py
│   │   ├── embeddings.py          # AttributeEmbedder ✅
│   │   ├── tactician.py           # RecurrentTacticianModel ✅
│   │   └── drafter.py             # TransformerDrafterModel ✅
│   ├── env.py                     # Gymnasium environments ✅
│   └── system.py                  # BattleFactorySystem ✅
├── tests/
├── tools/
│   └── live_debugger.py           # Real-time memory inspection
└── IMPLEMENTATION_PLAN.md         # This file
```

---

## Appendix B: Quick Start

### 1. Start mGBA with connector
```bash
# Load ROM in mGBA
# Tools -> Scripting -> Load Script -> connector.lua
# Console shows "Listening on port 7777"
```

### 2. Test connection
```python
from src.backends.emerald.backend import EmeraldBackend

backend = EmeraldBackend()
backend.connect("")
print(backend.memory.ping())  # Should print True
```

### 3. Run training
```python
import ray
from ray.rllib.algorithms.ppo import PPO

ray.init()

# Register custom model
from ray.rllib.models import ModelCatalog
from src.models.tactician import RecurrentTacticianModel

ModelCatalog.register_custom_model("RecurrentTacticianModel", RecurrentTacticianModel)

# Create and train
algo = PPO(config=tactician_config)
for i in range(1000):
    result = algo.train()
    print(f"Episode {i}: reward={result['episode_reward_mean']}")
```

---

## Appendix C: Research References

- [pret/pokeemerald](https://github.com/pret/pokeemerald) - Decompilation
- [Bulbapedia RAM Map](https://bulbapedia.bulbagarden.net/wiki/Pokémon_data_structure_(Generation_III))
- [RLlib Documentation](https://docs.ray.io/en/latest/rllib/index.html)
- PPO Paper: Schulman et al., "Proximal Policy Optimization Algorithms" (2017)
- Set Transformer: Lee et al., "Set Transformer" (2019)
- Pointer Networks: Vinyals et al., "Pointer Networks" (2015)

---

## Appendix D: Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| RAM offsets incorrect | Low | High | Cross-referenced with pret; runtime validation |
| Single emulator too slow | Medium | Medium | Optimized frame skipping; consider vectorization |
| Reward too sparse | Medium | Medium | Dense shaping rewards implemented |
| LSTM vanishing gradients | Low | Medium | LayerNorm, gradient clipping |
| Gen 4 encryption complex | Medium | Medium | Defer; focus Gen 3 first |
