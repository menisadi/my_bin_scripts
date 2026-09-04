-- wcag-nvim.lua — WCAG 2.x / APCA contrast audit for one Neovim colorscheme variant.
--
-- Invoked by the `wcag-nvim` wrapper. Direct use:
--   nvim --clean -l wcag-nvim.lua --repo PATH --scheme NAME [--background dark|light]
--
-- Strategy: don't parse the colorscheme, run it. Neovim resolves palettes,
-- variants, blends and links for us; we only read nvim_get_hl() and do arithmetic.
--
-- Exit status: 0 when every content-tier check meets the target ratio, else 1.

local opts = {
  repo = nil,
  scheme = nil,
  background = "dark",
  level = "aa",
  format = "text",
  all = false,
  color = true,
  assume_bg = nil,
  setup = nil,
  layers = "common",
  deps = {},
  width = tonumber(os.getenv("COLUMNS") or "") or 80,
}

local function die(msg)
  io.stderr:write("wcag-nvim: " .. msg .. "\n")
  os.exit(2)
end

do
  local a, i = _G.arg, 1
  while a[i] do
    local k = a[i]
    if k == "--repo" then opts.repo = a[i + 1]; i = i + 2
    elseif k == "--scheme" then opts.scheme = a[i + 1]; i = i + 2
    elseif k == "--background" then opts.background = a[i + 1]; i = i + 2
    elseif k == "--level" then opts.level = a[i + 1]; i = i + 2
    elseif k == "--format" then opts.format = a[i + 1]; i = i + 2
    elseif k == "--assume-bg" then opts.assume_bg = a[i + 1]; i = i + 2
    elseif k == "--setup" then opts.setup = a[i + 1]; i = i + 2
    elseif k == "--layers" then opts.layers = a[i + 1]; i = i + 2
    elseif k == "--dep" then opts.deps[#opts.deps + 1] = a[i + 1]; i = i + 2
    elseif k == "--width" then opts.width = tonumber(a[i + 1]); i = i + 2
    elseif k == "--all" then opts.all = true; i = i + 1
    elseif k == "--no-color" then opts.color = false; i = i + 1
    else die("unknown argument: " .. k) end
  end
end

if not opts.scheme then die("--scheme is required") end

--------------------------------------------------------------------------- color math

local function to_rgb(n)
  return { math.floor(n / 65536) % 256, math.floor(n / 256) % 256, n % 256 }
end

local function hex(rgb)
  return string.format("#%02x%02x%02x", rgb[1], rgb[2], rgb[3])
end

local function parse_hex(s)
  s = (s or ""):gsub("^#", "")
  if not s:match("^%x%x%x%x%x%x$") then return nil end
  return to_rgb(tonumber(s, 16))
end

-- WCAG 2.x relative luminance (sRGB, piecewise linearization).
local function channel(n)
  local c = n / 255
  if c <= 0.04045 then return c / 12.92 end
  return ((c + 0.055) / 1.055) ^ 2.4
end

local function luminance(rgb)
  return 0.2126 * channel(rgb[1]) + 0.7152 * channel(rgb[2]) + 0.0722 * channel(rgb[3])
end

local function contrast(a, b)
  local la, lb = luminance(a), luminance(b)
  if la < lb then la, lb = lb, la end
  return (la + 0.05) / (lb + 0.05)
end

-- APCA 0.1.9 (WCAG 3 draft). Perceptual, polarity-aware; far better behaved
-- than WCAG 2.x for light-text-on-dark, which is most Neovim schemes.
local function apca_y(rgb)
  return 0.2126729 * (rgb[1] / 255) ^ 2.4
       + 0.7151522 * (rgb[2] / 255) ^ 2.4
       + 0.0721750 * (rgb[3] / 255) ^ 2.4
end

local function apca(text, bg)
  local function clamp(y)
    if y < 0.022 then return y + (0.022 - y) ^ 1.414 end
    return y
  end
  local yt, yb = clamp(apca_y(text)), clamp(apca_y(bg))
  if math.abs(yb - yt) < 0.0005 then return 0 end
  local lc
  if yb > yt then -- dark text on light background
    lc = (yb ^ 0.56 - yt ^ 0.57) * 1.14
    lc = lc < 0.1 and 0 or (lc - 0.027) * 100
  else            -- light text on dark background
    lc = (yb ^ 0.65 - yt ^ 0.62) * 1.14
    lc = lc > -0.1 and 0 or (lc + 0.027) * 100
  end
  return math.abs(lc)
end

--------------------------------------------------------------------------- policy

-- Which failures actually matter. A tool that scolds you for a dim `Comment`
-- at the same volume as unreadable `@function` is a tool you stop running.
local THRESHOLD = {
  aa  = { content = 4.5, secondary = 4.5, ui = 3.0, surface = 1.5, other = 4.5 },
  aaa = { content = 7.0, secondary = 4.5, ui = 3.0, surface = 1.5, other = 7.0 },
}
local APCA_TARGET = { content = 60, secondary = 45, ui = 30, surface = 10, other = 60 }
local TIER_LABEL = {
  content   = "Content text (1.4.3)",
  secondary = "Secondary text (advisory)",
  ui        = "Non-text / UI (1.4.11, advisory)",
  surface   = "Tinted surfaces (reported, not scored)",
  other     = "Unclassified groups",
}
local TIER_ORDER = { "content", "secondary", "ui", "surface", "other" }

local CLASS = {}
local function set(tier, list)
  for _, g in ipairs(list) do CLASS[g] = tier end
end

set("content", {
  "Normal", "NormalNC", "Identifier", "Statement", "Constant", "Type", "PreProc",
  "Special", "String", "Character", "Number", "Boolean", "Float", "Function",
  "Keyword", "Conditional", "Repeat", "Label", "Operator", "Exception", "Include",
  "Define", "Macro", "PreCondit", "StorageClass", "Structure", "Typedef", "Tag",
  "Delimiter", "SpecialChar", "SpecialComment", "Debug", "Underlined", "Todo",
  "Title", "Directory", "Question", "MoreMsg", "ModeMsg", "ErrorMsg", "WarningMsg",
  "Error", "CursorLineNr", "Folded", "Search", "IncSearch", "CurSearch", "Substitute",
  "Pmenu", "PmenuSel", "PmenuKind", "PmenuKindSel", "PmenuExtra", "PmenuExtraSel",
  "StatusLine", "StatusLineNC", "TabLine", "TabLineSel", "WinBar", "WinBarNC",
  "NormalFloat", "MsgArea", "QuickFixLine", "Visual", "VisualNOS", "DiffAdd",
  "DiffChange", "DiffDelete", "DiffText", "SpellBad", "SpellCap", "SpellRare",
  "SpellLocal", "MatchParen", "FloatTitle", "FloatFooter",
})
set("secondary", {
  "Comment", "LineNr", "LineNrAbove", "LineNrBelow", "SignColumn", "FoldColumn",
  "MsgSeparator", "LspInlayHint", "TabLineFill",
})
set("ui", {
  "WinSeparator", "VertSplit", "ColorColumn", "CursorColumn", "CursorLine", "Cursor",
  "lCursor", "CursorIM", "TermCursor", "FloatBorder", "PmenuSbar", "PmenuThumb",
  "WildMenu", "StatusLineTerm", "StatusLineTermNC",
})
set("decoration", {
  "NonText", "Whitespace", "EndOfBuffer", "Conceal", "SpecialKey", "Ignore",
})

local function classify(name)
  if CLASS[name] then return CLASS[name] end
  if name:match("^@comment") then return "secondary" end
  if name:match("^@conceal") or name:match("^@none") then return "decoration" end
  if name:match("^@") then return "content" end -- treesitter captures are text
  if name:match("^DiagnosticUnderline") or name:match("^DiagnosticSign")
    or name:match("^DiagnosticVirtualLines") then return "ui" end
  if name:match("^DiagnosticVirtualText") or name:match("^DiagnosticFloating")
    or name:match("^Diagnostic") then return "content" end
  if name:match("^LspInlayHint") then return "secondary" end
  if name:match("^Lsp") then return "ui" end
  return "other"
end

-- Text sits on stacked backgrounds. A comment that passes over `Normal` can be
-- invisible over `CursorLine`; this list is what makes the audit worth running.
-- `common` layers are checked by default; the rest need --layers all. Failures
-- over a diff hunk or an active search are real but a different conversation.
local LAYER_GROUPS = {
  { "Normal", true }, { "CursorLine", true }, { "Visual", true },
  { "Pmenu", true }, { "NormalFloat", true }, { "StatusLine", true },
  { "Search", false }, { "IncSearch", false }, { "CurSearch", false },
  { "PmenuSel", false }, { "ColorColumn", false }, { "QuickFixLine", false },
  { "Folded", false }, { "DiffAdd", false }, { "DiffChange", false },
  { "DiffDelete", false }, { "DiffText", false }, { "TabLineSel", false },
  { "MatchParen", false },
}

-- WCAG 1.4.11 style checks: boundaries and indicators, compared bg-to-bg.
local UI_CHECKS = {
  { "CursorLine", "bg", "Normal", "bg", "surface" },
  { "CursorColumn", "bg", "Normal", "bg", "surface" },
  { "Visual", "bg", "Normal", "bg", "surface" },
  { "ColorColumn", "bg", "Normal", "bg", "surface" },
  { "MatchParen", "bg", "Normal", "bg", "surface" },
  { "Cursor", "bg", "Normal", "bg" },
  { "Pmenu", "bg", "Normal", "bg", "surface" },
  { "PmenuSel", "bg", "Pmenu", "bg", "surface" },
  { "PmenuThumb", "bg", "PmenuSbar", "bg" },
  { "NormalFloat", "bg", "Normal", "bg", "surface" },
  { "FloatBorder", "fg", "NormalFloat", "bg" },
  { "WinSeparator", "fg", "Normal", "bg" },
  { "VertSplit", "fg", "Normal", "bg" },
  { "StatusLine", "bg", "Normal", "bg", "surface" },
  { "TabLineSel", "bg", "TabLineFill", "bg", "surface" },
  { "DiffAdd", "bg", "Normal", "bg", "surface" },
  { "DiffDelete", "bg", "Normal", "bg", "surface" },
}

--------------------------------------------------------------------------- load

-- Dependencies first, then the scheme itself, so its own files take priority.
for _, dep in ipairs(opts.deps) do vim.opt.runtimepath:prepend(dep) end
if opts.repo then vim.opt.runtimepath:prepend(opts.repo) end
vim.o.termguicolors = true
vim.o.background = opts.background
if opts.setup then
  local ok, err = pcall(vim.cmd, "lua " .. opts.setup)
  if not ok then die("--setup failed: " .. tostring(err)) end
end
do
  local ok, err = pcall(vim.cmd.colorscheme, opts.scheme)
  if not ok then die("could not load colorscheme '" .. opts.scheme .. "': " .. tostring(err)) end
end

-- The bulk form of nvim_get_hl() ignores `link = false` and hands back
-- `{ link = "Other" }` entries, so use it only to enumerate names and ask for
-- each group individually to get attributes with links actually resolved.
local group_names = {}
for name in pairs(vim.api.nvim_get_hl(0, {})) do
  group_names[#group_names + 1] = name
end
table.sort(group_names) -- stable output across runs

local hl_cache = {}
local function resolve(name)
  local cached = hl_cache[name]
  if cached ~= nil then return cached or nil end
  local ok, h = pcall(vim.api.nvim_get_hl, 0, { name = name, link = false })
  h = (ok and h) or false
  hl_cache[name] = h
  return h or nil
end

local notes = {}
local normal = resolve("Normal") or {}
local base_bg = opts.assume_bg and parse_hex(opts.assume_bg)
  or (normal.bg and to_rgb(normal.bg))

-- What was requested is not evidence of what loaded. Schemes that ship one
-- file per flavour (rose-pine-dawn, dayfox, vimbones) ignore the requested
-- `background` and set the option themselves, so ask the result, not the
-- request. A real background is classified by the WCAG luminance flip point,
-- where contrast against white equals contrast against black; the post-load
-- option is the only signal left for a transparent scheme.
local rendered_bg = base_bg and (luminance(base_bg) > 0.179 and "light" or "dark")
  or vim.o.background

if not base_bg then
  base_bg = rendered_bg == "light" and { 255, 255, 255 } or { 0, 0, 0 }
  notes[#notes + 1] = ("Normal has no background (transparent scheme); assuming %s. Override with --assume-bg.")
    :format(hex(base_bg))
end
local base_fg = normal.fg and to_rgb(normal.fg)
  or (rendered_bg == "light" and { 0, 0, 0 } or { 255, 255, 255 })

-- Effective fg/bg for a group, honouring `reverse` and inheriting from Normal.
local function effective(name)
  local h = resolve(name)
  if not h then return nil end
  local fg = h.fg and to_rgb(h.fg) or nil
  local bg = h.bg and to_rgb(h.bg) or nil
  if h.reverse then fg, bg = bg or base_bg, fg or base_fg end
  return { fg = fg, bg = bg, hl = h }
end

--------------------------------------------------------------------------- checks

-- Several groups often share one background (Visual and CurSearch, say).
-- Deduping by colour is what keeps every finding from being reported twice.
local layers, seen_bg = {}, {}
for _, spec in ipairs(LAYER_GROUPS) do
  local name, common = spec[1], spec[2]
  if common or opts.layers == "all" then
    local e = effective(name)
    local bg = name == "Normal" and base_bg or (e and e.bg)
    if bg and not seen_bg[hex(bg)] then
      seen_bg[hex(bg)] = true
      layers[#layers + 1] = { name = name, bg = bg }
    end
  end
end

local checks = {}
local counted, cterm_only, hidden = {}, 0, 0

local function record(tier, fg, bg, layer, group, override)
  local t = override and override.wcag or THRESHOLD[opts.level][tier]
  local target_lc = override and override.apca or APCA_TARGET[tier]
  local key = table.concat({ tier, hex(fg), hex(bg), layer, tostring(t) }, "|")
  local c = counted[key]
  if c then
    c.groups[#c.groups + 1] = group
    return
  end
  c = {
    tier = tier, fg = fg, bg = bg, layer = layer, groups = { group },
    ratio = contrast(fg, bg), lc = apca(fg, bg), target = t,
  }
  c.pass = c.ratio >= t
  -- Normalized APCA shortfall. Continuous, unlike a pass/fail rate, so
  -- nudging a colour from Lc 20 to Lc 50 actually moves the score.
  c.deficit = math.max(0, math.min(1, (target_lc - c.lc) / target_lc))
  counted[key] = c
  checks[#checks + 1] = c
end

for _, name in ipairs(group_names) do
  local tier = classify(name)
  if tier ~= "decoration" then
    local e = effective(name)
    if e then
      if not e.fg and not e.bg and (e.hl.ctermfg or e.hl.ctermbg) then
        cterm_only = cterm_only + 1
      elseif e.fg and e.bg and hex(e.fg) == hex(e.bg) then
        -- fg identical to bg is deliberate invisibility (concealed delimiters,
        -- separator glyphs), not a contrast failure.
        hidden = hidden + 1
      elseif e.fg and e.bg then
        -- Self-contained: the group paints its own background.
        record(tier, e.fg, e.bg, "own", name)
      elseif e.fg and tier == "ui" then
        -- A separator or border glyph sits on the buffer background; the
        -- explicit UI_CHECKS below cover the cases where it sits elsewhere.
        record(tier, e.fg, base_bg, "Normal", name)
      elseif e.fg then
        -- Floating text: check it against every background it can land on.
        for _, layer in ipairs(layers) do
          record(tier, e.fg, layer.bg, layer.name, name)
        end
      end
    end
  end
end

for _, u in ipairs(UI_CHECKS) do
  local a, b = effective(u[1]), effective(u[3])
  local ca = a and (u[2] == "fg" and a.fg or a.bg)
  local cb = b and (u[4] == "fg" and b.fg or b.bg)
  if u[3] == "Normal" and u[4] == "bg" then cb = base_bg end
  if ca and cb and hex(ca) ~= hex(cb) then
    record(u[5] == "surface" and "surface" or "ui", ca, cb, u[3], u[1] .. " vs " .. u[3])
  end
end

table.sort(checks, function(x, y) return x.ratio < y.ratio end)

--------------------------------------------------------------------------- report

local stats = {}
for _, t in ipairs(TIER_ORDER) do
  stats[t] = { total = 0, fail = 0, base_total = 0, base_fail = 0 }
end
for _, c in ipairs(checks) do
  local s = stats[c.tier]
  s.total = s.total + 1
  if not c.pass then s.fail = s.fail + 1 end
  -- Failing on the buffer background is the headline; failing only over a
  -- popup or a selection is a softer finding and shouldn't dilute it.
  if c.layer == "Normal" or c.layer == "own" then
    s.base_total = s.base_total + 1
    if not c.pass then s.base_fail = s.base_fail + 1 end
  end
end

-- Surfaces are deliberately excluded from SCORE_WEIGHT: APCA clamps
-- low-contrast background pairs to Lc 0, so scoring them would just add a
-- constant penalty to every scheme rather than telling them apart.
-- Headline score. Aggregating per tier with fixed weights keeps it independent
-- of how many groups a scheme happens to define; the quadratic mean makes one
-- severe failure cost more than several marginal ones.
local SCORE_WEIGHT = { { "content", 0.60 }, { "ui", 0.25 }, { "secondary", 0.15 } }
local BUFFER_SHARE = 0.75

local function quadmean(list)
  if #list == 0 then return nil end
  local sum = 0
  for _, d in ipairs(list) do sum = sum + d * d end
  return math.sqrt(sum / #list)
end

local buckets = {}
for _, w in ipairs(SCORE_WEIGHT) do buckets[w[1]] = { buffer = {}, overlay = {} } end
for _, c in ipairs(checks) do
  local b = buckets[c.tier]
  if b then
    local list = (c.layer == "Normal" or c.layer == "own") and b.buffer or b.overlay
    list[#list + 1] = c.deficit
  end
end

local components, weighted, weight_used = {}, 0, 0
for _, w in ipairs(SCORE_WEIGHT) do
  local tier, weight = w[1], w[2]
  local buf, ov = quadmean(buckets[tier].buffer), quadmean(buckets[tier].overlay)
  local d
  if buf and ov then
    d = BUFFER_SHARE * buf + (1 - BUFFER_SHARE) * ov
  else
    d = buf or ov
  end
  if d then
    components[tier] = d
    weighted = weighted + weight * d
    weight_used = weight_used + weight
  end
end

-- Renormalize so a scheme that defines no UI groups isn't silently credited.
local score = weight_used > 0 and (100 * (1 - weighted / weight_used)) or nil

-- Bands are relative to real colorschemes, not to an absolute accessibility
-- bar: calibrated over 24 variants of kanagawa, tokyonight and the zenbones
-- family, which spanned 63-86. A letter grade would imply a standard that
-- neither WCAG nor APCA actually defines for terminal text.
local function band(value)
  if value >= 82 then return "strong" end
  if value >= 72 then return "good" end
  if value >= 62 then return "typical" end
  if value >= 52 then return "weak" end
  return "poor"
end

local failed = stats.content.fail > 0

if opts.format == "json" then
  local out = { scheme = opts.scheme, background = rendered_bg,
    requested_bg = opts.background, level = opts.level,
    normal = { fg = hex(base_fg), bg = hex(base_bg) }, notes = notes, stats = stats, checks = {} }
  if score then
    out.score = { value = math.floor(score + 0.5), band = band(score), deficit = {} }
    for tier, d in pairs(components) do
      out.score.deficit[tier] = tonumber(("%.3f"):format(d))
    end
  end
  for _, c in ipairs(checks) do
    if opts.all or not c.pass then
      out.checks[#out.checks + 1] = {
        tier = c.tier, fg = hex(c.fg), bg = hex(c.bg), layer = c.layer,
        ratio = tonumber(string.format("%.2f", c.ratio)),
        on_buffer_bg = c.layer == "Normal" or c.layer == "own",
        apca = math.floor(c.lc + 0.5), target = c.target, pass = c.pass, groups = c.groups,
      }
    end
  end
  io.write(vim.json.encode(out), "\n")
  os.exit(failed and 1 or 0)
end

local function paint(rgb, s)
  if not opts.color then return s end
  return string.format("\27[38;2;%d;%d;%dm%s\27[0m", rgb[1], rgb[2], rgb[3], s)
end

local function swatch(fg, bg)
  if not opts.color then return "" end
  return string.format("\27[38;2;%d;%d;%dm\27[48;2;%d;%d;%dm Ag \27[0m",
    fg[1], fg[2], fg[3], bg[1], bg[2], bg[3])
end

local function bold(s) return opts.color and ("\27[1m" .. s .. "\27[0m") or s end
local function dim(s) return opts.color and ("\27[2m" .. s .. "\27[0m") or s end

local bg_label = "background=" .. rendered_bg
if rendered_bg ~= opts.background then
  bg_label = bg_label .. (" (requested %s)"):format(opts.background)
end
io.write(("\n%s  %s  %s  %s\n"):format(
  bold(opts.scheme), dim(bg_label), dim(opts.level:upper()),
  dim("layers=" .. opts.layers)))
io.write(("  Normal  %s  %s on %s  %.2f:1  Lc %d\n\n"):format(
  swatch(base_fg, base_bg), paint(base_fg, hex(base_fg)), hex(base_bg),
  contrast(base_fg, base_bg), math.floor(apca(base_fg, base_bg) + 0.5)))

for _, note in ipairs(notes) do
  io.write("  ! " .. note .. "\n")
end
if #notes > 0 then io.write("\n") end

for _, tier in ipairs(TIER_ORDER) do
  local s = stats[tier]
  if s.total > 0 and (s.fail > 0 or opts.all) and (tier ~= "other" or opts.all) then
    local head = ("── %s "):format(TIER_LABEL[tier])
    local tail = ("%d of %d below %.1f:1"):format(s.fail, s.total, THRESHOLD[opts.level][tier])
    local pad = math.max(1, opts.width - #head - #tail - 2)
    io.write(("%s%s %s\n"):format(head, string.rep("─", pad), dim(tail)))

    local shown = 0
    for _, c in ipairs(checks) do
      if c.tier == tier and (opts.all or not c.pass) then
        shown = shown + 1
        if shown > 12 and not opts.all then
          io.write(dim(("     … %d more\n"):format(s.fail - 12)))
          break
        end
        local names = c.groups[1]
        if #c.groups > 1 then names = names .. dim((" +%d"):format(#c.groups - 1)) end
        local lc_flag = c.lc < APCA_TARGET[tier] and "" or dim("  (APCA ok)")
        io.write(("  %s %s %6.2f:1  Lc %-3d  %s on %s %s  %s%s\n"):format(
          c.pass and dim("·") or "✗", swatch(c.fg, c.bg), c.ratio,
          math.floor(c.lc + 0.5), paint(c.fg, hex(c.fg)), hex(c.bg),
          dim(("%-11s"):format(c.layer)), names, lc_flag))
      end
    end
    io.write("\n")
  end
end

local function pct(total, fail)
  if total == 0 then return "n/a" end
  return ("%d%%"):format(math.floor((total - fail) / total * 100 + 0.5))
end

local function rate(s)
  return ("%s%s"):format(pct(s.base_total, s.base_fail),
    s.total > s.base_total and dim(("/%s"):format(pct(s.total, s.fail))) or "")
end

if score then
  io.write(("  %s  %s  %s\n"):format(bold("Score"), bold(("%.0f (%s)"):format(score, band(score))),
    dim(("APCA deficit  content %.2f · ui %.2f · secondary %.2f"):format(
      components.content or 0, components.ui or 0, components.secondary or 0))))
end
io.write(("  %s     content %s  ·  secondary %s  ·  ui %s"):format(
  dim("AA"), rate(stats.content), rate(stats.secondary), rate(stats.ui)))
if hidden > 0 then io.write(dim(("  ·  %d hidden (fg=bg)"):format(hidden))) end
if cterm_only > 0 then io.write(dim(("  ·  %d cterm-only"):format(cterm_only))) end
if not opts.all and stats.other.fail > 0 then
  io.write(dim(("  ·  %d unclassified (--all)"):format(stats.other.fail)))
end
io.write("\n\n")

os.exit(failed and 1 or 0)
