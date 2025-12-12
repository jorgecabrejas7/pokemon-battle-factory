-- BizHawk Connector for Battle Factory Agent
-- Acts as a TCP Server to receive commands from Python

local socket = require("socket")
local port = 7777
local server = assert(socket.bind("*", port))
print("Battle Factory Agent listening on port " .. port)

local client = nil
local frame_buffer = {}

-- Main Loop
while true do
    -- Wait for connection
    if not client then
        print("Waiting for client...")
        server:settimeout(nil) -- block
        client = server:accept()
        print("Client connected!")
        client:settimeout(0) -- non-blocking communication?
        -- Actually, for lockstep, blocking read is safer to ensure we wait for Python's command
        client:settimeout(nil) 
    end

    -- Receive Command
    local line, err = client:receive()
    if err then
        print("Client disconnected: " .. err)
        client = nil
    else
        -- Parse Command
        -- Expected format: CMD ARG1 ARG2 ...
        local parts = {}
        for part in string.gmatch(line, "%S+") do
            table.insert(parts, part)
        end
        
        local cmd = parts[1]
        
        if cmd == "READ_BLOCK" then
            -- READ_BLOCK <ADDR_HEX> <SIZE_HEX>
            local addr = tonumber(parts[2], 16)
            local size = tonumber(parts[3], 16)
            local data = memory.read_bytes_as_array(addr, size, "System Bus")
            
            -- Convert to Hex String for easy sending
            local hex_str = ""
            for i=1, #data do
                hex_str = hex_str .. string.format("%02X", data[i])
            end
            client:send(hex_str .. "\n")
            
        elseif cmd == "WRITE_BYTE" then
            -- WRITE_BYTE <ADDR_HEX> <VAL_HEX>
            local addr = tonumber(parts[2], 16)
            local val = tonumber(parts[3], 16)
            memory.write_u8(addr, val, "System Bus")
            client:send("OK\n")
            
        elseif cmd == "FRAME_ADVANCE" then
            -- FRAME_ADVANCE <COUNT>
            local count = tonumber(parts[2]) or 1
            for i=1, count do
                emu.frameadvance()
            end
            client:send("OK\n")
            
        elseif cmd == "SET_INPUT" then
            -- SET_INPUT <BUTTON_MASK_INT>
            local mask = tonumber(parts[2])
            -- Helper to interpret mask
            -- A=1, B=2, Select=4, Start=8, Right=16, Left=32, Up=64, Down=128, R=256, L=512
            local input_table = {}
            if (mask & 1) ~= 0 then input_table["A"] = true end
            if (mask & 2) ~= 0 then input_table["B"] = true end
            if (mask & 4) ~= 0 then input_table["Select"] = true end
            if (mask & 8) ~= 0 then input_table["Start"] = true end
            if (mask & 16) ~= 0 then input_table["Right"] = true end
            if (mask & 32) ~= 0 then input_table["Left"] = true end
            if (mask & 64) ~= 0 then input_table["Up"] = true end
            if (mask & 128) ~= 0 then input_table["Down"] = true end
            if (mask & 256) ~= 0 then input_table["R"] = true end
            if (mask & 512) ~= 0 then input_table["L"] = true end
            
            joypad.set(input_table, 1)
            client:send("OK\n")
            
        elseif cmd == "RESET" then
            client:send("OK\n") -- Soft response before reset
            emu.softreset()
            
        elseif cmd == "SCREENSHOT" then
            client:send("TODO\n")
            
        else
            client:send("ERROR: Unknown Command\n")
        end
    end
    
    -- We do NOT auto-advance frame here. 
    -- The python script controls time via FRAME_ADVANCE.
    -- But we need to keep the UI responsive? 
    -- emu.yield()? No, loop runs inside script thread.
end
