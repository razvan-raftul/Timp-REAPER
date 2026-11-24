-- Timp REAPER
-- Când derulezi (muți cursorul sau sari în piesă), îți spune unde ești: „3 minute și 30 de secunde”.
-- Pornește singur odată cu REAPER, dar tace până îl pornești cu Control Shift Alt T (prins de addonul
-- NVDA „Timp REAPER”). Control Shift Alt I spune oricând unde ești și cât durează piesa.
-- Mesajele le citește addonul NVDA din fișierul de mai jos.

local FISIER = (os.getenv("TEMP") or "C:\\Windows\\Temp") .. "\\reaper_timp.txt"
local FIS_COMANDA = (os.getenv("TEMP") or "C:\\Windows\\Temp") .. "\\reaper_timp_comanda.txt"
local LINISTE = 0.15        -- secunde fără altă săritură până spune locul (la tasta ținută spune când o lași)
local SARITURA = 0.3        -- secunde: cât trebuie să sară cursorul ca să fie derulare, nu redare normală

local activ = false
local ultima_comanda = nil
local ultima_verificare = 0
local poz_veche, timp_vechi, stare_veche = nil, nil, nil
local de_spus = nil          -- momentul la care spune locul, după derulare

local function scrie(mesaj)
  local id = string.format("%.3f", reaper.time_precise())
  local tmp = FISIER .. ".tmp"
  local f = io.open(tmp, "w")
  if not f then return end
  f:write(id .. "\n" .. mesaj)
  f:close()
  os.remove(FISIER)
  os.rename(tmp, FISIER)
end

local function citeste_comanda()
  local f = io.open(FIS_COMANDA, "r")
  if not f then return nil end
  local t = f:read("a")
  f:close()
  return t
end

-- „1 minut”, „2 minute”, „20 de minute”, la fel la ore și secunde
local function cu_unitate(n, unu, multi)
  if n == 1 then return "1 " .. unu end
  local r = n % 100
  if n == 0 or (r >= 1 and r <= 19) then return n .. " " .. multi end
  return n .. " de " .. multi
end

local function in_cuvinte(secunde)
  local t = math.floor(secunde + 0.0001)
  if t < 0 then t = 0 end
  local h, m, s = t // 3600, (t % 3600) // 60, t % 60
  local parti = {}
  if h > 0 then parti[#parti + 1] = cu_unitate(h, "oră", "ore") end
  if m > 0 then parti[#parti + 1] = cu_unitate(m, "minut", "minute") end
  if s > 0 or #parti == 0 then parti[#parti + 1] = cu_unitate(s, "secundă", "secunde") end
  if #parti == 1 then return parti[1] end
  return table.concat(parti, ", ", 1, #parti - 1) .. " și " .. parti[#parti]
end

local function pozitie()
  local stare = reaper.GetPlayState()
  if stare & 1 == 1 or stare & 4 == 4 then return reaper.GetPlayPosition(), stare end
  return reaper.GetCursorPosition(), stare
end

local function bucla()
  local acum = reaper.time_precise()

  if acum - ultima_verificare >= 0.1 then
    ultima_verificare = acum
    local c = citeste_comanda()
    if c and c ~= ultima_comanda then
      ultima_comanda = c
      if c:find("comuta", 1, true) then
        activ = not activ
        de_spus = nil
        scrie(activ and "Timpul la derulare pornit" or "Timpul la derulare oprit")
      elseif c:find("info", 1, true) then
        local p = pozitie()
        scrie("Ești la " .. in_cuvinte(p) .. " din " .. in_cuvinte(reaper.GetProjectLength(0)))
      end
    end
  end

  local poz, stare = pozitie()
  if poz_veche and stare == stare_veche then
    local asteptat = poz_veche
    if stare & 1 == 1 and stare & 2 == 0 then
      asteptat = poz_veche + (acum - timp_vechi) * reaper.Master_GetPlayRate(0)
    end
    if math.abs(poz - asteptat) > (stare & 1 == 1 and SARITURA or 0.0005) then
      de_spus = acum + LINISTE
    end
  end
  -- la pornirea sau oprirea redării locul se schimbă singur: nu se spune
  poz_veche, timp_vechi, stare_veche = poz, acum, stare

  if de_spus and acum >= de_spus then
    de_spus = nil
    if activ then scrie(in_cuvinte(poz)) end
  end
  reaper.defer(bucla)
end

-- Pornire automată: la prima rulare se adaugă în __startup.lua din REAPER
local function porneste_singur()
  local cale_script = ({reaper.get_action_context()})[2]
  local startup = reaper.GetResourcePath() .. "\\Scripts\\__startup.lua"
  local continut = ""
  local f = io.open(startup, "r")
  if f then continut = f:read("a") or "" f:close() end
  if continut:find("Timp REAPER", 1, true) then return end
  local linii = "\n-- Timp REAPER: spune timpul piesei la derulare\n" ..
    "do local id = reaper.AddRemoveReaScript(true, 0, [[" .. cale_script .. "]], true)\n" ..
    "if id and id ~= 0 then reaper.Main_OnCommand(id, 0) end end\n"
  f = io.open(startup, "a")
  if f then f:write(linii) f:close() end
end

-- a doua pornire din lista de acțiuni îl oprește fără întrebări (REAPER 7)
if reaper.set_action_options then reaper.set_action_options(1) end
ultima_comanda = citeste_comanda()    -- ce era dinainte nu contează
porneste_singur()
bucla()
