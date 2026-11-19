# How far the research is, and what is missing

Written 2026-11-19, after the card-slot decision, the repro-HuCard geometry and the
EverDrive PRO sources. It is an inventory, not a plan: what is settled, what is
assumed, and what is simply absent.

**Verdict in one line: stage 1 is designed and can be built; stage 2 has a memory
map and a register list, and almost nothing below them; stage 3 is a paragraph.**

| area | state | what "done" would mean |
|---|---|---|
| Bus choice (card vs port) | **settled** — [BUS_OPTIONS.md](BUS_OPTIONS.md), validated by a shipping product and its MIT sources | — |
| Card-edge pinout | **settled on paper**, 1 source + T1c as the second | T1c on a console |
| Card mechanics/geometry | **settled on paper** from a repro board + slot drawing | T1d with a caliper |
| Stage 1 board (decode, buffers, pin map) | **designed, not built** ([STAGE1-CARD.md](STAGE1-CARD.md)) | schematic + PCB + a booting test ROM |
| Stage 1 timing | **modelled**, ~85 ns margin | T3 scope, T4b, T8 on hardware |
| Stage 2 memory map + registers | **specified from the MiSTer core** ([STAGE2_REFERENCE.md](STAGE2_REFERENCE.md)) | verified against a real BIOS |
| Stage 2 behaviour below the registers | **absent** — §4 | a BIOS-level behaviour spec |
| Stage 2 audio | **options known, no decision** — §5 | a chosen chip and a chosen output path |
| Storage / how images get in | **absent, and mechanical** — §5 | a socket plan and an image format |
| Arcade Card, save states, cheats | **absent** | spec + tests |
| Flash-cart role | **studied, blocked on the module choice** | a module decision and a loader |
| Phase 3 (HDMI, shadow VDC/VCE/PSG, SuperGrafx) | **one paragraph of leads** ([EARLIER-NOTES](EARLIER-NOTES-2026-11-04.md)) | nothing yet |
| Measurements on real hardware | **zero** | `docs/test_results/` with T1c, T1d, T3 in it |

## 1. Settled, with the source that settles it

- **The card slot is the right host**, and it is not speculative: a product ships
  this architecture and its sources are MIT ([BUS_OPTIONS.md](BUS_OPTIONS.md) §10,
  [REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md)).
- **A cartridge may drive windows above `A20`**: `bus_oe = cpu.oe & (own windows)`,
  no `/CE` involved. The windows a shipping cart answers are listed in
  [REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §2.
- **The CD system's address map**: registers `$1FF800`, work RAM `$100000–$10FFFF`,
  backup RAM `$1EE000–$1EE7FF`, Super System Card RAM `$0D0000–$0FFFFF`
  ([STAGE2_REFERENCE.md](STAGE2_REFERENCE.md) §2), each independently confirmed in
  the EverDrive sources.
- **The `$18C0–$18C7` signature bytes**, exact values, and the fact that the **card**
  answers them ([REFERENCE-EVERDRIVE-PRO.md](REFERENCE-EVERDRIVE-PRO.md) §3).
- **The register set and its read side effects** ([STAGE2_REFERENCE.md](STAGE2_REFERENCE.md) §4).
- **Region difference = one bit reversal per byte**, in the FPGA, no hardware
  change (two independent sources: HuConv and `top.sv`).
- **Card geometry**: 54.1 × 85.4 mm, 1.6 mm board, 1.27 mm pitch, 0.75 mm fingers,
  8.6 mm insertion, ~2.4 mm total needs a 0.75 mm shim.
- **Stage 1 timing**: data clean 55 ns after the address changes; the CPU model
  latches at ~140 ns.
- **The mappers exist in MIT source**, including Street Fighter II's.

## 2. Assumed, each with the test that would kill it

| assumption | killed or confirmed by |
|---|---|
| the card edge is wired as the wiki says | T1c |
| the real card matches the repro's dimensions | T1d |
| our board drives `$100000` cleanly | T4b |
| the console samples reads near the end of the cycle | T3 |
| BL616 lines 71–74 stay quiet | T5 |
| the slot gives enough current | T2 |
| an 8 KB ROM + 8 KB RAM fits 25 pins | the first build (design says yes) |
| the CPU leaves reset with all MPRs at 0, so the vector is at `$001FFE` | the HuC6280 manual, **not yet checked** — it decides our linker script |

## 3. Missing: what blocks ordering the carrier

1. **The FPGA module is undecided, and it is decided by the BIOS, not the flash cart.**
   Size budget (owner's decision 2026-11-19, [STAGE1-CARD.md](STAGE1-CARD.md) §1):
   the card may stick out of the console by 9 mm, outline at most 54.1 × 94.4 mm,
   so a module must fit **~54 × 75 mm** — or the FPGA goes directly on the card.
   A 256 KB BIOS is fetched linearly, so it needs A0–A17: 18 + 8 data + 2 strobes =
   **28 pins against 24 safe** — and 22–28 in practice, since the module's SD takes six
   header I/O. The FPGA is a fixed dev-board module (no bare-chip option), so the way
   out is to **keep the address bus off the FPGA**: the carrier's SRAM is addressed by
   the console, and the FPGA owns only the windows it must interpret — 18–19 pins
   ([CARRIER-ARCH.md](CARRIER-ARCH.md)). **This decides the carrier's footprint**, so
   it comes before any PCB.
2. **T1c, T1d, T3 and T5 have not been run**, and they need only a console, a meter,
   a scope and a real HuCard. They do not block the design; they block confidence.
3. **Does a working console with a HuCard exist on the bench?** Everything above
   assumes one. It is not written down anywhere in the repo.

## 4. Missing: stage 2 behaviour, the largest gap

The register map is a *shape*, not a *specification*. What nobody has written down:

- **What the System Card BIOS actually does at boot**: which registers it polls, in
  what order, with what delays, whether it reads `$18C0–$18C7`, whether it uses K7,
  what it does when a disc is absent. This is the real specification and we have
  never read one — only an emulator's implementation of it.
- **The SCSI command set the BIOS speaks** (`READ(10)`, `MODE SENSE`, seek, stop,
  the status bytes and the timing each expects). `cd.vhd`'s registers imply it; the
  sequence is undocumented here.
- **Seek timing.** The shipping product changed its "CD seek time calculations"
  twice: this is empirical, and we have no numbers at all.
- **Sector format and the image format**: 2352 vs 2048, subchannel/Q, CUE parsing
  (their changelog: cue parser buffer too small, CDDA sync bugs).
- **ADPCM specifics**: MSM5205 clocking and the 16 rates, whose sane value we now
  know only because a changelog said "32256 Hz → 32118 Hz"; DMA between the drive
  and ADPCM RAM is undescribed.
- **IRQ2 electrical behaviour**: open-drain, shared, and nothing recorded about the
  console's pull-up or who else drives it.
- **A contradiction in our own docs to resolve**: [STAGE2_REFERENCE.md](STAGE2_REFERENCE.md)
  says the register block is `$1FF800–$1FF8FF` (256 bytes) while
  [SOURCES_REVIEW.md](SOURCES_REVIEW.md), quoting the HuC6280 manual, says
  `$1FF800–$1FFBFF` (1 KB, "reserved for extension"). The core decodes 256 bytes;
  a board decoding the full 1 KB loses nothing. On `$1FF8C0–C7`: the MiSTer core
  answers it from `cd.vhd`, but that core emulates the CD unit *and* the Super System
  Card in one block, so it is not evidence that a real CD unit answers there. The
  EverDrive puts it in the card (`huc_ssc.sv`). **Most likely only the card answers**;
  a logic analyser on a real CD unit without an SSC settles it.
- **Arcade Card**: "supported" by the shipping product, 2 MB of RAM, and *nothing*
  in our docs — not even its registers.
- **Save states and backup-RAM persistence**: the lock/unlock semantics are in
  §4 of STAGE2, the file format and the storage side are absent.

## 5. Missing: decisions, not knowledge

- **Audio**: we now know a cart can carry its own I2S DAC and that audio never has
  to go through the card edge. Undecided: which DAC, and where the sound comes out
  — a jack on the carrier, an EDFX-style port board, or HDMI. This affects the
  carrier's connectors, so it is close to the module decision in urgency.
- **Media access — corrected, and not the trap I first wrote.** The Tang Nano 20K's
  microSD is wired **to the FPGA** (4-bit SDIO on I/O 80–85, per PCEHeroTN's own
  constraints), so BIOS images and disc images both live there and cost the carrier
  **zero pins**. It sits at the module's far end, which is the part that sticks out of
  the console, so it stays reachable. Two real constraints remain: those six FPGA I/O
  are spent, and the carrier must keep that end of the module clear of copper and
  parts. What *does* bite is the address width for presenting the BIOS at all —
  [STAGE1-CARD.md](STAGE1-CARD.md) §7.
- **Licence**: the repo has none. The CD reference (`cd.vhd`) is GPL; using it as a
  *specification to read* is prudent, porting it is not, and that line needs writing
  down while it is still cheap.
- **BIOS and disc policy**: the BIOS is not shippable and the user supplies it; test
  discs likewise. Nothing is written about what gets studied and what gets stored.

## 6. Ranked: what to do next

1. **The module decision** (bigger FPGA vs 20K + latch) — it gates the carrier.
2. **Build the 20K stage 1** anyway: it is a passive adapter, a comparator and a ROM,
   and it answers T4b/T8 for the board we can afford to be wrong about.
3. **Run T1c, T1d, T3, T5** with a console, a meter and a scope; start
   `docs/test_results/` so the map stops being paper.
4. **Read one BIOS**: capture what it does at boot (addresses, order, delays) on a
   real or emulated system, and write `docs/BIOS-BEHAVIOUR.md`. This is the single
   highest-value document the project does not have.
5. **Decide audio and media** (DAC + output path; SD socket vs USB), because both
   change the carrier's connectors.

After that: the SCSI command sequence and seek timing, Arcade Card, and only then
anything about HDMI.
