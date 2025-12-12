from enum import Enum, IntEnum, auto

class MoveCategory(IntEnum):
    PHYSICAL = 0
    SPECIAL = 1
    STATUS = 2

class StatusCondition(IntEnum):
    NONE = 0
    SLEEP = 1
    POISON = 2
    BURN = 3
    FREEZE = 4
    PARALYSIS = 5
    BAD_POISON = 6

class Weather(IntEnum):
    NONE = 0
    RAIN = 1
    SUN = 2
    SANDSTORM = 3
    HAIL = 4

class Terrain(IntEnum):
    NONE = 0
    ELECTRIC = 1
    GRASSY = 2
    MISTY = 3
    PSYCHIC = 4

class ScreenType(Enum):
    Other = auto()
    DRAFT = auto()
    SWAP = auto()
    BATTLE = auto()
    RESULT = auto()
