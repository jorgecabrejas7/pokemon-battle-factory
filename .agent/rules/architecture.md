---
trigger: always_on
glob:
description:
---
# Project Context
You are an expert AI Software Architect and ML Engineer working on a **Hierarchical Reinforcement Learning system** for the Pokémon Battle Factory.
The system is built on **Python**, **PyTorch**, **Stable-Baselines3**, and **mGBA** (headless).

# Core Architectural Rules

1.  **Abstraction First:**
    *   NEVER hardcode Generation 3 (Emerald) logic directly into the RL Agents or Training Loop.
    *   Always interact with the emulator through the `AbstractBattleBackend` interface.
    *   Agents must be agnostic to the underlying game version.

2.  **Gen 3 vs. Gen 4 Separation:**
    *   Concrete logic for memory reading, RAM addresses, or game mechanics must reside strictly in `src/backends/emerald/` or `src/backends/platinum/`.
    *   Shared logic goes in `src/core/`.

3.  **Tensor Operations:**
    *   When writing PyTorch models or forward passes, ALWAYS comment the shape of the tensor at key transformations.
    *   Example: `x = self.fc1(x)  # [Batch, Seq_Len, 256]`

4.  **Memory Safety:**
    *   When dealing with RAM addresses, define them as HEX constants in a dedicated `constants.py` file.
    *   Example: `PLAYER_PARTY_OFFSET = 0x020244EC`
    *   Never use magic numbers inside logic code.
