# Test plan: stage 1 (the RAM responder)

Every open question in [STAGE1-CARD.md](archive/STAGE1-CARD.md) §9 and
[STAGE1.md](archive/STAGE1.md) §5 gets a test here, in the order it's needed. The tests
before T8 need **no working board** and gate the order: T1c, T1d, T3 and T5 only
need the console, a meter, a scope and a real HuCard. T6–T10 need the board.

**Equipment:** multimeter (continuity and DC volts), oscilloscope (2 channels
minimum, 4 better, ≥100 MHz, 10× probes with short ground springs), a PC Engine
with a HuCard game, a real HuCard (to measure the card edge against), the Tang
Nano 20K.

**Two boards, one plan.** T1c, T2, T3, T4b, T5, T8 and T9 run on the **card-edge**
board ([STAGE1-CARD.md](archive/STAGE1-CARD.md)); T1, T1b, T6, T7 and T10 were written for
the **rear-port** board ([STAGE1.md](archive/STAGE1.md)), which is now stage 1b. T1b is a
card test too once the carrier exists: print the footprint 1:1 and lay a real
HuCard on it.

**Record every result** in `docs/test_results/T<n>-<date>.md`: what was
measured, scope screenshots, and pass or fail against the criterion below. A
test with no record didn't happen.

**Safety:** the console's power brick off and unplugged for every continuity
test. The 0.1" port pins are close together, and a card slot's contacts are
spring-loaded and easy to bridge: one slipped probe shorting a supply to a data
line can hurt the console. Use a probe tip, not a clip, and never push a probe
into the card slot's throat — probe the fingers of a scrap card instead.

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

### T1c: The card edge matches the (already verified) rear port (multimeter, console unplugged)

**Answers:** is [`hucard_pinout.csv`](hucard_pinout.csv) right? It has **one**
source — the wiki — while the rear-port pinout has two that agree. The rear port
taps the same bus, is easy to probe, and is already verified: so it is the second
source for the card edge, and this test is the one that makes the card pinout
trustworthy.

**How:** continuity between card-edge fingers and rear-port pins, on the same bus,
console powered off and unplugged. `card` = pin number in `hucard_pinout.csv`,
`port` = pin in `ext_bus_pinout.csv`. Nothing in the console needs opening: the
card slot's fingers are reachable, and so is the rear port.

| card | signal | beep to port | card | signal | beep to port |
|---|---|---|---|---|---|
| 14 | A0 | b12 | 26 | /RD | b7 |
| 15 | D0 | c12 | 34 | /WR | b4 |
| 24 | A20 | b19 | 35 | HSM | b3 |
| 33 | A18 | a4 | 37 | /IRQ2 | b21 |
| 3 | A19 | c19 | 18 | GND | c8 |
| 13 | A1 | c13 | 38 | +5V | *(no port equivalent: check the CPU's +5 V)* |

**Also check:** card 1 (/CD) does **not** beep to any of the above (it is a
separate console input, pulled up); and each row does not beep to its neighbours.

**Pass:** every row beeps where it should and nowhere else. **Fail:** stop, correct
`hucard_pinout.csv`, re-run `tools/hucard_bus.py` — and if the wiki is wrong the
tool's structural checks will not catch it, which is exactly why this test exists.

### T1d: The card's physical dimensions (caliper, a real HuCard, console unplugged)

**Answers:** whether the reference numbers in
[STAGE1-CARD.md](archive/STAGE1-CARD.md) §1 hold on a real card. They come from a working
repro board and the slot's drawing, not from a caliper, and the carrier cannot be
ordered on someone else's geometry.

| dimension | expected (confirm or correct) |
|---|---|
| PCB thickness | 1.6 mm |
| card total thickness | ≈ 2.4 mm (a 0.75 mm shim gets a 1.6 mm board there) |
| finger pitch | 1.27 mm |
| finger width | 0.75 mm |
| finger length | 5.0 mm (pins 1 and 38 at 5.5, pin 21 at 6.0) |
| PCB outline | 54.1 × 85.4 mm |
| insertion depth to the contacts | ≈ 8.6 mm, slot opening 2.9–2.95 mm |

**Also check:** the bevel at the leading edge (present on a real card? at what
angle?), whether the fingers are gold-plated, and where the finger pattern sits
along the edge (centred?).

**Pass:** the values are confirmed or corrected in `docs/test_results/`, and the
first carrier's gerbers match. A wrong thickness either will not enter the slot or
will not make contact.

### T2: The supply is healthy (multimeter + scope, console on, game running)

**Answers:** can the bus-side translators run from the console's supply — `+5A` on
the rear-port board (STAGE1 decision 5), **`+5 V` on card pin 38** on the card-edge
board? On the card the question is also **how much current the slot will give**
before the console sags: the Tang keeps its own USB-C supply, the card edge feeds
only the translators.

| measure | where | pass |
|---|---|---|
| DC voltage | rear port: a2 to c8; card: 38 to 18 | 4.75–5.25 V |
| ripple, AC-coupled, 20 MHz bandwidth limit | a2 / pin 38 | note the value; it's the baseline for T7 |
| current drawn from the slot | card: a series meter, board running | note it; the Tang's own supply stays primary |

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

**Expected** (MiSTer core's CPU model, [STAGE2_REFERENCE.md](STAGE2_REFERENCE.md)
§1): /RD falls ~47 ns after the address changes and read data is latched at /RD
rising, ~140 ns after it. Our board needs ≥ 55 ns. A real chip that samples much
earlier than the model would be the surprise this test exists to catch.

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

### T4b: A card may drive above the card window (scope, card fitted, self-test ROM running)

**Answers:** whether **our** board can answer `$100000` (A20 = 1) on a console with
no CD unit. The practice is settled twice over: the Turbo EverDrive Pro's built-in
CD-ROM² core does it from the card slot, and its MIT-licensed sources show the
mechanism — data is driven whenever /RD is low and a decoded window matches, with
the console's `/CE` not involved
([REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §2). So this checks our
decode, our drive strength and our timing, not the architecture.

**Probe:** CH1 /RD (card 26), CH2 A20 (card 24), CH3 D0 (card 15), CH4 /SEL_RAM
(the decoder's output for `$100000`), during the self-test ROM's read-back.

| measure | pass |
|---|---|
| D0 during a read of `$100000` | shows our data, no double driver (no mid-rail level, no hot chip) |
| D0 during a read of `$1FE000` (VDC, also A20 = 1) | the **console's** data, and our driver off |
| `/SEL_RAM` | low only for `$100000–$101FFF`, never during VDC or other I/O |
| the same with a real HuCard game running | unaffected: the game still boots and plays |

**Pass:** all four. **Fail:** if the console or another part drives the bus there,
the window needs the rear port instead — but the shipping product says the window
is ours to take, so a failure here is our bug, not the architecture's.

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

On the **card-edge** board "unconfigured" means the FPGA's I/Os are high-Z: the
console will see a card that answers nothing and hang at the reset vector — that is
expected and harmless, and it is what this test checks. Do **not** ground `/CD` on
a prototype where the FPGA is unloaded if you want the console usable without it;
fit a jumper.

| check | pass |
|---|---|
| the console boots a HuCard game normally **through** our card (flash-cart role, later) | yes |
| the console with the FPGA unloaded: hangs cleanly at the vector, no hot parts, no bus fight | yes |
| the picture: no new noise, bars or shimmer compared with no card | yes |
| supply ripple vs T2 | not noticeably worse |
| the data translator never drives the bus (CH1 its /OE, run 5 min) | /OE stays high unless a select is active |

### T8: The RAM answers (8 KB at bank $80) — card-edge board

**How:** flash the card bitstream and plug the board in. The FPGA's ROM window
holds the test program (8 KB at `$000000`, its reset vector at `$1FFE`), so the
console boots **our** program and no test card or programmer is needed. The
program shows a banner, maps bank `$80`, writes the patterns (walking ones, walking
zeros, address in data, pseudo-random) to `$100000–$101FFF`, reads them back, and
prints pass or fail per pattern, halting on the first mismatch with the address and
both values.

**On the rear-port board instead:** the same program has to come from a flash
HuCard, which is its own task.

**Pass:** all patterns read back, 10 minutes of repeats, no errors, and the screen
output survives a reset and a power cycle.

### T9: The timing margin, measured

**Probe:** CH1 /RD, CH2 D0 at the **port**, during reads of bank `$80`.

**Pass:** our data is valid at least as early before /RD rises as the HuCard's
was in T3. Record the margin.

### T10: The full 64 KB (after T5 passes)

Re-flash with A13–A15 enabled; re-run T8 across all of banks `$80–$87`.

**Pass:** all 64 KB tests clean. Stage 1 is done.
