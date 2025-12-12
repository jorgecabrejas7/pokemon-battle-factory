---
trigger: always_on
glob:"**/*.py
description:
---

# Python Style & Typing Rules

1.  **Strict Typing:**
    *   All function definitions must have type hints for arguments and return values.
    *   Use `typing.List`, `typing.Dict`, `typing.Optional`, and `typing.Tuple`.
    *   Use `npt.NDArray` or `torch.Tensor` for array inputs.

2.  **Imports Organization:**
    *   Group imports in this order:
        1.  Standard Library (os, sys, struct)
        2.  Third-Party (torch, gymnasium, numpy)
        3.  Local Application Imports (src.core...)

3.  **Data Structures:**
    *   Prefer `@dataclass` for structured data (e.g., `Pokemon`, `Move`) over dictionaries.

# Documentation Standards (Google Style)

Follow the Google Python Style Guide for docstrings. Every class and public method must have a docstring.

## Class Docstring Template:
```python
class FeatureExtractor(BaseFeatures):
    """Handles the conversion of raw emulator RAM into normalized tensors.
    
    This class is responsible for reading the 100-byte structure of a Pokémon
    from mGBA memory and normalizing stats to a 0-1 range.

    Attributes:
        species_embed (torch.nn.Embedding): Embedding layer for Species ID.
        vocab_size (int): Total number of Pokémon in the generation.
    """
```

## Method Docstring Template

```python
def read_party(self, ram_block: bytes) -> List[Pokemon]:
    """Parses a binary block of RAM into a list of Pokemon objects.

    Args:
        ram_block (bytes): A byte string containing the raw party data. 
                           For Gen 3, this should be 600 bytes (100 bytes * 6 slots).

    Returns:
        List[Pokemon]: A list of populated Pokemon dataclasses.

    Raises:
        ValueError: If ram_block size does not match expected generation size.
    """
```
## Quality Assurance

* 1. Logging:
	* Use the standard logging library. Do NOT use print().
	* Use logger.debug() for memory reads/hex dumps.
	* Use logger.info() for higg-level battle outcomes.
* 2. Unit Tests:
	* When generating logic for state decoding (e.g., converting a status byte 0x40 to "Paralyzed"), always implement a check to verify the bitwise operation. 


