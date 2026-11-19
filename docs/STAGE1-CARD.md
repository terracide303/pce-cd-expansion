# Stage 1 (card edge): the RAM responder that is also the card

**Decision:** this replaces the rear-port board as stage 1 — see
[BUS_OPTIONS.md](BUS_OPTIONS.md) for why. The port board is not abandoned: it
stays as stage 1b and as stage 2's host ([STAGE1.md](STAGE1.md)).

**Goal, unchanged:** prove the hard part — a Tang Nano 20K putting data on the PC
Engine's bus in time — before any CD logic exists. The board makes the console see
RAM at bank `$80` and reads it back.

**What is new:** the board is a HuCard. It boots the console with its own test
program, so the test needs no flash HuCard, no System Card, no console opening and
no second device. It plugs into the slot and reports on screen.

Status: **design, nothing ordered.** The card edge's pinout is from one source
(`docs/hucard_pinout.csv`, parsed by `tools/hucard_bus.py` from the committed
wiki text) — TEST_PLAN T1c is the second source.

---

## 1. The connector

38 fingers, all of them in [`docs/hucard_pinout.csv`](hucard_pinout.csv). What
reaches the FPGA for stage 1:

| needed | on the card edge |
|---|---|
| address | A0–A20, all 21 |
| data | D0–D7 |
| strobes | /RD, /WR |
| reset | /RST (not needed for a responder; used by the test ROM's reset) |
| power | **+5 V (pin 38)** and GND (18) — a real supply, unlike the port's `+5A` |
| mode flag | HSM (35): high = 7.16 MHz, the case we design for |
| CD-detect, audio, IRQ2 | /CD (1) grounded by us, AUDIO IN (2) left open, /IRQ2 (37) left high-Z in stage 1 |

**Three numbers are missing and must be measured on a real HuCard before the
carrier is ordered** — no committed source has them: board **thickness**, finger
**pitch and width**, and **insertion depth** of the fingers. Measured with a
caliper, recorded in `docs/test_results/`; then the fab options (thin board, ENIG
fingers, 45° bevel).

The console is the socket: there is no mating part to source, and no shroud,
cable or bracket to design. But the card also has to carry the Tang, which is
54 × 23 mm and 1.6 mm thick, standing out of the slot. Two consequences:

- the Tang's **USB-C faces away from the console** so it can be programmed while
  fitted; its microSD (underside) will be hidden — accept it for stage 1, move the
  SD socket to the carrier for the flash-cart build;
- insertion is friction only, and a USB-C cable adds leverage. Stage 1 is a bench
  proof: use a short extension cable, and put a support under the board before
  trusting it in a vertical console.

## 2. Pin budget: exactly fits, with one pin borrowed

Stage 1a answers an 8 KB ROM window at `$000000` and an 8 KB RAM window at
`$100000` — the two windows share the 13 address bits, and a select says which.

| signal | pins | direction (FPGA's view) |
|---|---|---|
| A0–A12 | 13 | in |
| D0–D7 | 8 | both |
| /RD, /WR | 2 | in |
| /SEL_ROM, /SEL_RAM | 2 | in |
| **total** | **25** | |

**24 safe pins exist** ([STAGE1.md](STAGE1.md) §2: 12 free + 12 usable), so the
25th pin comes from the four **unverified BL616 lines (71–74)** — the same four
that TEST_PLAN T5 already exists to clear. If T5 fails, the fallback is to spend
one of the twelve "usable" pins (sacrifice an on-board LED) — no respin.

64 KB (T5/T10) adds A13–A15 and needs three more pins; those are also BL616 lines.
That is the same squeeze as the port board, for the same reason: the limit is the
Tang's 34 header I/Os, not the connector ([BUS_OPTIONS.md](BUS_OPTIONS.md) §6).

## 3. The windows, and why the vector lands inside the ROM

- **ROM, 8 KB at `$000000`.** The CPU leaves reset with every MPR cleared to 0, so
  logical `$FFFE–$FFFF` — the reset vector — reads **physical `$001FFE–$001FFF`**,
  inside this window. That is why every HuCard's vector sits at `$1FFE` of its
  image. *(Confirm against the HuC6280 manual in `docs/datasheets/` before the ROM
  is written; it changes the linker script, not the board.)*
- **RAM, 8 KB at `$100000`** = bank `$80`, the CD work-RAM window. The program adds
  `$80` to an MPR to see it, e.g. MPR3 → logical `$6000–$7FFF`.
- The console's own I/O is also above the card window (VDC at `$1FE000`), so the
  test program must map bank `$FF` to a page to talk to the VDC. The card stays out
  of that window: it answers **only** its two selects.

## 4. Decode

Two 74HCT688s on the 5 V side, patterns compared against `A20–A13`:

| select | pattern | window |
|---|---|---|
| `/SEL_ROM` | `0000 0000` | `$000000–$001FFF` |
| `/SEL_RAM` | `1000 0000` | `$100000–$101FFF` |

One part more than the port board needed (it decoded one window). Everything else
carries over: the 74LVC8T245 for data with **DIR = /RD and /OE = the selects**
(STAGE1 decision 4), 74LVC245A input translators for address and strobes, the
Tang on its own USB-C supply, +5 V from the card edge for the bus side.

## 5. The ROM, and what the test does

The test program is 8 KB of HuC6280 code in the FPGA's block RAM (the 20K has ~100 KB
of BSRAM; the ROM is a rounding error, and no external memory is needed for stage 1).

Sequence, per TEST_PLAN T8:

1. wait for the VDC to settle, set up a text screen, print a banner;
2. map bank `$80`, then for each pattern — walking ones, walking zeros, address in
   data, pseudo-random — write 8 KB and read it back, comparing;
3. print pass or fail per pattern on screen, and halt on the first mismatch with
   the failing address and the two values.

The responder RTL is the stage-1 one: `rtl/ram_responder.v` already takes
`bus_a`, `bus_rd_n`, `bus_wr_n`, `bus_sel_n` and `ADDR_BITS`; only the top level
changes — a new `rtl/stage1_card_top.v` muxes the ROM window (read-only, from BRAM)
and the RAM window (the responder) into one data path, and the pin map changes. No
change to the responder's timing, which is the thing under test.

The simulation carries over: `sim/tb_ram_responder.sh` still drives
`ram_responder.v` with a 7.16 MHz asynchronous bus; the ROM mux is added as a
second bench case. The result that matters is unchanged — **data clean 55 ns after
the address changes** ([STAGE1.md](STAGE1.md) §7).

## 6. What this board does not do

- **`$1FF800` / CD registers** — stage 2. Nothing on this board answers there.
- **192 KB Super System Card RAM** (`$0D0000`) — stage 2, and it needs A0–A17 (18
  pins), i.e. the module decision in §7.
- **ADPCM, CD-DA, microSD disc images** — stage 2.
- **Stereo audio and K7** — impossible on this connector; see
  [BUS_OPTIONS.md](BUS_OPTIONS.md) §5.

## 7. The flash-cart role, and the decision it forces early

The same board should present HuCard ROMs from microSD. That needs:

- **A0–A19 (20 pins)** into the FPGA for a plain 1 MB linear card — banking does
  not help, because on a plain HuCard the CPU's address *is* the ROM offset;
- 8 data + /RD + /WR + the selects where the FPGA must **latch mapper writes**
  (e.g. Street Fighter II's mapper at `$1FF0–$1FF3`, which is also above the card
  window), so those registers need a decoder line of their own;
- the ROM itself in the Tang's SDRAM or PSRAM, with the mapper's bank switches
  driving the read address.

That is **~30–33 pins against 24 safe**, so:

| option | cost |
|---|---|
| **a module with more I/O** (e.g. Tang Primer 20K; its headers must be counted from the datasheet, not assumed) | a different module, so a different carrier footprint — decide **before** the carrier PCB |
| **an external address latch** (3× 74LVC574, latched on /RD falling, read back over 8 pins) | the FPGA loses the address→/RD window and is left ~90 ns (140 ns cycle − 47 ns to /RD) to fetch from SDRAM: tight, and it needs a new timing proof |
| **8 KB banked window only** | works for mapper games, breaks plain linear cards: not acceptable |

**Recommendation:** build stage 1a on the 20K as a bench proof, wired by hand on a
carrier prototype; and settle the module question in §7 *before* the product
carrier is laid out. The 24-pin stage-1 board is deliberately the smallest thing
that answers the only question that can kill the project.

## 8. Test plan changes

| test | change |
|---|---|
| T1, T2 | unchanged in intent: continuity with the console unplugged; `+5 V` instead of `+5A` now that the card supplies it |
| **T1c (new)** | card fingers ↔ **rear-port pins** continuity: the port's pinout is already verified against two sources, so it is the second source the card edge lacks. A0 card 14 ↔ port b12, D0 card 15 ↔ port c12, /RD card 26 ↔ port b7, /WR card 34 ↔ port b4, +5 V card 38 ↔ … (no port equivalent: check against the CPU's supply), GND card 18 ↔ port c8 |
| T1b | print the card footprint 1:1 and lay a real HuCard on it: fingers, pitch, bevel, and the `/CD` end must match |
| **T4b (new)** | scope: does the console tolerate our data at `$100000` during a read? CH1 /RD, CH2 A20, CH3 D0, CH4 /SEL_RAM. Expected: nothing else drives; pass = our bytes arrive intact |
| T4 | unchanged: confirm a HuCard's `/CE` follows A20 (still worth knowing) |
| T5 | unchanged: the BL616 lines 71–74 must stay quiet — now they carry `/SEL_RAM` and later A13–A15 |
| T8 | **simplified**: flash the bitstream, boot the console, read the screen. No test card, no programmer |
| T3, T9 | unchanged in intent, and now easier to probe: the card fingers are on the top side of the board |

## 9. Open questions

| question | answered by |
|---|---|
| card thickness, finger pitch/width, insertion depth | caliper on a real HuCard |
| does the console tolerate a card driving above the window | T4b |
| data-order reversal between PC Engine and TurboGrafx-16 | a TG16 with a PCE card, or a continuity check; until then build PCE and put the swap in `fpga/*.cst`, not the copper |
| does the card slot have series resistors that spoil drive levels | the schematic's CN202 area, then T4b's scope trace |
| how much current the slot will give the Tang | measure with the board fitted; the Tang's own USB-C stays the primary supply, the card edge feeds only the bus side |
| does the Tang's own 27 MHz PLL care that there is no bus clock on this connector | it does not (the design is fully asynchronous) — but confirm at bring-up |
