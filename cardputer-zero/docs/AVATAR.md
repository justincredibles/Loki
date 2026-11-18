# The Loki avatar — XP, levels, achievements, gear

Design locked 2026-11-17 (Justin's direction): a little cartoon
Loki who lives in lokicz. **Every real action in the app earns XP**
— handshakes, wardrives, network scans, all of it. Levels unlock
gear and armor the user equips on their personal Loki, rendered
wearing the loadout on the device and in the web portal.

Build order note: the avatar is the CAPSTONE — it lands after the
functional features it feeds on, so its XP hooks wire into real,
finished actions.

## XP table (per event; session caps stop idle farming)

| Action | XP |
|---|---|
| Capture session completed | +10 |
| Crackable handshake pair caught | +25 each |
| PMKID caught | +10 each |
| Wardrive: unique network logged | +1 each (cap 100/session) |
| Wardrive session with a GPS fix | +10 bonus |
| Network audit completed | +30 |
| Audit: open port found | +2 each |
| Audit: CVE found | +3 each |
| Audit: critical CVE (≥ 9.0) | +10 each |
| Sniff session completed | +10 |
| Sniff: signature hit (drone/ALPR) | +40 each |
| Tracker confirmed following you | +50 |
| Sub-GHz: OOK signal captured | +15 each |
| Sub-GHz: band sweep | +5 |
| NFC: tag read | +15 |
| Mesh: node heard | +2 (cap 20/day) |
| Flight radar check | +2 (cap 10/day) |
| Proximity radar scan | +5 |

## Levels

Cumulative XP: L2 100 · L3 250 · L4 500 · L5 850 · L6 1300 ·
L7 1900 · L8 2700 · L9 3700 · L10 5000 · then +1500 per level.

Titles: 1 Mortal · 2 Trickster · 3 Mischief Maker · 4 Illusionist ·
5 Schemer · 6 Sorcerer · 7 Prince of Lies · 8 God of Mischief ·
9 King of Asgard · 10 All-Father's Problem.

## Achievements (first batch)

- **First Blood** — catch your first handshake
- **Century Club** — 100 hashes total
- **Cracked It** — first WPA-SEC crack lands
- **Cartographer** — 1,000 wardriven networks
- **Eagle Eye** — first surveillance-sniffer hit
- **Bug Hunter** — first CVE found by an audit
- **Exterminator** — first critical CVE
- **The Auditor** — 10 audits completed
- **Sky Watcher** — 100 flight-radar checks
- **Crowded Room** — 50 devices in one proximity scan
- **Ghosted** — a tracker confirmed following you
- **Signal Thief** — first sub-GHz OOK capture
- **You're It** — first NFC tag read
- **Well Connected** — 10 mesh nodes heard

## Gear (unlock → equip; persists on-device)

- **Horns:** Classic (start) · Longhorn (L3) · Crown of Horns (L6)
  · Winged Helm (L9)
- **Armor:** Street Clothes (start) · Leather (L2) · Chainmail (L4)
  · Asgardian Plate (L7) · Royal Gold (L10)
- **Cape:** None (start) · Green Cape (L3) · Royal Cape (L8)
- **Chest gem:** None (start) · Emerald (Bug Hunter) · Sapphire
  (Sky Watcher) · Ruby (Exterminator)
- **Scepter:** L10, or the Exterminator + Century Club combo

## Status: SHIPPED 2026-11-17 (evening)

Engine (`lokicz/avatar.py`), character renderer + home screen
(`ui.draw_loki` / `ui.home_screen`), XP hooks in every LCD
handler and portal job, portal wardrobe — all live and verified
on the device (engine unit checks, framebuffer pixel check,
first live award: +10 XP from a portal sniff). Profile starts
fresh at Level 1 / Mortal.

## Home screen layout (Justin's sketch, 2026-11-17)

The avatar screen IS the home screen, 320×170:

- **Left:** the Loki avatar portrait, wearing the equipped gear.
- **Top middle:** a small Level box (the number).
- **Top right:** the XP bar (with level title + XP counts).
- **Right middle:** funny Loki-like sayings, rotating randomly
  from a list.
- **Bottom:** three soft labels aligned to the keypad —
  **PREV** over key **4**, the **selected menu item** (e.g.
  "Handshake Capture", "Network Audit") over key **6** — press
  6 to launch it — and **NEXT** over key **8**. The carousel
  flattens every app action into one list; the classic chip
  menus remain one keypress away (0 returns home from them).

## Implementation sketch

- `lokicz/avatar.py`: profile at `~/.config/lokicz/avatar.json`
  (device-local, never the repo): xp, level, counters per action,
  achievements unlocked, equipped gear. `award(event, n)` called by
  app + web actions at the same points stats are reported.
- Renderer: PIL layers on the LCD (helm mark is the base; face,
  armor, cape, gem drawn as themed vector shapes); the portal gets
  the same character as a rendered PNG + a wardrobe panel
  (equip unlocked gear) + achievements grid + XP progress bar.
- LCD: a LOKI character screen (portrait, level + title, XP bar,
  newest achievement).
