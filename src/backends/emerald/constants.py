# RAM Offsets for Pokemon Emerald (US/UK)

# ------------------------------------------------------------------------------
# Party Data
# ------------------------------------------------------------------------------
# Each party is 6 Pokemon * 100 bytes = 600 bytes.
# Note: Data is encrypted using the Personality Value and OT ID.
PLAYER_PARTY_OFFSET = 0x020244EC
ENEMY_PARTY_OFFSET  = 0x0202402C

# Pokemon Structure Sizes
POKEMON_SIZE_BYTES = 100
SUBSTRUCT_SIZE_BYTES = 12

# ------------------------------------------------------------------------------
# Battle Data
# ------------------------------------------------------------------------------
# Battle Structs (Active Pokemon stats, volatile status, etc.)
BATTLE_STRUCT_SIZE = 0x58 # Verify size
PLAYER_BATTLE_STRUCT_OFFSET = 0x02023BE4 # Approximate
ENEMY_BATTLE_STRUCT_OFFSET  = 0x02023BE4 + BATTLE_STRUCT_SIZE # Approximate index 1

# Specific Battle State Flags
# "Is Input Required?" flag. This is crucial for the RL agent timing.
# 0 = Busy/Animating, 1 = Waiting for Input
BATTLE_INPUT_WAIT_FLAG_OFFSET = 0x02023E4C # Check if 0x030030F0 or similar in other docs

# Current Turn Counter
TURN_COUNTER_OFFSET = 0x02023E82

# ------------------------------------------------------------------------------
# Factory / Frontier Data
# ------------------------------------------------------------------------------
# Battle Factory specific variables
FACTORY_ROOT = 0x02039A00 # Placeholder for Factory Struct start
FACTORY_ROUND_NUMBER_OFFSET = FACTORY_ROOT + 0x00
FACTORY_WIN_STREAK_OFFSET   = FACTORY_ROOT + 0x04

# Rental Pool
# This is usually generated into a temporary array before selection.
# Finding this requires scanning RAM during the "Draft" phase.
RENTAL_POOL_OFFSET = None # TBD: Requires live RAM scan

# Opponent Scientist Hints
# The 'Hint' ID provided by the scientist before battle.
SCIENTIST_HINT_OFFSET = None # TBD

# ------------------------------------------------------------------------------
# Game State Flags
# ------------------------------------------------------------------------------
# 0 = Overworld, 1 = Battle, etc.
GAME_STATE_OFFSET = 0x030030F0 # Callback? Or detailed state?
