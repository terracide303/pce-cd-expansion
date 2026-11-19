# Stage 2 reference: what a working CD-ROM² implementation does

Read from the **MiSTer PC Engine core** as vendored in PCEHeroTN `source/mister/`
(`HUC6280/HUC6280.vhd`, `pce_top.vhd`, `cd/cd.vhd`; GPL). This is the "working
original" rung: it says what a **correct emulation** does, which games and the
System Card accept. It is not a measurement of real hardware: where the two might
differ, it says so.

## 1. Bus timing, as the CPU model has it

The model runs on a ~42.95 MHz master clock (23.3 ns per tick). In fast mode
(HSM high, 7.16 MHz) one bus cycle is **6 ticks = 139.7 ns** (`CPU_CLK_CNT` 0..5):

| tick from the address change | what happens | source |
|---|---|---|
| 0 | address changes (start of cycle, `CPU_CE`) | `HUC6280.vhd` lines 96–104 |
| ~2 (≈ 47 ns) | /RD or /WR goes low (`CPU_CER`, count = 1) | lines 107–110, 162–166 |
| 6 (≈ 140 ns) | **read data latched** by the CPU core; /RD and /WR go high | lines 172–176 |

**For stage 1:** the board needs the console to sample read data ≥ 55 ns after
the address changes (simulation, [STAGE1.md](archive/STAGE1.md) §7). The model samples at
~140 ns: **~85 ns of margin.** Test T3 on the scope still confirms it on the real
chip, but it's now expected to pass, not a risk.

Also from the model: **VDC and VCE accesses get one wait state** (the CPU pulls
its own RDY, lines 168–170); slow mode (HSM low) is 24 ticks per cycle.

## 2. Memory map of the CD system

| what | physical | logical (bank) | in the core | on a real console |
|---|---|---|---|---|
| **CD registers** | `$1FF800–$1FF8FF` | `$1800` page of bank `$FF` | `cd.vhd` `REG_SEL`: A20..13 = `$FF`, A12..8 = `11000` | CD interface unit. The CPU has **no chip enable** for this block ("reserved for extension", HuC6280 manual p.12), so our board decodes A20–A8 itself. **Note:** 256 bytes is what the core decodes; the manual reserves `$1FF800–$1FFBFF` (1 KB), and `$1FF8C0–C7` belongs to the Super System Card, not the CD unit (the core lumps both into `cd.vhd`) — see [RESEARCH-STATUS.md](archive/RESEARCH-STATUS.md) §4 |
| **CD RAM**, 64 KB | `$100000–$10FFFF` | banks `$80–$87` | `cd.vhd` `RAM_SEL` covers `$68–$87` as one 256 KB block | CD interface unit (stage 1 already answers here) |
| **Super System Card RAM**, 192 KB | `$0D0000–$0FFFFF` | banks `$68–$7F` | same block | **inside the Super System Card HuCard.** If that card is plugged in, our board must NOT answer here, or two devices drive the bus. **Make it switchable** |
| **Backup RAM**, 2 KB | `$1EE000–$1EE7FF` | bank `$F7` | `pce_top.vhd` `CPU_BRM_SEL_N`: A20..11 = `$F7`&`00` | CD interface unit; locked/unlocked through `$1807` / `$1803` |
| **signature bytes** | `$1FF8C1–C7` | `$18C1–$18C7` | `cd.vhd` returns AA, 55, 00, then region bytes | **answered** ([REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §3): the **Super System Card** answers, being a card — `AA 55 00 FF`, then two region bytes, `C7` = `$C0` or `$03` |

## 3. CD presence

The core feeds the CPU's port K with `not CD_EN & "011" & joypad` (`pce_top.vhd`
line 293): **K7 low = a CD unit is present.** K7 is rear-port pin **b2**. A stage-2
board must hold b2 low, or the System Card won't look for a drive.

## 4. Registers (`cd.vhd` lines 252–340 write, 500–578 read)

| reg | write | read | **read side effect** |
|---|---|---|---|
| `$1800` | select the drive (SCSI SEL), clear DTR/DTD | SCSI status: BSY, REQ, MSG, C/D, I/O | |
| `$1801` | SCSI data out | SCSI data | |
| `$1802` | ACK (bit 7); IRQ enables: DTR (6), DTD (5), SUBCD (4), ADPCM end (3), ADPCM half (2) | same bits back | |
| `$1803` | | IRQ flags: DTR, DTD, SUBCD, ADPCM end, half; CD-DA channel | **locks backup RAM** |
| `$1804` | SCSI reset (bit 1), clears DTR/DTD | reset bit | |
| `$1805/6` | latch CD-DA volume sample | CD-DA level, low/high byte | |
| `$1807` | bit 7 = 1 unlocks backup RAM, 0 locks | subcode byte | **clears the SUBCD flag** |
| `$1808` | ADPCM address low | SCSI data | **auto-ACKs a SCSI data byte** |
| `$1809` | ADPCM address high | | |
| `$180A` | ADPCM data write | ADPCM data | **starts the next ADPCM read** |
| `$180B` | ADPCM DMA enable/run | same | |
| `$180C` | | status: read/write pending, playing, end | |
| `$180D` | ADPCM control (bit 5 = play) | same | |
| `$180E` | ADPCM rate (bits 3..0) | same | |
| `$180F` | fader (bits 3..1) | same | |

A shipping card's reference implementation puts its own registers at
`$1FFFF0–$1FFFFF` and answers `$1FF8C0`, `$1EE000` and `$0D0000` from the cartridge
([REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §2) — i.e. our window list
above is what a working device actually decodes.

**Reads with side effects mean the FPGA must act on each read exactly once per bus
cycle**: detect /RD's falling (or rising) edge once, never the level. Stage 1's
synchroniser plus edge detect is the right pattern; it has to be tested for this
specifically (a bench case: one CPU read of `$1807` clears SUBCD once, not twice).

## 5. Interrupts

IRQ2 (rear-port **b21**, /IRQ2) is asserted while any enabled flag is set:
DTR, DTD, SUBCD, ADPCM end, ADPCM half (`cd.vhd` line 580). On the board it must
be **open-drain** (pull low or float), since the line is shared.

## 6. ADPCM and CD audio

- 64 KB ADPCM RAM; MSM5205 decoder; 16 rates from `$180E` (the core's table:
  ~96.7 kHz down to 1.5 MHz divider clocks, i.e. the usual 2–32 kHz sample rates).
- DMA from the drive into ADPCM RAM (`$180B`).
- CD-DA streamed from the disc image, mixed with ADPCM, back to the console's
  audio lines (rear port a1/b1/c1) or out over HDMI later.

## 7. What this means for the stage-2 pin budget

Decoded externally into chip selects: CD/SSC RAM (`$68–$87`, switchable for
`$68–$7F`), registers (`$1FF800–$1FF8FF`), backup RAM (`$1EE000–$1EE7FF`). The
FPGA then needs A0–A17 (256 KB) + D0–D7 + /RD + /WR + 3 selects + /IRQ2 out +
audio out (1–2) + the companion link to the SD card: about **34–36 pins against
28 safe**. That's the pin crunch the hand-off predicted: plan the stage-2 board
around multiplexing or a bigger board from the start.

## Open questions this raises

| question | how to answer |
|---|---|
| who answers `$18C1–$18C7` on real hardware | **answered** from a shipping card's sources: the Super System Card, with the byte values in [REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §3. Still worth a logic-analyser check against a real SSC for the region pair |
| does a Super System Card claim `$68–$7F` itself | same; then the board's `$68–$7F` select is a jumper or a config bit |
| does the real HuC6280 do dummy reads on `$18xx` (e.g. read-modify-write instructions) that would trigger read side effects twice | the instruction timings in the HuC6280 Software Manual + a logic-analyser capture |
