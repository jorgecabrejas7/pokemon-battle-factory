"""
Emerald Constants
"""

# ==============================================================================
# CHARACTER MAP - Gen 3 Text Encoding
# ==============================================================================
# Simplified map for commonly used characters
CHAR_MAP = {
    0x00: " ", 0xA1: "0", 0xA2: "1", 0xA3: "2", 0xA4: "3", 0xA5: "4", 
    0xA6: "5", 0xA7: "6", 0xA8: "7", 0xA9: "8", 0xAA: "9",
    0xBB: "A", 0xBC: "B", 0xBD: "C", 0xBE: "D", 0xBF: "E", 0xC0: "F", 
    0xC1: "G", 0xC2: "H", 0xC3: "I", 0xC4: "J", 0xC5: "K", 0xC6: "L", 
    0xC7: "M", 0xC8: "N", 0xC9: "O", 0xCA: "P", 0xCB: "Q", 0xCC: "R", 
    0xCD: "S", 0xCE: "T", 0xCF: "U", 0xD0: "V", 0xD1: "W", 0xD2: "X", 
    0xD3: "Y", 0xD4: "Z",
    0xD5: "a", 0xD6: "b", 0xD7: "c", 0xD8: "d", 0xD9: "e", 0xDA: "f", 
    0xDB: "g", 0xDC: "h", 0xDD: "i", 0xDE: "j", 0xDF: "k", 0xE0: "l", 
    0xE1: "m", 0xE2: "n", 0xE3: "o", 0xE4: "p", 0xE5: "q", 0xE6: "r", 
    0xE7: "s", 0xE8: "t", 0xE9: "u", 0xEA: "v", 0xEB: "w", 0xEC: "x", 
    0xED: "y", 0xEE: "z",
    0xFF: "" # Terminator
}

# ==============================================================================
# PARTY DATA - Pokemon in player/enemy teams
# ==============================================================================
# Party structure: 6 Pokemon slots × 100 bytes each = 600 bytes total
# 
# Each 100-byte Pokemon structure contains:
#   Bytes 0-3:    Personality Value (PID) - determines nature, gender, ability, shininess
#   Bytes 4-7:    Original Trainer ID (OTID) - used for encryption key
#   Bytes 8-17:   Nickname (10 bytes, Gen3 character encoding, 0xFF terminated)
#   Bytes 18-19:  Language
#   Bytes 20-27:  OT Name (7 bytes)
#   Bytes 28-29:  Checksum (validates decrypted data)
#   Bytes 30-31:  Sanity/Padding
#   Bytes 32-79:  Encrypted Substructures (48 bytes, 4 blocks × 12 bytes)
#                 - Encryption key = PID XOR OTID
#                 - Block order shuffled based on PID % 24
#                 - Blocks: Growth, Attacks, EVs/Condition, Miscellaneous
#   Bytes 80-99:  UNENCRYPTED battle stats (only valid when in party)
#                 - Status condition, Level, Pokerus, Current HP, Stats
#
# Note: Empty slots have PID = 0

PLAYER_PARTY_OFFSET = 0x020244EC  # gPlayerParty - Your team of up to 6 Pokemon
ENEMY_PARTY_OFFSET = 0x02024744   # gEnemyParty - Opponent's team (populated at battle start)

# Structure sizes for parsing
POKEMON_SIZE_BYTES = 100      # Full Pokemon data structure
SUBSTRUCT_SIZE_BYTES = 12     # Each of the 4 encrypted substructure blocks
PARTY_SIZE = 6                # Maximum Pokemon per party
MAX_PARTY_BYTES = PARTY_SIZE * POKEMON_SIZE_BYTES  # 600 bytes total

# ==============================================================================
# BATTLE DATA - Active Pokemon currently fighting
# ==============================================================================
# gBattleMons contains the "battle structs" for active Pokemon.
# Unlike party data, these are UNENCRYPTED and contain real-time battle state:
#   - Modified stats (after stat stage changes)
#   - Current HP/PP
#   - Status conditions (including volatile ones like Confusion)
#   - Stat stage modifiers (-6 to +6)
#
# This is what you want to read during battle for accurate current state.

BATTLE_MONS_OFFSET = 0x02024084   # gBattleMons - Array of active battlers
BATTLE_MON_SIZE = 88              # 0x58 bytes per battler
BATTLE_MON_COUNT = 4              # Max 4 battlers (supports 2v2 doubles)
                                  # Index 0: Player slot 1
                                  # Index 1: Enemy slot 1
                                  # Index 2: Player slot 2 (doubles)
                                  # Index 3: Enemy slot 2 (doubles)

# Battle state tracking
ACTIVE_BATTLER_OFFSET = 0x02024064   # gActiveBattler - Index of Pokemon taking action (0-3)
BATTLERS_COUNT_OFFSET = 0x0202406C   # gBattlersCount - 2 for singles, 4 for doubles

# Weather affects damage calculations and some abilities
# This is a bitfield, not a simple enum
BATTLE_WEATHER_OFFSET = 0x020243CC   # gBattleWeather - Current weather condition
                                     # Bits 0-2: Rain (0x07)
                                     # Bits 3-4: Sandstorm (0x18)
                                     # Bits 5-6: Sun (0x60)
                                     # Bit 7: Hail (0x80)

# Turn tracking for battle logic
TURN_COUNTER_OFFSET = 0x02023E82     # Current turn number in battle

# Trainer identification
TRAINER_ID_OFFSET = 0x02038BCA       # gTrainerId - Current opponent trainer ID

# Critical for RL agent timing - indicates when player input is expected
BATTLE_INPUT_WAIT_FLAG_OFFSET = 0x02023E4C  # 0 = Busy/Animating, 1 = Waiting for Input

# Battle Flow / History
# Defined in game_variables_mapo.md
BATTLE_OUTCOME_OFFSET = 0x0202433A    # gBattleOutcome: 0=Ongoing, 1=Win, 2=Loss, 3=Draw, 4=Ran
LAST_USED_MOVE_OFFSET = 0x02024248    # gLastMoves (Array of u16) - Note: Mapo says array, check usage
BATTLE_COMMUNICATION_OFFSET = 0x02024332 # gBattleCommunication
BATTLER_IN_MENU_ID_OFFSET = 0x020244B8   # gBattlerInMenuId
BATTLE_TYPE_FLAGS_OFFSET = 0x02022FEC    # gBattleTypeFlags
DISABLE_STRUCTS_OFFSET = 0x020242BC      # gDisableStructs
SIDE_TIMERS_OFFSET = 0x02024294          # gSideTimers
ACTION_SELECTION_CURSOR = 0x020244AC     # gActionSelectionCursor
MOVE_SELECTION_CURSOR = 0x020244B0       # gMoveSelectionCursor
MOVE_RESULT_FLAGS_OFFSET = 0x0202427C    # gMoveResultFlags
BATTLE_RESOURCES_PTR = 0x020244A8        # gBattleResources (Pointer)

# Unverified or Legacy (Keep until confirmed unused)
BATTLER_ATTACKER_OFFSET = 0x02023D6C  # gBattlerAttacker: Who used the move (0-3)

# ==============================================================================
# SAVE BLOCK POINTERS - Indirect access to save data
# ==============================================================================
# SaveBlock1 and SaveBlock2 are large structures containing persistent game state.
# These addresses contain POINTERS to the actual data, not the data itself.
#
# Usage: 
#   1. Read the 4-byte pointer value at these addresses
#   2. Add the field offset to get the actual data address
#   3. Read the data from that calculated address
#
# Example (reading win streak):
#   base = read_u32(SAVE_BLOCK_2_PTR)  # e.g., returns 0x02039xxx
#   win_streak = read_u16(base + FRONTIER_FACTORY_STREAK_OFFSET)

SAVE_BLOCK_1_PTR = 0x03005D8C  # gSaveBlock1Ptr - Player progress, flags, variables
SAVE_BLOCK_2_PTR = 0x03005D90  # gSaveBlock2Ptr - Trainer data, Battle Frontier records

# RNG State - Useful for debugging and RNG manipulation
RNG_VALUE_OFFSET = 0x03005D80   # gRngValue - Current PRNG state (u32)
MAIN_LOOP_OFFSET = 0x030022C0   # gMain - Input keys, callbacks, game state

# ==============================================================================
# FRONTIER DATA - Battle Frontier state (offsets from SaveBlock2)
# ==============================================================================
# All offsets below are added to the VALUE read from SAVE_BLOCK_2_PTR
#
# Level Mode determines stat calculations:
#   0 = Level 50 (all Pokemon scaled to Lv50, recommended for consistency)
#   1 = Open Level (use actual levels, higher level Pokemon allowed)

FRONTIER_LVL_MODE_OFFSET = 0xCA9     # frontier.lvlMode - Only bit 0 matters

# Array of the last 20 trainer IDs faced (for avoiding repeats)
FRONTIER_TRAINER_IDS_OFFSET = 0xCB4  # frontier.trainerIds[20] - Each is u16

# Win streak offsets - organized as [battleMode][lvlMode] arrays
# battleMode: 0=Singles, 1=Doubles, 2=Multis, 3=Link Multis
# lvlMode: 0=Lv50, 1=Open
# Formula: base_offset + 2 * (2 * battleMode + lvlMode)
FRONTIER_TOWER_STREAK_OFFSET = 0xCE0    # Battle Tower - Test of endurance
FRONTIER_DOME_STREAK_OFFSET = 0xD0C     # Battle Dome - Tournament bracket
FRONTIER_PALACE_STREAK_OFFSET = 0xDC8   # Battle Palace - Pokemon choose moves based on nature
FRONTIER_ARENA_STREAK_OFFSET = 0xDDA    # Battle Arena - 3-turn battles judged
FRONTIER_FACTORY_STREAK_OFFSET = 0xDE2  # Battle Factory - Rental Pokemon
FRONTIER_PIKE_STREAK_OFFSET = 0xE04     # Battle Pike - Choose-your-path challenge
FRONTIER_PYRAMID_STREAK_OFFSET = 0xE1A  # Battle Pyramid - Dungeon exploration

# Battle Factory specific - tracks how many times you've swapped/rented Pokemon
FRONTIER_FACTORY_RENTS_OFFSET = 0xDF6   # frontier.factoryRentsCount[mode][lvl]

# Rental Pokemon storage for Battle Factory
# Structure: 6 slots × 12 bytes each
# Each RentalMon (12 bytes):
#   Bytes 0-1: monId (u16) - Index into gFacilityTrainerMons (0-882)
#   Byte 2:    ivs - IV spread identifier
#   Byte 3:    abilityNum - Which ability (0 or 1)
#   Bytes 4-7: personality - For nature/gender determination
#   Bytes 8-11: otId - Original trainer ID
FRONTIER_RENTAL_MONS_OFFSET = 0xE70     # frontier.rentalMons[6]
RENTAL_MON_SIZE = 12                     # Bytes per rental Pokemon entry

# ==============================================================================
# GAME VARIABLES - Scripting variables (offsets from SaveBlock1)
# ==============================================================================
# Variables are stored as u16 array starting at SaveBlock1 + VARS_OFFSET
# Variable address = SaveBlock1 + VARS_OFFSET + 2 * (varId - VARS_START)

VARS_START = 0x4000   # First variable ID
VARS_OFFSET = 0x139C  # Offset from SaveBlock1 to variables array

# These variables track current Frontier challenge state
VAR_FRONTIER_BATTLE_MODE = 0x40CE  # 0=Singles, 1=Doubles, 2=Multis, 3=Link Multis
VAR_FRONTIER_FACILITY = 0x40CF     # Current facility ID (see FACILITY_* constants)

# ==============================================================================
# FACILITY IDS - Battle Frontier location identifiers
# ==============================================================================
FACILITY_TOWER = 0    # Battle Tower - Classic 7-battle streak challenge
FACILITY_DOME = 1     # Battle Dome - 4-round tournament, see opponent info
FACILITY_PALACE = 2   # Battle Palace - Pokemon choose moves based on nature
FACILITY_ARENA = 3    # Battle Arena - 3-turn battles, then judged
FACILITY_FACTORY = 4  # Battle Factory - Rent random Pokemon, swap after wins
FACILITY_PIKE = 5     # Battle Pike - Choose rooms, some have battles
FACILITY_PYRAMID = 6  # Battle Pyramid - Roguelike dungeon, find items

# ==============================================================================
# BATTLE MON STRUCTURE - Field offsets within 88-byte battle struct
# ==============================================================================
# These offsets are used when parsing data from gBattleMons.
# All values are already modified by stat stages and abilities.

# Base stats (after modifications) - Each is u16 (2 bytes)
BATTLE_MON_SPECIES = 0x00      # Species ID (1-386 for Gen 3)
BATTLE_MON_ATTACK = 0x02       # Modified Attack stat
BATTLE_MON_DEFENSE = 0x04      # Modified Defense stat
BATTLE_MON_SPEED = 0x06        # Modified Speed stat (determines turn order)
BATTLE_MON_SP_ATTACK = 0x08    # Modified Special Attack stat
BATTLE_MON_SP_DEFENSE = 0x0A   # Modified Special Defense stat

# Moves - 4 move slots, each u16 (move ID, 0 = empty)
BATTLE_MON_MOVE1 = 0x0C        # First move slot
BATTLE_MON_MOVE2 = 0x0E        # Second move slot
BATTLE_MON_MOVE3 = 0x10        # Third move slot
BATTLE_MON_MOVE4 = 0x12        # Fourth move slot

# PP (Power Points) - 4 bytes, one u8 per move
BATTLE_MON_PP = 0x14           # pp[4] - Current PP for each move

# Stat stages - 8 signed bytes (s8), range -6 to +6
# Order: [HP (unused), Attack, Defense, Speed, SpAtk, SpDef, Accuracy, Evasion]
# Multipliers: -6=2/8, -5=2/7, -4=2/6, -3=2/5, -2=2/4, -1=2/3, 
#              0=1, +1=3/2, +2=4/2, +3=5/2, +4=6/2, +5=7/2, +6=8/2
BATTLE_MON_STAT_STAGES = 0x18  # statStages[8]

# HP values
BATTLE_MON_HP = 0x28           # Current HP (u16)
BATTLE_MON_MAX_HP = 0x2A       # Maximum HP (u16)
BATTLE_MON_LEVEL = 0x2C        # Pokemon level (u8, 1-100)

# Status conditions
BATTLE_MON_STATUS1 = 0x4C      # Primary status (u32) - Sleep, Poison, Burn, etc.
BATTLE_MON_STATUS2 = 0x50      # Volatile status (u32) - Confusion, Flinch, etc.

# ==============================================================================
# STATUS CONDITION FLAGS - Bitfields for status1
# ==============================================================================
# status1 contains non-volatile status conditions (persist after battle ends)

STATUS1_SLEEP = 0x7        # Bits 0-2: Sleep turn counter (1-7, 0 = awake)
STATUS1_POISON = 0x8       # Bit 3: Regular poison (1/8 HP damage per turn)
STATUS1_BURN = 0x10        # Bit 4: Burn (1/16 HP damage, halves Attack)
STATUS1_FREEZE = 0x20      # Bit 5: Frozen (can't move, 20% thaw chance)
STATUS1_PARALYSIS = 0x40   # Bit 6: Paralyzed (25% can't move, 1/4 Speed)
STATUS1_TOXIC = 0x80       # Bit 7: Toxic poison (increasing damage each turn)

# status2 contains volatile conditions (cleared when switching/battle ends)
# These are more complex bitfields - see pokeemerald source for full details

# ==============================================================================
# LEGACY ALIASES - For backward compatibility with older code
# ==============================================================================
# These may not be accurate and should be migrated to SaveBlock-based access

FACTORY_ROOT = 0x02039A00              # Old placeholder, prefer SaveBlock2 access
FACTORY_ROUND_NUMBER_OFFSET = FACTORY_ROOT + 0x00
FACTORY_WIN_STREAK_OFFSET = FACTORY_ROOT + 0x04
RENTAL_POOL_OFFSET = None              # Must use SaveBlock2 + FRONTIER_RENTAL_MONS_OFFSET
SCIENTIST_HINT_OFFSET = None           # TBD - Hints about opponent Pokemon
GAME_STATE_OFFSET = 0x030030F0         # General game state callback pointer