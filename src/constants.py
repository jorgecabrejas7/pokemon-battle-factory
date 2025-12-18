"""
Memory Addresses and Constants for Pokémon Emerald (US).

This file contains memory addresses (pointers, offsets) and game logic constants
specifically for the Pokémon Emerald version. These values are derived from
reverse engineering and analysis of the Globalize Emerald codebase.

Reference: game_variables_map.md for detailed memory mapping.
"""

# Base Addresses
EWRAM_BASE = 0x02000000  # External Work RAM Base
IWRAM_BASE = 0x03000000  # Internal Work RAM Base

# Game Variables (as per game_variables_map.md)
ADDR_BATTLE_OUTCOME = 0x0202433a       # u8: 0=Ongoing, 1=Win, 2=Loss, 3=Draw, 4=Ran
ADDR_BATTLE_COMMUNICATION = 0x02024332 # u8[]: Communication byte flags
ADDR_BATTLER_IN_MENU_ID = 0x020244b8   # u8: ID of the battler currently in menu
ADDR_BATTLE_MONS = 0x02024084          # BattlePokemon[]: Array of 4 active battle structs
ADDR_LAST_MOVES = 0x02024248           # u16[]: Array of last used move IDs per battler
ADDR_MAP_LAYOUT_ID = 0x0203732A        # u16: Current map layout ID (determines room/Location)
ADDR_CHALLENGE_BATTLE_NUM = 0x02025D52 # u16: Current battle number in the streak (0-6)
ADDR_BATTLE_TYPE_FLAGS = 0x02022fec    # u32: Bitmask for battle type (Double, Link, etc.)
ADDR_DISABLE_STRUCTS = 0x020242bc      # DisableStruct[]: Encored, Disabled, etc.
ADDR_ENEMY_PARTY = 0x02024744          # Pokemon[]: Enemy party (6x100 bytes)
ADDR_PLAYER_PARTY = 0x020244ec         # Pokemon[]: Player party (6x100 bytes)

ADDR_RNG_VALUE = 0x03005d80            # u32: Current RNG seed at 0x3005D80 (IWRAM)
ADDR_MAIN = 0x030022c0                 # struct Main: Main game loop struct
ADDR_SAVEBLOCK2 = 0x02024a54           # struct SaveBlock2: Player name, options, etc.
ADDR_SAVEBLOCK1_PTR = 0x03005d8c       # pointer to SaveBlock1 (Game state, key items)
ADDR_SAVEBLOCK2_PTR = 0x03005d90       # pointer to SaveBlock2

ADDR_BATTLE_WEATHER = 0x020243cc       # u16: Weather flags
ADDR_SIDE_TIMERS = 0x02024294          # struct SideTimer[]: Reflect/LightScreen timers
ADDR_ACTION_CURSOR = 0x020244ac        # u8[]: Cursor position in menus
ADDR_MOVE_CURSOR = 0x020244b0          # u8[]: Cursor position in move selection
ADDR_MOVE_RESULT_FLAGS = 0x0202427c    # u8: Outcome of move execution (Hit, Miss, etc.)

# Data Structure Sizes (Bytes)
SIZE_POKEMON = 100        # Gen 3 Party Pokemon Structure Size
SIZE_BATTLE_MON = 88      # Gen 3 Active Battle Pokemon Structure Size
SIZE_RENTAL_MON = 12      # Factory Rental Pokemon Compact Structure Size
PARTY_SIZE = 6

# Battle Frontier Offsets (Relative to SaveBlock2 Base)
# Note: It is safer to read the pointer at ADDR_SAVEBLOCK2_PTR than assume 0x02024a54
OFFSET_FRONTIER_LVL_MODE = 0xCA9       # u8 (0=Lvl 50, 1=Open Lvl)
OFFSET_FRONTIER_BATTLE_NUM = 0xCB2     # u16: Current win streak count?
OFFSET_FACTORY_WIN_STREAKS = 0xDE2     # u16[][]: Recorded win streaks
OFFSET_FACTORY_RENTS_COUNT = 0xDF6     # u16[][]: Rental stats
OFFSET_FACTORY_RENTAL_MONS = 0xE70     # RentalMon[]: Array of available rental mons

# Constants
BATTLE_OUTCOME_ONGOING = 0
BATTLE_OUTCOME_WIN = 1
BATTLE_OUTCOME_LOSS = 2
BATTLE_OUTCOME_DRAW = 3
BATTLE_OUTCOME_RAN = 4

# Map Layout IDs
LAYOUT_FACTORY_PRE_BATTLE = 347 # Lobby/Drafting/Swapping Room
LAYOUT_FACTORY_BATTLE = 348     # Battle Arena

# Weather Flags
WEATHER_RAIN_TEMPORARY      = (1 << 0)
WEATHER_RAIN_DOWNPOUR       = (1 << 1)
WEATHER_RAIN_PERMANENT      = (1 << 2)
WEATHER_SANDSTORM_TEMPORARY = (1 << 3)
WEATHER_SANDSTORM_PERMANENT = (1 << 4)
WEATHER_SUN_TEMPORARY       = (1 << 5)
WEATHER_SUN_PERMANENT       = (1 << 6)
WEATHER_HAIL_TEMPORARY      = (1 << 7)
# Note: Hail permanent (1 << 8) exists in some games but mostly Hail is temp in Gen 3 unless hacked?

