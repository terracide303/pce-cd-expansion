# Carrier architecture: a HuCard carrier with a socket for the Tang Nano 20K

**The constraint, stated plainly:** the FPGA is a **Tang Nano 20K module** — the
30 × 54 mm dev board, not the bare GW2AR-18 — and the carrier is HuCard-shaped with
two header rows for it (the rows are fixed 20.32 mm apart,
[PLACEMENT_BRIEF.md](PLACEMENT_BRIEF.md)). Everything below is arithmetic under that
constraint. It is a proposal, not a design; each claim marked **verify** is unchecked.

## 1. The arithmetic that rules out the obvious design

| | pins |
|---|---|
| header I/O on the module | 34 |
| of those, occupied by the **on-board microSD** (`sd_sclk`, `sd_cmd`, `sd_dat[0..3]`, I/O 80–85) | −6 |
| left for the card bus | **28** |
| of which "free today" / "shared with an LED, the amp or HDMI's EDID" / "unverified BL616" | 12 / 12 / 4 |

A System Card BIOS is **256 KB** and the CPU fetches it **linearly**, so serving it
from the FPGA needs:

```
A0–A17                     18
D0–D7                       8
/RD, /WR                    2
window select               1
                          ──
                           29     and that is a read-only BIOS with nothing else
```

**29 into 28**, with 16 of those 28 being pins we do not confidently own. Even the
generous count fails, and it fails before CD registers, CD RAM, backup RAM, IRQ2 or
audio are considered. So:

> **The card's address bus cannot enter the FPGA.** Not "should not" — there are no
> pins for it. Any architecture that assumes `TG_A[20:0]` reaches the FPGA is dead on
> this module.

## 2. The consequence: memory on the carrier, addressed by the console

The bus is a bus. A 5 V SRAM can hang off it and be read by the CPU *without the FPGA
involved at all* — that is how every simple HuCard works, and it is how the repro
flash cards work with no logic on board.

Proposed block diagram:

```
console card edge ──┬── A0–A15 ──────────────────────────► SRAM A0–A15   (direct, 5 V)
  (38 fingers)      │
                    ├── 3 window bits ──► 74AHCT574 ────► SRAM A16–A18  (which window)
                    │
                    ├── D0–D7 ──┬───────────────────────► SRAM D0–D7   (direct, 5 V)
                    │           └──► 74LVC8T245 ─────────► FPGA          (the FPGA's only bus
                    │                                                    attachment)
                    ├── /RD, /WR ───────────────────────► decode (74HCT688s) + SRAM OE/WE
                    └── /IRQ2 ◄────────────────────────── FPGA

FPGA ── SD (6 pins, on the module) ── loads images into the SRAM at boot,
        holding the console in reset through TG_RST-like control.
```

Wins: the 256 KB BIOS, the 192 KB Super System Card RAM, the 64 KB CD work RAM and
the 2 KB backup RAM all live in **one 512 KB×8 SRAM** (`AS6C4008`-class, 5 V, 55 ns)
addressed by the console. The FPGA is not in the read path, so the timing is
decode + SRAM, not decode + FPGA + buffer.

## 3. What the FPGA then costs

| signal | pins | note |
|---|---|---|
| D0–D7 | 8 | the only bus lines it needs |
| /RD, /WR | 2 | for read side effects and register writes |
| window select in | 2–3 | from the decode: ROM / CD-RAM / registers |
| SRAM write enable, load-mode mux | 2 | it owns the SRAM while loading |
| address counter clock + reset | 2 | see §4 |
| console reset out | 1 | hold the CPU while loading |
| IRQ2 out | 1 | open drain |
| **total** | **18–19** | of 24 safe, **and the SD is already paid for** |

That leaves room for audio (2 pins to an I2S DAC) and a companion link, which the
naive design had no room for at all.

## 4. Loading without an address bus

The FPGA never generates 19 address lines, so it generates none: a **74AHCT4040
(12-bit) + 74AHCT393** counter chain drives the SRAM's address during loading, and
the FPGA supplies only **clock and reset**. Loading is sequential, which is exactly
what a ROM or BIOS image is. (74AHCT, not 74HC: at 5 V a 74HC input wants 3.5 V and
the FPGA's 3.3 V outputs do not reliably reach it.)

For the CD work RAM and ADPCM, access is likewise sequential, which is what a counter
is good at. Random access is the loader's problem only, and it owns the SRAM then.

## 5. What this changes about stage 1

Nothing. Stage 1 remains the 8 KB ROM + 8 KB RAM responder on 25 pins
([STAGE1-CARD.md](STAGE1-CARD.md)) — it is the *other* architecture, and that is its
value: it proves the FPGA can drive the bus at all. If §2 is the product, stage 1 is
the bench proof of the risky half.

What it does change: the carrier's first real revision should be §2, and stage 1 can
be a hand-wired adapter instead of a PCB.

## 6. Verify before believing any of this

| claim | how |
|---|---|
| a 5 V SRAM on the edge reads in time: decode 35 ns + SRAM 55 ns + buffer ≈ 100 ns against the model's ~140 ns latch | T3 on a real console, then a timing budget as in [STAGE1.md](STAGE1.md) §7 (margin shrinks from ~85 ns to ~35 ns — this is the cost of this architecture) |
| the CPU tri-states its data pins while held in reset, so the FPGA can drive the SRAM through the bus | the HuC6280 manual, then a scope |
| the bus tolerates SRAM + FPGA + the decode all attached: capacitance, ringing | T4b, T7 |
| the window latch can be set by pure decode, without an FPGA pin per window | a 74HCT688 pair + a 74AHCT574: straightforward, but the SRAM's A16–A18 must never glitch mid-cycle |
| one 512 KB SRAM is enough | BIOS 256 KB + CD RAM 64 KB + SSC RAM 192 KB + BRAM 2 KB = 514 KB. **It is not enough** — use a 1 MB part (AS6C8008-class) or drop a window |

That last line is the kind of thing worth finding on paper: 514 KB into 512 KB.

## 7. The alternative, if this looks like too much board

Accept a **read-only card**: 256 KB BIOS only, no CD RAM, no IRQ2, no audio —
about 29 pins, so still not the 20K. Or go back to a bigger module or a bare chip,
both of which the constraint in the title rules out.

So §2 is the shape. It also happens to be how the shipping product is built: a
companion memory and a small FPGA that owns only what it must — with the difference
that they could afford a bigger FPGA and used it.

## 8. Open

- 1 MB 5 V SRAM choice (AS6C8008?) — availability and price, and whether 5 V parts
  are still sane to design in for a 2026 build.
- The counter chain vs. a tiny CPLD: a 32-macrocell CPLD costs less board space and
  does the decode, the latch and the counter at once — **a CPLD may replace four
  74-series parts and free the FPGA further**. Worth pricing before the schematic.
- Audio: an I2S DAC on the carrier (2 FPGA pins) into a jack, or an EDFX-style port
  board. Undecided ([RESEARCH-STATUS.md](RESEARCH-STATUS.md) §5).
