# Pokemon Battle Factory RL System

A hierarchical reinforcement learning system for playing the Battle Factory facility in Pokemon Emerald. Uses a two-agent architecture with a **Drafter** (team selection) and **Tactician** (battle decisions).

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Configuration Guide](#configuration-guide)
- [Creating Custom Steps](#creating-custom-steps)
- [Adding New Parameters](#adding-new-parameters)
- [Extending the Pipeline](#extending-the-pipeline)
- [File Structure](#file-structure)
- [API Reference](#api-reference)

---

## Quick Start

### Prerequisites

1. **mGBA** emulator with Pokemon Emerald ROM loaded
2. **connector.lua** script loaded in mGBA: `Tools -> Scripting -> Load`
3. Python 3.10+ with dependencies: `pip install -r requirements.txt`

### Run an Episode

```bash
# Basic run with random agents
python scripts/run_episode.py

# Fast mode (for fast-forward emulation)
python scripts/run_episode.py --speed turbo

# Interactive debugging
python scripts/run_episode.py --interactive

# Multiple episodes with stats
python scripts/run_episode.py -n 10 --stats
```

### In Python

```python
from src import TrainingController, RandomDrafter, RandomTactician, config

# Optional: Set speed mode for faster execution
config.timing.set_speed_mode('turbo')

# Create controller and agents
controller = TrainingController()
controller.connect()
controller.initialize_to_draft()

drafter = RandomDrafter()
tactician = RandomTactician()

# Run episode
result = controller.run_episode(drafter, tactician)
print(f"Win streak: {result.win_streak}")

controller.disconnect()
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       TrainingController                             │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                      State Machine                              │ │
│  │   DRAFT → BATTLE_READY → IN_BATTLE → POST_BATTLE → (SWAP) →...│ │
│  └────────────────────────────────────────────────────────────────┘ │
│                              ↓                                       │
│  ┌──────────────┐    ┌─────────────────┐    ┌───────────────────┐  │
│  │   Drafter    │    │    Tactician    │    │  EmeraldBackend   │  │
│  │  (obs→team)  │    │  (obs→action)   │    │     (mGBA)        │  │
│  └──────────────┘    └─────────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **TrainingController** | `src/controller/training.py` | Main orchestrator for episodes |
| **InputController** | `src/controller/input.py` | Button input handling |
| **StateMachine** | `src/controller/state_machine.py` | Game phase transitions |
| **EmeraldBackend** | `src/backends/emerald/backend.py` | mGBA communication |
| **MemoryReader** | `src/backends/emerald/memory_reader.py` | Game memory parsing |
| **Config** | `src/config.py` | All configurable parameters |

---

## Configuration Guide

All configuration is centralized in **`src/config.py`**. The global `config` object contains:

### Timing Configuration

Controls button press speed. **Location:** `config.timing`

```python
from src.config import config

# Use presets
config.timing.set_speed_mode('normal')   # Default
config.timing.set_speed_mode('fast')     # 2x faster
config.timing.set_speed_mode('turbo')    # 4x faster
config.timing.set_speed_mode('instant')  # Maximum speed

# Custom values (in seconds)
config.timing.set_custom_timing(
    button_hold=0.01,    # How long to hold button
    wait_short=0.02,     # Wait after button press
    wait_medium=0.05,    # Wait for menu transitions
    wait_long=0.1,       # Wait for screen transitions
    wait_battle=0.2,     # Wait for battle animations
)

# Scale all timing (0.5 = 2x faster)
config.timing.scale_timing(0.5)
```

| Parameter | Default | Description |
|-----------|---------|-------------|
| `button_hold_time` | 0.08s | How long to hold each button |
| `wait_short` | 0.25s | Wait after button press |
| `wait_medium` | 0.5s | Wait for menu transitions |
| `wait_long` | 1.0s | Wait for screen transitions |
| `wait_battle` | 2.0s | Wait for battle animations |
| `input_timeout` | 60.0s | Max wait for input prompt |

### Observation Dimensions

Controls neural network input sizes. **Location:** `config.dimensions`

```python
config.dimensions.battle_obs_dim    # 64 - Battle observation size
config.dimensions.draft_obs_dim     # 128 - Draft observation size
config.dimensions.swap_obs_dim      # 64 - Swap observation size
config.dimensions.battle_num_actions  # 6 - Move 1-4, Switch 1-2
```

### Reward Shaping

Controls RL reward signals. **Location:** `config.rewards`

```python
config.rewards.win_base_reward      # 10.0 - Base reward for winning
config.rewards.win_streak_multiplier  # 0.1 - Bonus per streak
config.rewards.loss_base_penalty    # 10.0 - Penalty for losing
config.rewards.damage_dealt_multiplier  # 0.01 - Reward per damage %
config.rewards.damage_taken_multiplier  # 0.0005 - Penalty per damage
config.rewards.enemy_faint_bonus    # 1.0 - Bonus for KO
config.rewards.player_faint_penalty # 0.5 - Penalty for getting KO'd
```

### Network Configuration

Connection settings. **Location:** `config.network`

```python
config.network.host       # "127.0.0.1"
config.network.port       # 7777
config.network.buffer_size  # 4096
```

### Game Constants

Pokemon game constants. **Location:** `config.game`

```python
config.game.max_streak          # 42 - Factory Brain at 42
config.game.battles_per_round   # 7
config.game.team_size           # 3
config.game.rental_pool_size    # 6
```

---

## Creating Custom Steps

### Adding New Navigation Steps

Navigation sequences are defined in **`src/controller/input.py`**:

```python
from src.controller.input import ButtonSequence, ButtonPress, Button

# Create a new sequence
MY_CUSTOM_SEQUENCE = ButtonSequence(
    name="My Custom Navigation",
    presses=[
        ButtonPress(Button.A, wait_after=0.5, description="Press A"),
        ButtonPress(Button.DOWN, wait_after=0.3, description="Navigate down"),
        ButtonPress(Button.A, wait_after=0.5, description="Confirm"),
        ButtonPress(Button.WAIT, wait_after=1.0, description="Wait for transition"),
        ButtonPress(Button.B, wait_after=0.3, description="Back out"),
    ]
)

# Use it
controller.input.execute_sequence(MY_CUSTOM_SEQUENCE)
```

### Adding New Phase Steps

To add a new phase to the pipeline, modify **`src/controller/training.py`**:

```python
# 1. Add phase result method
def step_my_phase(self, agent=None) -> PhaseResult:
    """Execute my custom phase."""
    logger.info("=== MY PHASE ===")
    
    if self.phase != GamePhase.MY_PHASE:
        return PhaseResult(
            success=False,
            phase="my_phase",
            next_phase=self.phase,
            error="Not in my phase"
        )
    
    try:
        # Get observation
        obs = self.get_my_observation()
        
        # Get agent action
        if agent:
            action = agent(obs, self.phase)
        else:
            action = self._default_my_action()
        
        # Execute action
        self._execute_my_action(action)
        
        # Transition to next phase
        self.transition_to(GamePhase.NEXT_PHASE, force=True)
        
        return PhaseResult(
            success=True,
            phase="my_phase",
            next_phase=self.phase,
            data={"action": action}
        )
    except Exception as e:
        return PhaseResult(
            success=False,
            phase="my_phase",
            next_phase=GamePhase.ERROR,
            error=str(e)
        )
```

### Adding New Game Phases

Add to **`src/core/enums.py`**:

```python
class GamePhase(Enum):
    # ... existing phases ...
    MY_CUSTOM_PHASE = auto()
    
    @property
    def is_my_phase(self) -> bool:
        return self == GamePhase.MY_CUSTOM_PHASE
```

Update valid transitions in **`src/controller/state_machine.py`**:

```python
VALID_TRANSITIONS = {
    # ... existing transitions ...
    GamePhase.SOME_PHASE: {
        GamePhase.MY_CUSTOM_PHASE,  # Add transition
        GamePhase.ERROR,
    },
    GamePhase.MY_CUSTOM_PHASE: {
        GamePhase.NEXT_PHASE,
        GamePhase.ERROR,
    },
}
```

---

## Adding New Parameters

### To Config

Add new parameters to **`src/config.py`**:

```python
@dataclass
class MyNewConfig:
    """My new configuration section."""
    my_param: float = 1.0
    another_param: int = 42

@dataclass
class BattleFactoryConfig:
    # ... existing fields ...
    my_config: MyNewConfig = field(default_factory=MyNewConfig)
```

### To Agents

Add agent parameters in **`src/agents/base.py`**:

```python
class AgentConfig:
    def __init__(
        self,
        # ... existing params ...
        my_new_param: float = 0.5,
    ):
        self.my_new_param = my_new_param
```

### To Command Line

Add CLI args in **`scripts/run_episode.py`**:

```python
parser.add_argument(
    "--my-param",
    type=float,
    default=1.0,
    help="Description of my parameter",
)

# Then use it
args = parser.parse_args()
config.my_config.my_param = args.my_param
```

---

## Extending the Pipeline

### Creating a New Agent

Create a new agent in **`src/agents/`**:

```python
# src/agents/my_agent.py
from .base import BaseDrafter, BaseTactician
from ..core.enums import GamePhase
import numpy as np

class MyDrafter(BaseDrafter):
    """My custom drafter implementation."""
    
    def __init__(self, my_param: float = 0.5):
        self.my_param = my_param
    
    def __call__(self, obs: np.ndarray, phase: GamePhase) -> np.ndarray:
        if phase == GamePhase.DRAFT_SCREEN:
            return self.select_team(obs)
        elif phase == GamePhase.SWAP_SCREEN:
            return np.array([self.decide_swap(obs)])
        return np.array([0])
    
    def select_team(self, obs: np.ndarray) -> np.ndarray:
        # Your team selection logic
        return np.array([0, 1, 2])  # Select first 3
    
    def decide_swap(self, obs: np.ndarray) -> int:
        # Your swap logic
        return 0  # Keep team


class MyTactician(BaseTactician):
    """My custom tactician implementation."""
    
    def __call__(
        self,
        obs: np.ndarray,
        phase: GamePhase,
        action_mask: np.ndarray,
    ) -> int:
        return self.select_action(obs, action_mask)
    
    def select_action(self, obs: np.ndarray, mask: np.ndarray) -> int:
        # Your battle action logic
        valid = np.where(mask > 0)[0]
        return int(valid[0]) if len(valid) > 0 else 0
    
    def get_initial_hidden_state(self):
        return None
```

Export in **`src/agents/__init__.py`**:

```python
from .my_agent import MyDrafter, MyTactician
__all__ = [..., "MyDrafter", "MyTactician"]
```

### Creating a Custom Environment

Add a new Gymnasium environment in **`src/env.py`**:

```python
class MyCustomEnv(gym.Env):
    """My custom environment."""
    
    def __init__(self, config_dict=None):
        super().__init__()
        # Define observation/action spaces
        self.observation_space = spaces.Box(...)
        self.action_space = spaces.Discrete(...)
    
    def reset(self, *, seed=None, options=None):
        # Reset logic
        return observation, info
    
    def step(self, action):
        # Step logic
        return observation, reward, terminated, truncated, info
```

### Adding Memory Reading

Add new memory reads in **`src/backends/emerald/memory_reader.py`**:

```python
class MemoryReader:
    # Memory addresses (find via debugging)
    ADDR_MY_DATA = 0x02000000
    
    def read_my_data(self) -> MyDataClass:
        """Read my custom data from memory."""
        raw = self._read_memory(self.ADDR_MY_DATA, size=32)
        # Parse raw bytes
        return MyDataClass(...)
```

---

## File Structure

```
pokemon-battle-factory/
├── src/
│   ├── __init__.py              # Package exports
│   ├── config.py                # ⚙️ ALL CONFIGURATION HERE
│   │
│   ├── controller/              # 🎮 GAME CONTROL LAYER
│   │   ├── __init__.py
│   │   ├── base.py              # Base controller (observations, rewards)
│   │   ├── input.py             # Button input & sequences
│   │   ├── state_machine.py     # Phase transitions
│   │   └── training.py          # TrainingController (main interface)
│   │
│   ├── agents/                  # 🤖 AGENT IMPLEMENTATIONS
│   │   ├── __init__.py
│   │   ├── base.py              # Agent interfaces
│   │   ├── random_agents.py     # Random baseline agents
│   │   └── interactive.py       # Human-controlled agents
│   │
│   ├── backends/                # 🔌 EMULATOR BACKENDS
│   │   └── emerald/
│   │       ├── backend.py       # mGBA socket connection
│   │       ├── memory_reader.py # Memory parsing
│   │       ├── decoder.py       # Text decoding
│   │       └── connector.lua    # mGBA Lua script
│   │
│   ├── core/                    # 📦 CORE TYPES
│   │   ├── enums.py             # GamePhase, BattleOutcome, etc.
│   │   ├── dataclasses.py       # BattleState, Pokemon, Move
│   │   ├── exceptions.py        # Custom exceptions
│   │   └── knowledge_base.py    # Pokemon data (species, moves)
│   │
│   ├── env.py                   # 🏋️ GYMNASIUM ENVIRONMENTS
│   ├── navigation.py            # Navigation sequences (legacy)
│   └── observations.py          # Observation building
│
├── scripts/                     # 🚀 RUNNABLE SCRIPTS
│   ├── run_episode.py           # Main episode runner
│   └── run_random.py            # Random agent runner
│
├── tools/                       # 🔧 DEBUGGING TOOLS
│   ├── step_checker.py          # Pipeline verification
│   ├── live_debugger.py         # Real-time debugging
│   └── find_input_flag.py       # Memory address finder
│
├── data/
│   └── knowledge_base.db        # Pokemon data SQLite
│
└── requirements.txt
```

---

## API Reference

### TrainingController

```python
controller = TrainingController(backend=None, verbose=False)

# Connection
controller.connect(host="127.0.0.1", port=7777) -> bool
controller.disconnect()

# Navigation
controller.initialize_to_draft() -> bool

# Phase execution
controller.step_draft(agent) -> PhaseResult
controller.step_battle(agent) -> PhaseResult
controller.step_swap(agent) -> PhaseResult
controller.step_turn(action: int) -> TurnResult

# Full episode
controller.run_episode(drafter, tactician) -> EpisodeResult

# State
controller.phase -> GamePhase
controller.is_connected -> bool
controller.is_run_complete -> bool
controller.run_stats -> RunStats

# Observations
controller.get_battle_observation() -> np.ndarray
controller.get_draft_observation() -> np.ndarray
controller.get_action_mask() -> np.ndarray
```

### InputController

```python
input_ctrl = controller.input

# Basic presses
input_ctrl.press_a(hold=0.01, wait=0.02)
input_ctrl.press_b()
input_ctrl.press_up()
input_ctrl.press_down()

# Navigation
input_ctrl.navigate_menu(target=3, current=0)
input_ctrl.press_direction('down', count=3)

# Sequences
input_ctrl.execute_sequence(MY_SEQUENCE)

# Timing control
input_ctrl.set_timing(hold=0.01, wait=0.02)
input_ctrl.reset_timing()
```

### Config

```python
from src.config import config

# Timing
config.timing.set_speed_mode('turbo')
config.timing.set_custom_timing(button_hold=0.01)
config.timing.scale_timing(0.5)

# Dimensions
config.dimensions.battle_obs_dim
config.dimensions.draft_obs_dim

# Rewards
config.rewards.win_base_reward

# Network
config.network.host
config.network.port
```

---

## Troubleshooting

### Connection Issues

```bash
# Test connection
python scripts/run_episode.py --test

# Check mGBA console for "Listening on port 7777"
```

### Timing Issues

```bash
# If actions are too fast/slow
python scripts/run_episode.py --speed turbo
python scripts/run_episode.py --hold-time 0.02 --wait-time 0.05
```

### Debug Pipeline

```bash
# Interactive debugging
python tools/step_checker.py --interactive

# Step-by-step with confirmations
python tools/step_checker.py --confirm
```

---

## License

MIT License - See LICENSE file for details.

