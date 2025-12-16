# Pokemon Emerald Battle Factory Memory Map

| Variable | C Variable Name | Address (Hex) | Type | RL Usage |
| :--- | :--- | :--- | :--- | :--- |
| **Battle Outcome** | `gBattleOutcome` | `0x0202433a` | `u8` | `0x0`=On-going, `0x1`=Win, `0x2`=Loss |
| **Battle State** | `gBattleCommunication` | `0x02024332` | `u8[]` | Read `[0]` or specific index for state |
| **Input Lock** | `gBattlerInMenuId` | `0x020244b8` | `u8` | Who is currently selecting an action |
| **Active Mons** | `gBattleMons` | `0x02024084` | `BattlePokemon[]` | Data for currently fighting pokemon |
| **Last Moves** | `gLastMoves` | `0x02024248` | `u16[]` | Previous move used by each battler |
| **Battle Type** | `gBattleTypeFlags` | `0x02022fec` | `u32` | Single/Double/Factory/Link flags |
| **Timers/Disable**| `gDisableStructs` | `0x020242bc` | `DisableStruct[]` | Encore/Disable/Taunt counters |
| **Enemy Party** | `gEnemyParty` | `0x02024744` | `Pokemon[]` | Full enemy team (for swapping) |
| **RNG Seed** | `gRngValue` | `0x03005d80` | `u32` | Internal RNG state (IWRAM) |
| **Main Loop** | `gMain` | `0x030022c0` | `struct Main` | Input keys, callbacks, game state |
| **SaveBlock2** | `gSaveblock2` | `0x02024a54` | `struct SaveBlock2`| Contains Battle Frontier Data |
| **Weather** | `gBattleWeather` | `0x020243cc` | `u16` | Current weather state |
| **Side Timers** | `gSideTimers` | `0x02024294` | `struct SideTimer[]` | Reflect/LightScreen/Mist/SafeGuard |
| **Player Party** | `gPlayerParty` | `0x020244ec` | `struct Pokemon[]` | Player's full bench (Size 6) |
| **Action Cursor** | `gActionSelectionCursor` | `0x020244ac` | `u8[]` | Current cursor for Fight/Bag/Pokemon/Run |
| **Move Cursor** | `gMoveSelectionCursor` | `0x020244b0` | `u8[]` | Current cursor for Move 1-4 |
| **Move Results** | `gMoveResultFlags` | `0x0202427c` | `u8` | `MOVE_RESULT_MISSED`, `SUPER_EFFECTIVE`, etc. |
| **Battle Resources**| `gBattleResources` | `0x020244a8` | `struct BattleResources*` | Pointer to AI Data (See Notes) |

## Battle Frontier Data Offsets
The Battle Frontier data is located within `gSaveblock2`.
**Base Address**: `0x02024a54` (gSaveblock2)
**Frontier Offset**: `+ 0x64C`
**Frontier Base**: `0x020250A0`

| field | Relative Offset | Absolute Address | Type | Description |
| :--- | :--- | :--- | :--- | :--- |
| `curChallengeBattleNum` | `+ 0xCB2` | `0x02025D52` | `u16` | Round number (0-6) |
| `factoryWinStreaks` | `+ 0xDE2` | `0x02025E82` | `u16[][]` | Current Win Streak |
| `rentalMons` | `+ 0xE70` | `0x02025F10` | `RentalMon[]` | Draft/Swap Candidates |
| `factoryRentsCount` | `+ 0xDF6` | `0x02025E96` | `u16[][]` | Number of rentals used |

## Important Constants (Battle Outcome)
- `1`: Won
- `2`: Lost
- `3`: Drew
- `4`: Ran
- `7`: Caught (Not applicable in Factory)

## AI Flags Access (Pointer Chain)
`gBattleResources` is a pointer to a struct allocated on the heap.
1. Read **Pointer** at `0x020244a8` -> gets `Address A` (Base of `BattleResources`)
2. Read **Pointer** at `Address A + 0x14` -> gets `Address B` (Base of `AI_ThinkingStruct`)
3. Read **u32** at `Address B + 0x0C` -> `aiFlags`
    *   `1`: Check Bad Move
    *   `2`: Try To Faint
    *   `4`: Viability
    *   `8`: Setup First Turn
    *   (See `include/battle_ai_script_commands.h`)

## Notes
- **Memory Regions**:
    - `0x02000000`: EWRAM (External Work RAM) - Most game logic variables.
    - `0x03000000`: IWRAM (Internal Work RAM) - Fast variables like RNG, Stack.
- `gBattleMons` logic: The array index corresponds to `gBattlerPartyIndexes`. In Single Battle, usually `0` is Player, `1` is Opponent.
