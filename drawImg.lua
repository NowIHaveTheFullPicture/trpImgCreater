local DISPLAY_W, I = 350, 5
local G = (args and args._G) or _G
local M = G.math
local f = G.gnomeCanvas
if not f then
    f = G.CreateFrame("Frame", "gnomeCanvas", G.UIParent, "BackdropTemplate")
    f:SetBackdrop({ bgFile = "Interface/Buttons/WHITE8X8", edgeFile = "Interface/DialogFrame/UI-DialogBox-Border", edgeSize = 14, insets = { left = I, right = I, top = I, bottom = I } })
    f:SetPoint("CENTER"); f:SetFrameStrata("DIALOG"); f:EnableMouse(true); f:SetMovable(true); f:SetClampedToScreen(true); f
        :RegisterForDrag("LeftButton")
    f:SetScript("OnDragStart", f.StartMoving)
    f:SetScript("OnDragStop", f.StopMovingOrSizing)
    f.pool = {}
    local x = G.CreateFrame("Button", nil, f, "UIPanelCloseButton")
    x:SetPoint("TOPRIGHT", 2, 2); x:SetScript("OnClick", function() f:Hide() end)
end
f:SetBackdropColor(0, 0, 0, 0)
G.gnomeCache = G.gnomeCache or {}

local BV = {}
do
    local CH = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    for i = 1, #CH do BV[CH:byte(i)] = i - 1 end
end

local function draw(w)
    local P     = G.img2Palette
    local W     = G.img2CanvasW
    local H     = G.img2CanvasH
    local PALSZ = G.img2PalSz or 64
    local maxS  = (G.UIParent:GetHeight() - 180) / H
    local S     = M.min(DISPLAY_W / W, maxS)
    local dispW = M.floor(S * W)
    local dispH = M.ceil(S * H)
    f:SetSize(dispW + I * 2, dispH + I * 2)
    local idx = 1
    for i = 1, #w - 4, 5 do
        local b1, b2, b3, b4, b5 = w:byte(i, i + 4)
        local n = ((((BV[b1] * 62 + BV[b2]) * 62 + BV[b3]) * 62 + BV[b4]) * 62 + BV[b5])
        local c    = n % PALSZ;           n = M.floor(n / PALSZ)
        local dx_1 = n % W;               n = M.floor(n / W)
        local y1   = n % H;               local x1 = M.floor(n / H)
        local x2   = x1 + dx_1 + 1
        local pi   = c * 3 + 1
        local tex  = f.pool[idx]
        if not tex then
            tex = f:CreateTexture(nil, "ARTWORK"); f.pool[idx] = tex
        end
        tex:Show(); tex:ClearAllPoints(); tex:SetColorTexture(P[pi], P[pi + 1], P[pi + 2])
        local px = M.floor(x1 * S)
        local py = M.floor(y1 * S)
        tex:SetPoint("BOTTOMLEFT", f, "BOTTOMLEFT", I + px, I + py)
        tex:SetSize(M.max(1, M.ceil(x2 * S) - px), M.max(1, M.ceil((y1 + 1) * S) - py))
        idx = idx + 1
    end
    for i = idx, #f.pool do f.pool[i]:Hide() end
end

if not G.img2Data or not G.img2Palette or not G.img2CanvasW or not G.img2CanvasH then
    f:Hide()
    print("newDraw2: no data -- run the _loader2.lua script first.")
    return
end

local key = (#G.img2Data) .. "|" .. G.img2Data:sub(1, 16) .. G.img2Data:sub(-16)
if G.gnomeCache["img2"] ~= key or not f:IsShown() then
    G.gnomeCache["img2"] = key
    for i = 1, #f.pool do f.pool[i]:Hide() end
    f:Show()
    draw(G.img2Data)
else
    f:Show()
end
