# What the PCEHeroTN documents give this project

Reviewed 2026-11-19: every PDF in PCEHeroTN `docs/datasheets/` (branch `dev`, which
has more docs than `main`), **including the pages that are images**, which text
search of the OCR'd `.txt` extracts can't see. Plus `docs/`, `docs/archive/`,
`docs/captures/` and the vendored cores in `source/`.

## What they settle

| question | answer | source |
|---|---|---|
| rear port pinout | all 69 pins (agrees with the PCEdev wiki) | `PC_Engine_Schematics_r1.2.pdf`, sheet 5, CN102 |
| which pins are digital ground, which analog | GND c8/c17/c20, GNDA a21/c2, +5A a2/c21 | same |
| where the CPU's chip enables point | CER = `$1F0000–$1F7FFF` (work RAM, banks F8–FB); CE7 = VDC `$1FE000–$1FE3FF`; CEK = VCE `$1FE400–$1FE7FF`; PSG, timer, I/O and interrupt registers inside the CPU | HuC6280 Hardware Manual p.12 (H8-9, "Chip Enable Allocation"; an image, the OCR is garbled) |
| **where the CD-ROM² registers live** | logical `$1800` in bank `$FF` = physical **`$1FF800–$1FFBFF`**, a block the manual marks **"reserved for extension", with no chip-enable output**. A stage-2 board must decode A20–A10 itself | same page |
| HuCard chip enable | slot pin 24 is the CPU's A20 | PCEdev wiki (committed in `datasheets/`) |
| bus cycle | 138 ns at the top speed (7.16 MHz) | HuC6280 Hardware Manual §1 |
| Tang Nano 20K pins and size | 34 I/Os, banks 3.3 V, 54.04 × 22.55 mm | Sipeed datasheet pp. 5–6 |
| CD logic to borrow for stage 2 | MiSTer TurboGrafx-16 `cd.vhd`, `SCSI.vhd`, FIFOs (GPL) | PCEHeroTN `source/mister/cd/` |

## What they do not contain, after looking at every page

- **No AC timing for the HuC6280's pins**: no address-to-/RD, no data setup or
  hold, no strobe widths. The hardware manual has no electrical chapter at all.
- **No DC levels** (input thresholds, output drive).
- The image-only pages of the Tech Notes (5) and the CD-ROM² Software Manual
  (20) are section title pages, not diagrams.

So read timing comes **only** from the scope: [TEST_PLAN.md](TEST_PLAN.md) T3.
The simulation says this board needs the console to sample read data
≥ 55 ns after the address changes ([STAGE1.md](STAGE1.md) §7).
