# Test plan: stage 1 (the RAM-responder board)

Every open question in [STAGE1.md](STAGE1.md) §5 gets a test here, in the order
it's needed. Tests T1–T5 need **no board** and gate the order. T6–T10 need the
board.

**Equipment:** multimeter (continuity and DC volts), oscilloscope (2 channels
minimum, 4 better, ≥100 MHz, 10× probes with short ground springs), a PC Engine
with a HuCard game, the Tang Nano 20K.

**Record every result** in `docs/test_results/T<n>-<date>.md`: what was
measured, scope screenshots, and pass or fail against the criterion below. A
test with no record didn't happen.

**Safety:** the console's power brick off and unplugged for every continuity
test. The 0.1" port pins are close together: one slipped probe shorting
+5A to a data line can hurt the console. Use a probe tip, not a clip, on the
rear port.

---

## Before the board exists

### T1: The rear port matches the pinout (multimeter, console unplugged)

**Answers:** does [`ext_bus_pinout.csv`](ext_bus_pinout.csv) match the real console?

**How:** continuity between rear-port pins and the **HuCard slot**, which carries
the same bus and is easier to probe than the CPU. Both pinouts are on sheet 5
of the [console schematic](datasheets/PC_Engine_Schematics_r1.2.pdf) (CN202 is
the HuCard slot). Orientation for the rear port: looking into the back, AV/RF
port up, power jack down, card slot away from you. Column left/middle/right =
row a/b/c; top row = pin 1.

| rear port pin | signal | beep to |
|---|---|---|
| c12 | D0 | HuCard slot D0 |
| b8 | D7 | HuCard slot D7 |
| b12 | A0 | HuCard slot A0 |
| a4 | A18 | HuCard slot A18 |
| b19 | A20 | HuCard slot A20 |
| b7 | /RD | HuCard slot /RD |
| b4 | /WR | HuCard slot /WR |
| b22 | /RESET | HuCard slot /RESET |
| c8, c17, c20 | GND | console ground (the shield, or the power jack's ground) |
| a2, c21 | +5A | each other (both +5A) |

**Also check:** each of the above does **not** beep to its neighbours in the row
(catches a misread row or column).

**Pass:** every row beeps where it should and nowhere else. **Fail:** stop,
correct the pinout, re-run `tools/ext_bus.py`.

### T1b: The footprint mates the right way round (paper, console unplugged)

**Answers:** does our 3×23 footprint face the console the right way? A mirrored
connector footprint is the classic way to kill a first board.

**How:** print the board's connector area 1:1 (KiCad: File → Print, scale 1:1,
silkscreen and pads, pad numbers on). Push a pin through pad **a1** (the square
pad) and hold the sheet as the board will sit when plugged in. The pin must
land on the console's **a1** (AudioL), which T1 identified.

**Pass:** a1 on a1, and c23 on c23. **Fail:** mirror the footprint.

### T2: +5A is healthy (multimeter + scope, console on, game running)

**Answers:** can the bus-side translators run from +5A (STAGE1 decision 5)?

| measure | where | pass |
|---|---|---|
| DC voltage | a2 to c8 | 4.75–5.25 V |
| ripple, AC-coupled, 20 MHz bandwidth limit | a2 | note the value; it's the baseline for T7 |

### T3: Bus timing, the real deadline (scope, console on, HuCard game running)

**Answers:** how fast must our board put data on the bus after a read starts?
The HuC6280 manual we have gives only "138 ns bus cycle", no pin timing.

**Probe** at the rear port (or HuCard slot): CH1 /RD (b7), CH2 D0 (c12),
CH3 A20 (b19), CH4 HSM (b3). Trigger on /RD falling edge.

| measure | how | why we need it |
|---|---|---|
| HSM level | DC | high = 7.16 MHz mode, the case we design for |
| bus cycle period | /RD falling edge to falling edge, back-to-back reads | expect ~140 ns |
| /RD low width | CH1 | the window our data must be valid inside |
| address valid → /RD falling | CH3 vs CH1 (use an address line that changes) | how much decode time we get before /RD |
| **data valid → /RD rising**, from the HuCard ROM | CH2 vs CH1 | **the console's own margin; our board must do at least as well** |
| data hold after /RD rising | CH2 vs CH1 | how long we must keep driving |
| /WR low width, data setup → /WR rising, hold after | move CH1 to /WR (b4), trigger on /WR | the write timing our latch must meet |

**Pass:** the numbers are recorded. Then work the **budget**: translator delay
(74HCT688 decode + 74LVC245 in + FPGA + 74LVC8T245 out, roughly 30–40 ns from
datasheets) must fit inside "/RD falling → data needed", with margin.

### T4: Nothing else answers at banks $80–$87 (scope, console on) — confirmation

**Answers:** is bank `$80–$87` really empty with a HuCard in? The
[HuCard pinout](datasheets/pcedev-wiki-HuCard_pinout-2026-11-19.txt) already
says slot pin 24 (/CE) **is** A20, so this only confirms it: the two traces
should be identical.

**Probe:** CH1 A20 (b19), CH2 HuCard slot pin 24 (/CE, called XCE on the
schematic). Trigger on A20 rising.

**Pass:** whenever A20 is high, the HuCard's /CE stays high (the card isn't
selected). **Fail:** the card decodes A20 high too; choose a different bank range.

### T5: The BL616 leaves pins 71–73 alone (Tang Nano only)

**Answers:** can A13–A15 use pins 71, 72, 73 (64 KB instead of 8 KB)?

**How:** flash a tiny image where those pins are inputs with weak pull-downs,
copied to the on-board LEDs. Run FPGA-Companion on the BL616 as usual. Watch the
LEDs and scope the pins for 10 minutes, including a USB plug/unplug and an SD
card load.

**Pass:** the pins never go high. **Fail:** the board stays at 8 KB, or a
respin moves A13–A15.

---

## With the board

### T6: No back-feeding (board fitted, console OFF, Tang ON)

| measure | where | pass |
|---|---|---|
| DC voltage | port a2 (+5A) to c8 | below 0.3 V |
| DC voltage | port c12 (D0), b12 (A0) | below 0.3 V |

### T7: The board does no harm (board fitted, console ON, FPGA unconfigured)

| check | pass |
|---|---|
| the console boots a HuCard game normally | yes |
| the picture: no new noise, bars or shimmer compared with no board | yes |
| +5A ripple vs T2 | not noticeably worse |
| the data translator never drives the bus (CH1 its /OE, run 5 min) | /OE stays high unless A20–A16 = `1 0000` |

### T8: The RAM answers (8 KB at bank $80)

**How:** flash the 8 KB responder image. Boot a test program that writes
patterns to bank `$80`, `$2000–$3FFF` and reads them back (walking ones, address
in data, random), and shows pass or fail on screen. The program loads from a
flash HuCard; writing it is its own task.

**Pass:** all patterns read back, 10 minutes of repeats, no errors.

### T9: The timing margin, measured

**Probe:** CH1 /RD, CH2 D0 at the **port**, during reads of bank `$80`.

**Pass:** our data is valid at least as early before /RD rises as the HuCard's
was in T3. Record the margin.

### T10: The full 64 KB (after T5 passes)

Re-flash with A13–A15 enabled; re-run T8 across all of banks `$80–$87`.

**Pass:** all 64 KB tests clean. Stage 1 is done.
