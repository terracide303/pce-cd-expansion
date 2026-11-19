# The card: placement and routing brief

For whoever lays out `hw/card/pce_card.kicad_pcb`. The schematic is generated and
checked (`tools/check_card.py`); the board has every footprint and net
(schematic parity: 0 differences). **Only J101, the card edge, is placed.** The rest
is staged to the right of the outline in one column per schematic sheet.

## Fixed by the console

- **Outline 54.1 × 85.4 mm**, 1.6 mm, 4 layers, ENIG. The finger edge is the bottom
  edge (y = 85.4); order it with a **45° bevel** on that edge.
- **The bottom 8.6 mm goes into the slot.** A rule area forbids vias, parts and pours
  there; only the fingers and the tracks leaving them.
- **The top edge (y = 0) is the only end you can reach** with the card in the
  console. **J5 (USB-C, programming), J102 (USB-C, companion), J103 (audio jack) and
  J6 (microSD) belong on that edge**, facing out. Before fixing them, measure how far
  a real HuCard sticks out of your console (open item in [CARD.md](CARD.md)): parts
  taller than the slot opening (~2.9 mm) must sit in the part that stays outside.
- Check the **power-switch card lock** (T1d) against the outline before ordering.

## Follow the Icepi Zero for the core

The FPGA core is the Icepi Zero v1.4's, part for part. Its layout is proven on the
same stack-up: open `reference/icepi-zero-v1.4` in the upstream repo
(`hardware/v1.4/icepi-zero.kicad_pcb`) side by side and copy the arrangement of:

- **U1** (ECP5, BGA-256 0.8 mm) with its decoupling under/around it, **0.45/0.2 mm
  vias** in the ball field (a custom rule enforces them inside U1's courtyard);
- **U11** SDRAM next to U1, the same side and orientation as on the Icepi, short
  equal-ish lines;
- **U2/U3/U4** regulators with L1–L3 and their capacitors, switch nodes small;
- **U12** config flash and **Y1** 50 MHz oscillator near their balls;
- **U9** FT231X near J5.

Planes as on the Icepi: **In1 = GND, unbroken. In2 = power** (+1V1 under the FPGA
core, +3V3 elsewhere, +2V5 where needed).

## The card's own parts

| part | where | why |
|---|---|---|
| **U101–U103, U104** input translators, **U105** data translator | in a row right behind the 8.6 mm line | short bus stubs from the fingers |
| **R110–R117** (33 Ω) | between U105 and the data fingers | series termination at the source side |
| **R101** (/OE pull-up), **R102** (DIR pull-down), **R103**, **U106** IRQ buffer | next to U105 / U106 | |
| bus banks of **U1** | rotate U1 so **banks 6/7** (address, left side `PL` balls) and **bank 3** (data) face the translators | the freed balls were chosen by bank for this |
| **D101–D103** OR diodes, **C108** | near the regulators | +5V_CON from finger 38, VBUS_FT from J5, VBUS_RP from J102 |
| **U107** RP2040, **U108** flash, **Y101** | between J102 and U1 | the RP2040's QSPI and crystal lines short |
| **U110** PCM5102A, **J103** | near the top edge, away from SDRAM and the regulators' switch nodes | analogue audio |
| **C149** to finger 2 (`BUS_AUDIO`) | route the mono line over GND, away from digital | it goes into the console's mixer |
| test points **TP101–TP108** | reachable with the card on the bench | scope tests T3, T4b, T9 |

## Routing notes

- Every bus line over the unbroken In1 GND plane, finger to translator.
- Track widths: 0.15 mm minimum in the BGA, 0.2 mm default, 0.4 mm for the Power
  net class (`+5V_*`, `VBUS_*`, rails, GND).
- `RP_DP`/`RP_DM` and the FT231X USB pair: short and together (USB full speed; no
  impedance control needed at 12 Mbit/s).
- Run `kicad-cli pcb drc --schematic-parity` and PCB HERO's `check_board.py` (reads
  `board.json`) before ordering.
