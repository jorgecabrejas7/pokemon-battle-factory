-- mGBA Connector for Battle Factory Agent
-- Uses mGBA's built-in socket API
-- Load this script in mGBA: Tools -> Scripting -> File -> Load Script

-- Create server socket using mGBA's socket API
local server = socket.bind(nil, 7777)  -- nil = bind to all interfaces
if not server then
    console:log("ERROR: Failed to bind to port 7777")
    return
end

local ok, err = server:listen()
if not ok then
    console:log("ERROR: Failed to listen: " .. tostring(err))
    return
end

console:log("Battle Factory Agent listening on port 7777")
console:log("Commands: PING, READ_BLOCK, READ_U16, READ_U32, READ_PTR, WRITE_BYTE, SET_INPUT, FRAME_ADVANCE, RESET")

local client = nil
local current_keys = {}

function parseCommand(line)
    local parts = {}
    for part in string.gmatch(line, "%S+") do
        table.insert(parts, part)
    end
    return parts
end

function handleCommand(line)
    local parts = parseCommand(line)
    local cmd = parts[1]
    
    if cmd == "PING" then
        return "PONG"
        
    elseif cmd == "READ_BLOCK" then
        -- READ_BLOCK <addr_hex> <size_hex>
        -- Returns hex string of bytes
        local addr = tonumber(parts[2], 16)
        local size = tonumber(parts[3], 16)
        if not addr or not size then
            return "ERROR: Invalid address or size"
        end
        local hex_str = ""
        for i = 0, size - 1 do
            local byte = emu:read8(addr + i)
            hex_str = hex_str .. string.format("%02X", byte)
        end
        return hex_str
        
    elseif cmd == "READ_U16" then
        -- READ_U16 <addr_hex>
        -- Returns decimal value of u16 at address (little-endian)
        local addr = tonumber(parts[2], 16)
        if not addr then
            return "ERROR: Invalid address"
        end
        local lo = emu:read8(addr)
        local hi = emu:read8(addr + 1)
        local value = lo + (hi * 256)
        return tostring(value)
        
    elseif cmd == "READ_U32" then
        -- READ_U32 <addr_hex>
        -- Returns decimal value of u32 at address (little-endian)
        local addr = tonumber(parts[2], 16)
        if not addr then
            return "ERROR: Invalid address"
        end
        local b0 = emu:read8(addr)
        local b1 = emu:read8(addr + 1)
        local b2 = emu:read8(addr + 2)
        local b3 = emu:read8(addr + 3)
        local value = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        return tostring(value)
        
    elseif cmd == "READ_PTR" then
        -- READ_PTR <ptr_addr_hex> <offset_hex> <size_hex>
        -- Reads pointer at ptr_addr, adds offset, then reads size bytes
        -- Useful for SaveBlock access: READ_PTR 03005D90 E70 48
        local ptr_addr = tonumber(parts[2], 16)
        local offset = tonumber(parts[3], 16)
        local size = tonumber(parts[4], 16)
        if not ptr_addr or not offset or not size then
            return "ERROR: Invalid parameters"
        end
        -- Read the pointer value (4 bytes, little-endian)
        local b0 = emu:read8(ptr_addr)
        local b1 = emu:read8(ptr_addr + 1)
        local b2 = emu:read8(ptr_addr + 2)
        local b3 = emu:read8(ptr_addr + 3)
        local base_addr = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        -- Calculate target address
        local target_addr = base_addr + offset
        -- Read the data
        local hex_str = ""
        for i = 0, size - 1 do
            local byte = emu:read8(target_addr + i)
            hex_str = hex_str .. string.format("%02X", byte)
        end
        return hex_str
        
    elseif cmd == "READ_PTR_U16" then
        -- READ_PTR_U16 <ptr_addr_hex> <offset_hex>
        -- Reads pointer, adds offset, reads u16
        local ptr_addr = tonumber(parts[2], 16)
        local offset = tonumber(parts[3], 16)
        if not ptr_addr or not offset then
            return "ERROR: Invalid parameters"
        end
        local b0 = emu:read8(ptr_addr)
        local b1 = emu:read8(ptr_addr + 1)
        local b2 = emu:read8(ptr_addr + 2)
        local b3 = emu:read8(ptr_addr + 3)
        local base_addr = b0 + (b1 * 256) + (b2 * 65536) + (b3 * 16777216)
        local target_addr = base_addr + offset
        local lo = emu:read8(target_addr)
        local hi = emu:read8(target_addr + 1)
        return tostring(lo + (hi * 256))
        
    elseif cmd == "WRITE_BYTE" then
        -- WRITE_BYTE <addr_hex> <value_hex>
        local addr = tonumber(parts[2], 16)
        local val = tonumber(parts[3], 16)
        if not addr or not val then
            return "ERROR: Invalid address or value"
        end
        emu:write8(addr, val)
        return "OK"
        
    elseif cmd == "FRAME_ADVANCE" then
        -- FRAME_ADVANCE <count>
        local count = tonumber(parts[2]) or 1
        for i = 1, count do
            emu:setKeys(current_keys)
            emu:runFrame()
        end
        return "OK"
        
    elseif cmd == "SET_INPUT" then
        -- SET_INPUT <button_mask>
        -- Bitmask: A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512
        local mask = tonumber(parts[2])
        if not mask then
            return "ERROR: Invalid mask"
        end
        emu:clearKeys(0x3FF)  -- Clear all 10 keys
        if mask ~= 0 then
            emu:addKeys(mask)
        end
        return "OK"
        
    elseif cmd == "RESET" then
        emu:reset()
        return "OK"
        
    elseif cmd == "HELP" then
        return "Commands: PING, READ_BLOCK, READ_U16, READ_U32, READ_PTR, READ_PTR_U16, WRITE_BYTE, SET_INPUT, FRAME_ADVANCE, RESET"
        
    else
        return "ERROR: Unknown Command '" .. tostring(cmd) .. "'"
    end
end

-- Add callback for incoming connections
server:add("received", function()
    if not client then
        client = server:accept()
        if client then
            console:log("Client connected!")
            -- Add callback for client data
            client:add("received", function()
                local data = client:receive(1024)
                if data then
                    -- Split by newlines in case multiple commands
                    for line in string.gmatch(data, "[^\r\n]+") do
                        console:log("Received: " .. line)
                        local response = handleCommand(line)
                        client:send(response .. "\n")
                    end
                end
            end)
            client:add("error", function()
                console:log("Client disconnected")
                client = nil
            end)
        end
    end
end)

callbacks:add("frame", function()
    -- Poll sockets for events
    server:poll()
    if client then
        client:poll()
    end
end)
