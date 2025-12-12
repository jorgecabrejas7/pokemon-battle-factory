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
        local addr = tonumber(parts[2], 16)
        local size = tonumber(parts[3], 16)
        local hex_str = ""
        for i = 0, size - 1 do
            local byte = emu:read8(addr + i)
            hex_str = hex_str .. string.format("%02X", byte)
        end
        return hex_str
        
    elseif cmd == "WRITE_BYTE" then
        local addr = tonumber(parts[2], 16)
        local val = tonumber(parts[3], 16)
        emu:write8(addr, val)
        return "OK"
        
    elseif cmd == "FRAME_ADVANCE" then
        local count = tonumber(parts[2]) or 1
        for i = 1, count do
            emu:setKeys(current_keys)
            emu:runFrame()
        end
        return "OK"
        
    elseif cmd == "SET_INPUT" then
        local mask = tonumber(parts[2])
        -- Clear all keys first, then add the requested ones
        -- Bitmask: A=1, B=2, SELECT=4, START=8, RIGHT=16, LEFT=32, UP=64, DOWN=128, R=256, L=512
        emu:clearKeys(0x3FF)  -- Clear all 10 keys
        if mask ~= 0 then
            emu:addKeys(mask)
            console:log("Setting keys with mask: " .. mask)
        end
        return "OK"
        
    elseif cmd == "RESET" then
        emu:reset()
        return "OK"
        
    else
        return "ERROR: Unknown Command"
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
