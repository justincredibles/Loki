# Supported USB Wi-Fi dongles

**This list ships in the app description at publish time** (Justin's
direction, 2026-11-17) — keep it current when adapter support changes.
Researched 2026-11-17 against the platform that matters: **Debian 13
(trixie), kernel 6.12, arm64** on the Cardputer Zero. A dongle counts
as supported when its driver is in the mainline kernel (plug-and-play)
or lokicz ships a pre-built driver for it.

The baseline adapter lokicz was developed and verified with is a
TP-Link USB dongle on the **Realtek RTL8822BU** (in-kernel `rtw88`):
monitor-mode capture works well; injection is weak, and rtw88 has no
VIF / active-monitor support.

## Tier 1 — plug-and-play (in-kernel drivers)

| Adapter | Chipset | Bands | Notes |
|---|---|---|---|
| **ALFA AWUS036ACM** ⭐ | MediaTek MT7612U (`mt76`) | dual | **Recommended.** Monitor + injection + active monitor; hcxdumptool's reference adapter; ~360–400 mA. Needs Debian `firmware-mediatek`. If it ever crashes under load on a Pi: `options mt76_usb disable_usb_sg=1`. |
| ALFA AWUS036ACHM | MT7610U (`mt76`) | dual | Same feature set, USB 2, smaller. |
| Panda PAU0B | MT7610U (`mt76`) | dual | Same class as the ACHM. |
| ASUS USB-AC51 | MT7610U (`mt76`) | dual | Tiny pocket dongle — best fit for a handheld. |
| ALFA AWUS036NHA | Atheros AR9271 (`ath9k_htc`) | 2.4 GHz | The long-capture reliability king. Firmware is open (`firmware-ath9k-htc`). |
| Panda PAU09 | Ralink RT5572 (`rt2800usb`) | dual | Cheaper dual-band N option. |
| Panda PAU06 | Ralink RT5372 (`rt2800usb`) | 2.4 GHz | Cheapest solid option. |
| TP-Link Archer T3U class | Realtek RTL8822BU (`rtw88`) | dual | The verified baseline: capture ✅, injection weak, no VIF/active monitor. |

## Tier 2 — works only with a pre-built driver (NOT stock Debian 13)

In-kernel support for these Realtek chips landed in kernel 6.14+
(RTL8812AU/8821AU) and 6.16 (RTL8814AU) — **after** Debian 13's 6.12,
so 2026 "plug-and-play" claims for them do not apply to a stock
Cardputer Zero install. The plan for this tier is a pre-built
**lwfinger/rtw88** backport module in a future lokicz image (which
requires freezing the image's kernel version).

| Adapter | Chipset | Notes |
|---|---|---|
| TP-Link Archer T2U Nano / T2U Plus | RTL8811AU | ~$10–13; smallest/cheapest of this tier. |
| ALFA AWUS036ACS | RTL8811AU | RP-SMA external antenna version. |
| TP-Link Archer T4U v1/v2, ALFA AWUS036ACH | RTL8812AU | Strongest of the tier; USB 3, ~720 mA class under TX. |

## Not supported — don't buy for Loki

- **TP-Link TL-WN722N v2/v3** — only v1 is the AR9271; v2/v3 are
  RTL8188EUS (2357:010c) with no reliable injection.
- **RTL8821CU / RTL8811CU Bluetooth-combo sticks** (BrosTrend AC650,
  Cudy WU650, most generic multi-mode sticks) — no usable
  monitor/injection path.
- **RTL8852AU / RTL8832AU Wi-Fi 6 sticks** — poor drivers; in-kernel
  support only at 6.17–6.19+.
- **MT7921AU adapters** — monitor mode regressed on recent kernels.
- **Anything Broadcom** — no monitor mode.
- **Archer T2U v3** (= RTL8811AU, Tier 2) vs **v1/v2** (= MT7610U,
  Tier 1): same model name, different chip — check the version.

## Sources

- morrownr/USB-WiFi chipset + Kali adapter lists (maintained)
- hcxdumptool upstream discussions (ZerBea) — driver requirements
- Kali NetHunter wireless card list
- Full research report: `~/workspace/research_notes/` (2026-11-17)
