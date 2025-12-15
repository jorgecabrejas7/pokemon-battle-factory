--[[
================================================================================
mGBA Connector Script for Battle Factory RL Agent
================================================================================

PURPOSE:
    This Lua script creates a TCP server inside mGBA that allows external Python
    programs to control the emulator and read game memory. It serves as the
    communication bridge between the RL training system and the Pokemon Emerald
    game running in the emulator.

USAGE:
    1. Open mGBA with Pokemon Emerald (USA) ROM loaded
    2. Go to: Tools -> Scripting -> File -> Load Script
    3. Select this file (connector.lua)
    4. Console should show "Battle Factory Agent listening on port 7777"
    5. Run the Python backend to connect

ARCHITECTURE:
    ┌─────────────────┐         TCP Socket         ┌──────────────────┐
    │  Python Agent   │ ◄──────────────────────► │  mGBA Emulator    │
    │  (RL Training)  │     Port 7777             │  (This Script)   │
    └─────────────────┘                           └──────────────────┘

PROTOCOL:
    - Text-based command/response protocol over TCP
    - Commands are sent as single lines ending with \n
    - Responses are single lines ending with \n
    - Multiple commands can be sent in sequence

SUPPORTED COMMANDS:
    Memory Reading:
        - PING                          → Test connection, returns "PONG"
        - READ_BLOCK <addr> <size>      → Read raw bytes as hex string
        - READ_U16 <addr>               → Read 16-bit unsigned integer
        - READ_U32 <addr>               → Read 32-bit unsigned integer
        - READ_PTR <ptr> <off> <size>   → Read through pointer indirection
        - READ_PTR_U16 <ptr> <offset>   → Read u16 through pointer
    
    Memory Writing:
        - WRITE_BYTE <addr> <value>     → Write single byte to memory
    
    Emulator Control:
        - SET_INPUT <mask>              → Set button state (bitmask)
        - FRAME_ADVANCE <count>         → Run emulator for N frames
        - RESET                         → Reset the emulator
    
    RL-Specific Commands:
        - IS_WAITING_INPUT              → Check if battle awaits player input
        - GET_BATTLE_OUTCOME            → Get battle result (win/loss/ongoing)
        - READ_LAST_MOVES               → Get last move used and by whom
        - READ_RNG                      → Read current PRNG state

MEMORY ADDRESSES:
    All addresses are for Pokemon Emerald USA (BPEE).
    Verified against pret/pokeemerald decompilation project.
    See src/backends/emerald/constants.py for full memory map.

AUTHOR: Battle Factory RL Project
VERSION: 2.0 (with RL commands)
================================================================================
--]]

-- =============================================================================
-- INITIALIZATION
-- =============================================================================

-- Create TCP server socket using mGBA's built-in socket API
-- Bind to all interfaces (nil) on port 7777
local server = socket.bind(nil, 7777)
if not server then
    console:log("ERROR: Failed to bind to port 7777")
    console:log("       Another process may be using this port.")
    console:log("       Close any other mGBA instances and try again.")
    return
end

-- Start listening for incoming connections
local ok, err = server:listen()
if not ok then
    console:log("ERROR: Failed to listen: " .. tostring(err))
    return
end

-- Display startup message with available commands
console:log("================================================================================")
console:log("Battle Factory RL Agent - mGBA Connector v2.0")
console:log("================================================================================")
console:log("Listening on port 7777")
console:log("")
console:log("Memory Commands:")
console:log("  PING, READ_BLOCK, READ_U16, READ_U32, READ_PTR, READ_PTR_U16, WRITE_BYTE")
console:log("")
console:log("Control Commands:")
console:log("  SET_INPUT, FRAME_ADVANCE, RESET")
console:log("")
console:log("RL Commands:")
console:log("  IS_WAITING_INPUT, GET_BATTLE_OUTCOME, READ_LAST_MOVES, READ_RNG")
console:log("================================================================================")

-- =============================================================================
-- MEMORY ADDRESSES (BPEE - Pokemon Emerald USA)
-- =============================================================================
-- These addresses are verified against the pret/pokeemerald decompilation.
-- They are used by the RL-specific commands for efficient state polling.

-- gBattleControllerExecFlags: Bitfield indicating which battle controllers are busy
-- When this equals 0, all controllers are idle and the game is waiting for input
-- Address: 0x02023E4C in EWRAM
local ADDR_BATTLE_INPUT_WAIT = 0x02023E4C

-- gBattleOutcome: Single byte indicating battle result
-- Values: 0 = Ongoing, 1 = Player Won, 2 = Player Lost, 3 = Draw, 4 = Ran Away
-- Address: 0x02023EAC in EWRAM
local ADDR_BATTLE_OUTCOME = 0x02023EAC

-- gLastUsedMove: 16-bit move ID of the most recently executed move
-- Updated after each move animation completes
-- Address: 0x02023E6C in EWRAM
local ADDR_LAST_USED_MOVE = 0x02023E6C

-- gBattlerAttacker: Byte indicating which battler (0-3) used the last move
-- 0 = Player slot 1, 1 = Enemy slot 1, 2 = Player slot 2, 3 = Enemy slot 2
-- Address: 0x02023D6C in EWRAM
local ADDR_BATTLER_ATTACKER = 0x02023D6C

-- gRngValue: 32-bit PRNG state used for all random number generation
-- Useful for debugging RNG manipulation and understanding randomness
-- Address: 0x03005D80 in IWRAM
local ADDR_RNG_VALUE = 0x03005D80

-- =============================================================================
-- STATE VARIABLES
-- =============================================================================

-- Currently connected client socket (nil if no client connected)
local client = nil

-- Current button state mask to apply during FRAME_ADVANCE
-- This allows holding buttons across multiple frames
-- Set by SET_INPUT command
local current_key_mask = 0

-- Command counter for debugging
local command_count = 0

-- =============================================================================
-- UTILITY FUNCTIONS
-- =============================================================================

--[[
    Decode button mask to human-readable button names.
    
    Args:
        mask: Button bitmask value
    
    Returns:
        String with button names (e.g., "A+B" or "NONE" or "A+B+UP")
--]]
local function decode_button_mask(mask)
    if mask == 0 then
        return "NONE (release)"
    end
    
    local buttons = {}
    -- Check each bit position using division and modulo
    -- Button bitmask: A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512
    if math.floor(mask / 1) % 2 >= 1 then table.insert(buttons, "A") end
    if math.floor(mask / 2) % 2 >= 1 then table.insert(buttons, "B") end
    if math.floor(mask / 4) % 2 >= 1 then table.insert(buttons, "SELECT") end
    if math.floor(mask / 8) % 2 >= 1 then table.insert(buttons, "START") end
    if math.floor(mask / 16) % 2 >= 1 then table.insert(buttons, "RIGHT") end
    if math.floor(mask / 32) % 2 >= 1 then table.insert(buttons, "LEFT") end
    if math.floor(mask / 64) % 2 >= 1 then table.insert(buttons, "UP") end
    if math.floor(mask / 128) % 2 >= 1 then table.insert(buttons, "DOWN") end
    if math.floor(mask / 256) % 2 >= 1 then table.insert(buttons, "R") end
    if math.floor(mask / 512) % 2 >= 1 then table.insert(buttons, "L") end
    
    if #buttons == 0 then
        return "UNKNOWN(0x" .. string.format("%03X", mask) .. ")"
    end
    
    return table.concat(buttons, "+")
end

--[[
    Parse a command string into an array of space-separated parts.
    
    Example: "READ_BLOCK 02024084 58" -> {"READ_BLOCK", "02024084", "58"}
    
    @param line: The raw command string
    @return: Array of string parts
--]]
function parseCommand(line)
    local parts = {}
    for part in string.gmatch(line, "%S+") do
        table.insert(parts, part)
    end
    return parts
end

-- =============================================================================
-- COMMAND HANDLER
-- =============================================================================

--[[
    Process a single command and return the response string.
    
    This is the main dispatch function that routes commands to their handlers.
    All commands return a single-line string response.
    
    @param line: The command string to process
    @return: Response string to send back to client
--]]
function handleCommand(line)
    local parts = parseCommand(line)
    local cmd = parts[1]
    
    -- Increment command counter
    command_count = command_count + 1
    
    -- =========================================================================
    -- BASIC COMMANDS
    -- =========================================================================
    
    if cmd == "PING" then
        -- Simple connection test
        -- Usage: PING
        -- Returns: "PONG"
        console:log(string.format("[CMD #%d] PING -> PONG", command_count))
        return "PONG"
        
    -- =========================================================================
    -- MEMORY READING COMMANDS
    -- =========================================================================
        
    elseif cmd == "READ_BLOCK" then
        -- Read a contiguous block of memory as hexadecimal string
        -- Usage: READ_BLOCK <address_hex> <size_hex>
        -- Returns: Hex string of bytes (e.g., "0A1B2C3D...")
        -- Example: READ_BLOCK 02024084 58  (reads 88 bytes of battle mon data)
        
        local addr = tonumber(parts[2], 16)
        local size = tonumber(parts[3], 16)
        if not addr or not size then
            return "ERROR: Invalid address or size. Usage: READ_BLOCK <addr_hex> <size_hex>"
        end
        
        -- Read each byte and convert to hex
        local hex_str = ""
        for i = 0, size - 1 do
            local byte = emu:read8(addr + i)
            hex_str = hex_str .. string.format("%02X", byte)
        end
        return hex_str
        
    elseif cmd == "READ_U16" then
        -- Read a 16-bit unsigned integer (little-endian)
        -- Usage: READ_U16 <address_hex>
        -- Returns: Decimal value as string
        -- Example: READ_U16 02024084  (reads species ID from battle mon)
        
        local addr = tonumber(parts[2], 16)
        if not addr then
            return "ERROR: Invalid address. Usage: READ_U16 <addr_hex>"
        end
        
        -- GBA is little-endian: low byte first, then high byte
        local lo = emu:read8(addr)
        local hi = emu:read8(addr + 1)
        local value = lo + (hi * 256)
        return tostring(value)
        
    elseif cmd == "READ_U32" then
        -- Read a 32-bit unsigned integer (little-endian)
        -- Usage: READ_U32 <address_hex>
        -- Returns: Decimal value as string
        -- Example: READ_U32 03005D80  (reads RNG value)
        
        local addr = tonumber(parts[2], 16)
        if not addr then
            return "ERROR: Invalid address. Usage: READ_U32 <addr_hex>"
        end
        
        -- Read 4 bytes in little-endian order
        local b0 = emu:read8(addr)
        local b1 = emu:read8(addr + 1)
        local b2 = emu:read8(addr + 2)
        local b3 = emu:read8(addr + 3)
        local value = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        return tostring(value)
        
    elseif cmd == "READ_PTR" then
        -- Read memory through pointer indirection
        -- Usage: READ_PTR <ptr_addr_hex> <offset_hex> <size_hex>
        -- Returns: Hex string of bytes at (ptr_value + offset)
        -- 
        -- This is essential for reading SaveBlock data where the base address
        -- varies between game sessions.
        -- Example: READ_PTR 03005D90 E70 48
        --          (reads rental Pokemon from SaveBlock2 + 0xE70)
        
        local ptr_addr = tonumber(parts[2], 16)
        local offset = tonumber(parts[3], 16)
        local size = tonumber(parts[4], 16)
        if not ptr_addr or not offset or not size then
            return "ERROR: Invalid parameters. Usage: READ_PTR <ptr_hex> <offset_hex> <size_hex>"
        end
        
        -- First, read the 4-byte pointer value
        local b0 = emu:read8(ptr_addr)
        local b1 = emu:read8(ptr_addr + 1)
        local b2 = emu:read8(ptr_addr + 2)
        local b3 = emu:read8(ptr_addr + 3)
        local base_addr = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        
        -- Calculate the target address and read the data
        local target_addr = base_addr + offset
        local hex_str = ""
        for i = 0, size - 1 do
            local byte = emu:read8(target_addr + i)
            hex_str = hex_str .. string.format("%02X", byte)
        end
        return hex_str
        
    elseif cmd == "READ_PTR_U16" then
        -- Read a 16-bit value through pointer indirection
        -- Usage: READ_PTR_U16 <ptr_addr_hex> <offset_hex>
        -- Returns: Decimal value as string
        -- Example: READ_PTR_U16 03005D90 DE2
        --          (reads Factory win streak from SaveBlock2 + 0xDE2)
        
        local ptr_addr = tonumber(parts[2], 16)
        local offset = tonumber(parts[3], 16)
        if not ptr_addr or not offset then
            return "ERROR: Invalid parameters. Usage: READ_PTR_U16 <ptr_hex> <offset_hex>"
        end
        
        -- Read pointer and dereference
        local b0 = emu:read8(ptr_addr)
        local b1 = emu:read8(ptr_addr + 1)
        local b2 = emu:read8(ptr_addr + 2)
        local b3 = emu:read8(ptr_addr + 3)
        local base_addr = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        local target_addr = base_addr + offset
        
        -- Read u16 at target
        local lo = emu:read8(target_addr)
        local hi = emu:read8(target_addr + 1)
        return tostring(lo + (hi * 256))
    
    -- =========================================================================
    -- MEMORY WRITING COMMANDS
    -- =========================================================================
        
    elseif cmd == "WRITE_BYTE" then
        -- Write a single byte to memory
        -- Usage: WRITE_BYTE <address_hex> <value_hex>
        -- Returns: "OK" on success
        -- WARNING: Writing to wrong addresses can crash the game!
        
        local addr = tonumber(parts[2], 16)
        local val = tonumber(parts[3], 16)
        if not addr or not val then
            return "ERROR: Invalid address or value. Usage: WRITE_BYTE <addr_hex> <value_hex>"
        end
        
        emu:write8(addr, val)
        return "OK"
    
    -- =========================================================================
    -- EMULATOR CONTROL COMMANDS
    -- =========================================================================
        
    elseif cmd == "FRAME_ADVANCE" then
        -- DEPRECATED: The emulator runs continuously, no need to advance frames.
        -- Waits should be handled by Python using time.sleep().
        -- Kept for backwards compatibility but does nothing.
        -- Usage: FRAME_ADVANCE [count]
        -- Returns: "OK" immediately
        local count = tonumber(parts[2]) or 0
        local frame = emu:getFrameCount()
        console:log(string.format("[CMD #%d] FRAME_ADVANCE(%d) -> OK (current frame=%d)", 
            command_count, count, frame))
        return "OK"
        
    elseif cmd == "SET_INPUT" then
        -- Set the button input state using a bitmask
        -- Usage: SET_INPUT <button_mask>
        -- Returns: "OK"
        --
        -- Button Bitmask Values:
        --   A      = 0x001 (1)
        --   B      = 0x002 (2)
        --   SELECT = 0x004 (4)
        --   START  = 0x008 (8)
        --   RIGHT  = 0x010 (16)
        --   LEFT   = 0x020 (32)
        --   UP     = 0x040 (64)
        --   DOWN   = 0x080 (128)
        --   R      = 0x100 (256)
        --   L      = 0x200 (512)
        --
        -- To press A+B simultaneously: SET_INPUT 3 (1+2)
        -- To release all buttons: SET_INPUT 0
        
        local mask = tonumber(parts[2])
        if not mask then
            return "ERROR: Invalid mask. Usage: SET_INPUT <button_mask_decimal>"
        end
        
        -- Decode and log button press
        local button_names = decode_button_mask(mask)
        local frame_count = emu:getFrameCount()
        local mask_hex = string.format("0x%03X", mask)
        
        if mask == 0 then
            console:log(string.format("[INPUT] Frame %d: RELEASE ALL BUTTONS (mask=%s)", frame_count, mask_hex))
        else
            console:log(string.format("[INPUT] Frame %d: PRESS %s (mask=%s, decimal=%d)", 
                frame_count, button_names, mask_hex, mask))
        end
        
        -- Store the mask for use in FRAME_ADVANCE
        current_key_mask = mask
        
        -- Clear all buttons first
        emu:clearKeys(0x3FF)  -- 0x3FF = all 10 GBA buttons
        
        -- Set new button state
        if mask ~= 0 then
            emu:addKeys(mask)
        end
        return "OK"
        
    elseif cmd == "RESET" then
        -- Reset the emulator (soft reset)
        -- Usage: RESET
        -- Returns: "OK"
        -- Note: This is equivalent to pressing the reset button, not a full restart
        
        local frame = emu:getFrameCount()
        console:log(string.format("[CMD #%d] RESET (frame=%d)", command_count, frame))
        emu:reset()
        return "OK"
        
    -- =========================================================================
    -- RL AGENT COMMANDS (Event-Driven)
    -- =========================================================================
    -- These commands are optimized for RL training, providing quick access
    -- to commonly-needed battle state information without reading large
    -- memory blocks.
    
    elseif cmd == "IS_WAITING_INPUT" then
        -- Check if the battle system is waiting for player input
        -- Usage: IS_WAITING_INPUT
        -- Returns: "YES" if waiting for input, "NO" if busy (animating, etc.)
        --
        -- This reads gBattleControllerExecFlags which is a bitfield tracking
        -- which battle controllers are currently executing. When all controllers
        -- are idle (value = 0), the game is waiting for the player's next action.
        --
        -- Use this to know when to:
        --   1. Read the current battle state
        --   2. Inject the next action
        
        local flags = emu:read32(ADDR_BATTLE_INPUT_WAIT)
        local frame = emu:getFrameCount()
        local result = (flags == 0) and "YES" or "NO"
        console:log(string.format("[CMD #%d] IS_WAITING_INPUT -> %s (flags=0x%08X, frame=%d)", 
            command_count, result, flags, frame))
        return result
        
    elseif cmd == "GET_BATTLE_OUTCOME" then
        -- Get the current battle outcome
        -- Usage: GET_BATTLE_OUTCOME
        -- Returns: Single digit string
        --   "0" = Battle ongoing (no outcome yet)
        --   "1" = Player won the battle
        --   "2" = Player lost the battle
        --   "3" = Battle ended in a draw
        --   "4" = Player ran away from battle
        --
        -- Check this after IS_WAITING_INPUT returns NO to see if battle ended
        
        local outcome = emu:read8(ADDR_BATTLE_OUTCOME)
        local outcome_names = {"ONGOING", "WIN", "LOSS", "DRAW", "RAN"}
        local outcome_name = outcome_names[outcome + 1] or "UNKNOWN"
        local frame = emu:getFrameCount()
        console:log(string.format("[CMD #%d] GET_BATTLE_OUTCOME -> %d (%s, frame=%d)", 
            command_count, outcome, outcome_name, frame))
        return tostring(outcome)
        
    elseif cmd == "READ_LAST_MOVES" then
        -- Read the most recently used move and who used it
        -- Usage: READ_LAST_MOVES
        -- Returns: "move_id,attacker_slot" (comma-separated)
        --   move_id: The ID of the move (0-354)
        --   attacker_slot: Who used it (0=Player1, 1=Enemy1, 2=Player2, 3=Enemy2)
        --
        -- Example response: "89,1" means Enemy used move #89 (Earthquake)
        --
        -- Use this to:
        --   1. Track what moves the enemy has revealed
        --   2. Verify your action was executed correctly
        --   3. Build battle history for the LSTM model
        
        local move_id = emu:read16(ADDR_LAST_USED_MOVE)
        local attacker = emu:read8(ADDR_BATTLER_ATTACKER)
        local frame = emu:getFrameCount()
        local attacker_names = {"Player1", "Enemy1", "Player2", "Enemy2"}
        local attacker_name = attacker_names[attacker + 1] or "Unknown"
        console:log(string.format("[CMD #%d] READ_LAST_MOVES -> move_id=%d, attacker=%d (%s, frame=%d)", 
            command_count, move_id, attacker, attacker_name, frame))
        return tostring(move_id) .. "," .. tostring(attacker)
        
    elseif cmd == "READ_RNG" then
        -- Read the current PRNG (Pseudo-Random Number Generator) state
        -- Usage: READ_RNG
        -- Returns: Decimal value of the 32-bit RNG state
        --
        -- Pokemon Emerald uses a Linear Congruential Generator (LCG):
        --   next = (current * 0x41C64E6D + 0x6073) & 0xFFFFFFFF
        --
        -- This is useful for:
        --   1. Debugging randomness-related issues
        --   2. RNG manipulation research
        --   3. Verifying determinism in test scenarios
        
        local rng = emu:read32(ADDR_RNG_VALUE)
        local frame = emu:getFrameCount()
        console:log(string.format("[CMD #%d] READ_RNG -> 0x%08X (decimal=%u, frame=%d)", 
            command_count, rng, rng, frame))
        return tostring(rng)
        
    elseif cmd == "HELP" then
        -- Display available commands
        return "Commands: PING, READ_BLOCK, READ_U16, READ_U32, READ_PTR, READ_PTR_U16, WRITE_BYTE, SET_INPUT, FRAME_ADVANCE, RESET, IS_WAITING_INPUT, GET_BATTLE_OUTCOME, READ_LAST_MOVES, READ_RNG"
        
    else
        return "ERROR: Unknown command '" .. tostring(cmd) .. "'. Send HELP for command list."
    end
end

-- =============================================================================
-- SOCKET EVENT HANDLERS
-- =============================================================================

--[[
    Handle new client connections.
    
    This callback is triggered when a client attempts to connect to our server.
    We only accept one client at a time - if a client is already connected,
    new connection attempts are ignored.
--]]
server:add("received", function()
    if not client then
        client = server:accept()
        if client then
            local frame = emu:getFrameCount()
            console:log("================================================================================")
            console:log(string.format("✅ CLIENT CONNECTED from Python backend (frame=%d)", frame))
            console:log("================================================================================")
            command_count = 0  -- Reset counter on new connection
            
            -- Set up data receive handler for this client
            client:add("received", function()
                local data = client:receive(1024)
                if data then
                    -- Process each line (command) in the received data
                    -- Commands are newline-separated
                    for line in string.gmatch(data, "[^\r\n]+") do
                        -- Process command and send response
                        local response = handleCommand(line)
                        client:send(response .. "\n")
                        
                        -- Log response for debugging (truncate long responses)
                        -- Note: Command details are logged inside handleCommand()
                        -- Only log errors or very long responses to avoid spam
                        if string.find(response, "ERROR") then
                            console:log(string.format("[RESPONSE] ❌ %s", response))
                        elseif #response > 100 then
                            console:log(string.format("[RESPONSE] %s... (%d bytes)", string.sub(response, 1, 50), #response))
                        end
                    end
                end
            end)
            
            -- Handle client disconnect
            client:add("error", function()
                local frame = emu:getFrameCount()
                console:log("================================================================================")
                console:log(string.format("❌ CLIENT DISCONNECTED (frame=%d, total commands=%d)", frame, command_count))
                console:log("================================================================================")
                client = nil
                command_count = 0
            end)
        end
    end
end)

-- =============================================================================
-- MAIN LOOP (Frame Callback)
-- =============================================================================

--[[
    Per-frame callback to poll socket events.
    
    mGBA's socket API is event-driven but requires explicit polling.
    This callback runs every frame to check for new data/connections.
    
    Note: The emulator does NOT pause while waiting for commands.
    The RL agent is responsible for controlling timing via FRAME_ADVANCE.
--]]
callbacks:add("frame", function()
    -- Poll server for new connection attempts
    server:poll()
    
    -- Poll client for incoming data
    if client then
        client:poll()
    end
end)

--[[
================================================================================
END OF CONNECTOR SCRIPT
================================================================================
--]]
