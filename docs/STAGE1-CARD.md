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

Status: **design, nothing ordered.** The card edge's pinout is from two sources
(`docs/hucard_pinout.csv`, by `tools/hucard_bus.py`: the committed wiki text against
the console schematic's CN202, all 38 pins agree) — TEST_PLAN T1c is the physical check.

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

### Dimensions

No committed source had these, so they were taken from a working repro HuCard and
from the datasheet drawing of the one slot you can buy
([partlyhuman/HuCARD-repro](https://github.com/partlyhuman/HuCARD-repro), a fork
of ichigobankai's reproduction cards; geometry only — no layout, no licence
obligation is inherited by reading numbers off a board). These are the values to
**confirm** with a caliper (T1d), not to discover:

| dimension | value | source |
|---|---|---|
| PCB outline | **54.1 × 85.4 mm** | the repro board's `Edge.Cuts` |
| PCB thickness | **1.6 mm** | its fab note: "fabricate at 1.6mm thickness" |
| card total | **≈ 2.4 mm** | its gerber note, plus the **0.75 mm** riser it ships (`prints/HuCard riser.stl`) because a bare 1.6 mm PCB does not grip |
| finger pitch | **1.27 mm** | its `HuCard_Edge` footprint (38 pads, span 46.99 mm) |
| finger width | **0.75 mm** | same |
| finger length | **5.0 mm**; pins 1 and 38 at 5.5, pin 21 at 6.0 | same |
| contact span | **46.99 ± 0.1 mm** (38 × 1.27) | JT Studios slot drawing, "recommended PCB layout" |
| slot opening height | **2.9–2.95 mm** | same drawing |
| insertion depth to the contacts | **≈ 8.6 mm** | same drawing, section A-A |
| finish | **ENIG, gold fingers, bevel on the front face only** | repro README |

Consequences for the carrier:

- **1.6 mm is the right board**, so no thin-board fab option; the grip comes from a
  shim or a printed frame, exactly as the repro does it (2.9–2.95 mm of slot to
  fill, so ~0.75 mm of shim and a little clearance).
- fingers are **0.75 mm wide on 1.27 mm pitch**, i.e. **0.52 mm** between them:
  a 0.25 mm trace fits, but barely. Keep the fan-out short, and never route a
  signal between fingers *inside the contact area* — the slot's contacts press
  there.
- **8.6 mm of insertion depth** is used by the fingers and the slot: the
  translators and the Tang must sit behind that line, which sets where the board's
  parts can go relative to the card edge.
- **No slot is needed.** The card is programmed over the Tang's own USB-C and
  needs only +5 V and ground on two bench leads; the fingers and the board's test
  points are probe-able with it lying on the bench. A bought slot (JT Studios,
  38-pin) would be a *fixture*, not a programmer: useful only if four channels must
  be clipped on something that stays still, or if T4b has to be chased with no
  console in the loop — and even then it needs a jig PCB built around it first.
  The repro-HuCard world needs a slot because it flashes a TSOP; this board never
  writes to the bus side.

### Decision (2026-11-19): the card may be longer than a HuCard

The owner's call: **the card does not have to be HuCard-sized.** Only the part that
goes into the slot has to match a real card; the rest may stick out of the console.

| part of the card | constraint |
|---|---|
| the slot end: fingers, bevel, thickness, the first **8.6 mm** | **exact**, per the table above |
| the width inside the slot opening | **54.1 mm**, the card's own width, or it won't go in |
| length | **free.** It sticks out of the front of the console |
| width outside the console | free in principle; keep 54.1 mm until T1d shows the slot surround |

What to check on the real console before drawing the outline (add to T1d): what the
**power switch's card lock** reaches on a real HuCard (a PC Engine locks the card
while it is on), and where the console's front lip is, so the wider part (if any)
starts after both.

What it changes: **board size no longer limits the FPGA module.** A module bigger
than the Tang Nano 20K fits on a longer card, so the module decision
([RESEARCH-STATUS.md](RESEARCH-STATUS.md) §3) is about pins and price only. The
section below, written for a card-sized board, still holds for a 20K.

### Does the Tang even fit on a card?

The card is **54.1 × 85.4 mm**; the Tang Nano 20K is **54 × 23 mm**
([PLACEMENT_BRIEF.md](PLACEMENT_BRIEF.md)). Its 54 mm side is therefore **0.05 mm
wider than nothing** on a card's width: mounted across the card, its header rows
land exactly on the card's long edges and there is no border left for a shim tab,
a bevel or a probe point.

Rotated so its 54 mm axis runs along the card's **depth**, the budget works:

| | mm |
|---|---|
| fingers + slot insertion (nothing may be fitted here) | 8.6 |
| translator row + 33 Ω resistors, close to the fingers | ~10 |
| the Tang, along the depth axis | 54 |
| **used** | **72.6** of 85.4 |
| left over | 12.8 |

The card's width then holds the 23 mm Tang plus **31 mm** of side area — which is
where the decoder, the test points and the passives go. **Mount it that way.** The
0.75 mm shim or printed frame goes on the **face away from the Tang**, and the board
bevel (front face only) on the side the slot's guide sees.

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

That is **~30–33 pins against 24 safe**, so — and note the one shipping product
that does this job ([Turbo EverDrive Pro](https://krikzz.com/our-products/cartridges/turbo-everdrive-pro.html),
[BUS_OPTIONS.md](BUS_OPTIONS.md) §10) uses a **Cyclone IV with 16 MB PSRAM on a
6-layer board**: the pin count is the reason, not the idea. Memory is not the
problem — 2 MB of Arcade Card RAM plus 256 KB of CD RAM plus a BIOS fits in the
20K's 8 MB SDRAM:

| option | cost |
|---|---|
| **a module with more I/O** (e.g. Tang Primer 20K; its headers must be counted from the datasheet, not assumed) | a different module, so a different carrier footprint — decide **before** the carrier PCB |
| **an external address latch** (3× 74LVC574, latched on /RD falling, read back over 8 pins) | the FPGA loses the address→/RD window and is left ~90 ns (140 ns cycle − 47 ns to /RD) to fetch from SDRAM: tight, and it needs a new timing proof |
| **8 KB banked window only** | works for mapper games, breaks plain linear cards: not acceptable |

### What a BIOS costs in pins — the real reason the module decision cannot wait

The FPGA is a **module**, not a bare chip — a Tang Nano 20K dev board in a socket on
the carrier — so the 34 header I/O are the hard limit and there is no "bigger package"
escape. The full arithmetic, and the architecture it forces, is
[CARRIER-ARCH.md](CARRIER-ARCH.md).

Stage 1a fits 25 pins only because its ROM is **8 KB**: 13 address lines. Now count
what the device must do *first*, before any CD logic:

- a **System Card / Super System Card BIOS is 256 KB**, and the CPU fetches it
  **linearly** across `$000000–$03FFFF` — there is no banking to hide behind, because
  the address the CPU puts out *is* the ROM offset (`huc_ssc` in
  [REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §4 decodes it exactly that
  way);
- 256 KB needs **A0–A17**, i.e. 18 pins, plus 8 data, plus /RD and /WR = **28**, before
  a single select. That is already **four more than the 24 safe pins**, and there is
  no version of this board that boots a BIOS on a 20K without help.

So the flash-cart role was never the thing that forced the module choice; **booting a
BIOS from the SD card forces it**, and that is stage 2's first minute.

The three ways out, honestly priced:

| option | what it costs |
|---|---|
| **a module with more I/O** (Tang Primer 20K, Mega 60K, …) | count the usable pins from its own pinout before committing; a different module means a different carrier footprint |
| **keep the 20K and move the address bus off the FPGA** — the carrier's SRAM is addressed by the console directly, and the FPGA owns only the windows it must interpret | the architecture [CARRIER-ARCH.md](CARRIER-ARCH.md) proposes; 18–19 pins instead of 29, at the price of the FPGA being out of the read path (and a ~35 ns timing budget instead of ~85 ns) |
| **20K + address latches** (3× 74LVC574, latched on /RD falling) | the FPGA loses the address→/RD window and is left ~90 ns to fetch; needs its own timing proof, and it is the only option that keeps the 20K |

**The SD card is free, though.** The Tang Nano 20K's microSD is wired **to the FPGA**
(4-bit SDIO: `sd_sclk`, `sd_cmd`, `sd_dat[0..3]` on I/O 80–85, per PCEHeroTN's own
constraints), so neither the BIOS file nor a disc image costs the carrier a single
pin. It does consume those six FPGA I/O, which is why [STAGE1.md](STAGE1.md) §2 already
lists some of them as "kept".

**Recommendation:** build stage 1a on the 20K as a bench proof, wired by hand on a
carrier prototype; and settle the module question *before* the product carrier is laid
out. The 24-pin stage-1 board is deliberately the smallest thing that answers the only
question that can kill the project.

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
| are the §1 dimensions right? (they come from a repro board and a slot drawing, not a caliper) | T1d: a caliper on a real HuCard, then the fabricated carrier |
| does the bare 1.6 mm board grip well enough, or does it need the 0.75 mm shim | T1d on the first carrier: does it stay seated with a probe attached |
| does the console tolerate a card driving above the window | T4b |
| data-order reversal between PC Engine and TurboGrafx-16 | **answered, and it is not a hardware problem.** The card is the same; the region difference is a **reversal of every data byte's bit order**. The HuConv tool that prepares images for these repro cards emits a TG16 variant by mapping bit 0↔7, 1↔6, 2↔5, 3↔4 (`HuCONV_v1.5/huconv.py` lines 142–152). So it is a mapping in the FPGA — free — or a setting when an image is loaded. No jumper, no CST difference, no second PCB. |
| does the card slot have series resistors that spoil drive levels | the schematic's CN202 area, then T4b's scope trace |
| how much current the slot will give the Tang | measure with the board fitted; the Tang's own USB-C stays the primary supply, the card edge feeds only the bus side |
| does the Tang's own 27 MHz PLL care that there is no bus clock on this connector | it does not (the design is fully asynchronous) — but confirm at bring-up |
