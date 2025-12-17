# Memory Addresses for Pokemon Emerald (US)

# Base Addresses
EWRAM_BASE = 0x02000000
IWRAM_BASE = 0x03000000

# Game Variables (as per game_variables_map.md)
ADDR_BATTLE_OUTCOME = 0x0202433a       # u8: 0=Ongoing, 1=Win, 2=Loss
ADDR_BATTLE_COMMUNICATION = 0x02024332 # u8[]
ADDR_BATTLER_IN_MENU_ID = 0x020244b8   # u8
ADDR_BATTLE_MONS = 0x02024084          # BattlePokemon[] (Active stats)
ADDR_LAST_MOVES = 0x02024248           # u16[]
ADDR_MAP_LAYOUT_ID = 0x0203732A        # u16 (See LAYOUT_ constants)
ADDR_CHALLENGE_BATTLE_NUM = 0x02025D52 # u16 (0-6)
ADDR_BATTLE_TYPE_FLAGS = 0x02022fec    # u32
ADDR_DISABLE_STRUCTS = 0x020242bc      # DisableStruct[]
ADDR_ENEMY_PARTY = 0x02024744          # Pokemon[] (Full party data)
ADDR_PLAYER_PARTY = 0x020244ec         # Pokemon[]

ADDR_RNG_VALUE = 0x03005d80            # u32 (IWRAM)
ADDR_MAIN = 0x030022c0                 # struct Main (IWRAM)
ADDR_SAVEBLOCK2 = 0x02024a54           # struct SaveBlock2
ADDR_SAVEBLOCK1_PTR = 0x03005d8c       # pointer to SaveBlock1
ADDR_SAVEBLOCK2_PTR = 0x03005d90       # pointer to SaveBlock2

ADDR_BATTLE_WEATHER = 0x020243cc       # u16
ADDR_SIDE_TIMERS = 0x02024294          # struct SideTimer[]
ADDR_ACTION_CURSOR = 0x020244ac        # u8[]
ADDR_MOVE_CURSOR = 0x020244b0          # u8[]
ADDR_MOVE_RESULT_FLAGS = 0x0202427c    # u8

# Data Structure Sizes (Bytes)
SIZE_POKEMON = 100        # Gen 3 Party Mon
SIZE_BATTLE_MON = 88      # Gen 3 Battle Mon
SIZE_RENTAL_MON = 12      # Factory Rental Mon 
PARTY_SIZE = 6

# Battle Frontier Offsets (Relative to SaveBlock2 Base)
# Note: It is safer to read the pointer at ADDR_SAVEBLOCK2_PTR than assume 0x02024a54
OFFSET_FRONTIER_LVL_MODE = 0xCA9       # u8 (0=Lvm50, 1=OpenLvl)
OFFSET_FRONTIER_BATTLE_NUM = 0xCB2     # u16
OFFSET_FACTORY_WIN_STREAKS = 0xDE2     # u16[][]
OFFSET_FACTORY_RENTS_COUNT = 0xDF6     # u16[][]
OFFSET_FACTORY_RENTAL_MONS = 0xE70     # RentalMon[]

# Constants
BATTLE_OUTCOME_ONGOING = 0
BATTLE_OUTCOME_WIN = 1
BATTLE_OUTCOME_LOSS = 2
BATTLE_OUTCOME_DRAW = 3
BATTLE_OUTCOME_RAN = 4

# Map Layout IDs
LAYOUT_FACTORY_PRE_BATTLE = 347 # Lobby/Drafting/Swapping
LAYOUT_FACTORY_BATTLE = 348     # Arena/Battle
