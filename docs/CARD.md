# The card: final board architecture

Decided 2026-11-19 with the owner. This is the board the project ships: one
HuCard-sized card that is the flash cart and, later, the whole CD-ROM² system,
EverDrive style. It replaces boards A and B ([CARRIER-ARCH.md](archive/CARRIER-ARCH.md)).

## Status (2026-11-20)

| step | state |
|---|---|
| schematic | **generated** (`hw/card/`, 9 sheets) from `hw/card/design.py` by `tools/gen_card.py` |
| checks | **all pass** (`python tools/check_card.py --selftest`): KiCad netlist = design; the FPGA core is wired exactly as the working Icepi Zero v1.4 apart from the documented changes; edge, 5 V isolation, safe defaults, power OR-ing, 3.3 V banks; every pin has a pad; ERC. The self-test plants 9 faults and catches all 9 |
| review | independent schematic review 2026-11-20: [REVIEW-2026-11-20.md](REVIEW-2026-11-20.md). It found the edge fingers mirrored (fixed) and a few pull-up and decoupling changes (made) |
| PCB | placed by script (`tools/place_card.py`), fingers in the HuCARD-repro order, ground finger pre-routed; routing in progress. Steps in [WORKFLOW.md](WORKFLOW.md) |
| BOM | LCSC numbers on the Icepi parts and on the card's plain passives; the rest to fill when ordering ([ORDER.md](ORDER.md)) |

Regenerate after editing `design.py`:

```
python tools/gen_card.py
python tools/check_card.py --selftest
"C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/make_card_pcb.py   # only before placement starts
```

## Choices (owner, 2026-11-19)

| question | answer |
|---|---|
| FPGA | Lattice ECP5 **LFE5U-45F-6BG256**, on the card ([FPGA-ECP5.md](FPGA-ECP5.md)) |
| size | **HuCard, 54.1 × 85.4 mm**, fingers copied from the working HuCARD-repro card, order and lengths included (`tools/gen_card.py` `edge_footprint`) |
| video out | **none**: the console's own AV output |
| SD card, menu, loading | **RP2040 companion** (FPGA-Companion firmware, as in the MiSTle family) |
| programming | **USB-C + FT231X** on-board USB-JTAG, openFPGALoader |
| CD audio | **mono into the console** (card pin 2) **and a stereo 3.5 mm jack** |

## Where each block comes from

Nothing in the FPGA's core circuit is new. It is copied from hardware that works:

| block | source | status of the source |
|---|---|---|
| ECP5 power (1.1 V core, 2.5 V aux, 3.3 V banks: 3 × TLV62569), decoupling | Icepi Zero v1.4 | **working**: the owner has a 45F Icepi Zero |
| configuration: 50 MHz oscillator, W25Q128 flash, PROGRAMN/DONE/INITN, CFG pins | Icepi Zero v1.4 | working |
| USB-JTAG: FT231XQ bit-banging JTAG, USB-C, ESD | Icepi Zero v1.4 | working |
| 32 MB SDRAM (W9825G6KH) | Icepi Zero v1.4 | working |
| microSD (on the FPGA, read by the companion through it) | Icepi Zero v1.4 | working |
| RP2040 + W25Q16 + 12 MHz crystal, SPI link to the FPGA (SCK, MOSI, MISO, CS, IRQ) | MiniMistle 0.2 (owner's ECP5 board) and the Raspberry Pi RP2040 minimal design | MiniMistle not yet fabbed: cross-check against the Raspberry Pi reference |
| **card edge, bus translators, audio, power input** | **new**, this project | stage-1 translator design and its 55 ns simulation carry over |

Licence of the copied parts: Icepi Zero is **Solderpad Hardware v2.1**
(Apache-2.0 wrapper): keep its notice and credit in the schematic title block.

## Block diagram

```
 console slot (38 fingers, 5 V)                         outer end of the card
 ──────────────────────────────                          ─────────────────────
 A0–A20, /RD, /WR, /RST ──► 74LVC245A ×3 (3.3 V, 5 V-tolerant in) ──► ECP5
 HSM ──► 74LVC1G34 ──► ECP5
 D0–D7 ◄──33 Ω──► SN74LVC8T245 (B = console 5 V, A = 3.3 V) ◄──────────► ECP5
                     DIR, /OE ◄── ECP5 (pulled safe: /OE high, DIR toward FPGA)
 /IRQ2 ◄── 74LVC1G07 open drain ◄── ECP5
 AUDIO IN (pin 2) ◄── L+R mix, coupling cap ◄── PCM5102A DAC ◄─I2S── ECP5
                                                    └──► 3.5 mm stereo jack
 /CD (pin 1) ── GND (a card is present)
 +5 V (pin 38) ──Schottky──┐
 USB-C (FT231X) VBUS ─Schottky┴─► +5V_CARD ─► TLV62569 ×3 ─► 3.3 / 2.5 / 1.1 V
                                                  ECP5 ◄─SPI─► RP2040 ── USB-C
                                                  ECP5 ── SDRAM, config flash, microSD
                                                  ECP5 ── FT231X (JTAG/UART) ── USB-C
```

## Power

- **Console +5 V (pin 38)** runs the card in the console. **USB** runs it on the
  bench. The two meet through **Schottky diodes** into `+5V_CARD`, so USB can never
  push current into the console's 5 V rail, and the console cannot feed a PC.
- The translators' **5 V side is the console's +5 V directly, never `+5V_CARD`.**
  On the bench with the console off, that side is unpowered and the translators'
  partial-power-down (Ioff) keeps them off the bus.
- **Unknown, and a test:** how much current the slot can give. A HuCard draws very
  little; this card is an FPGA, SDRAM and a microcontroller, roughly
  **150–300 mA at 5 V** (estimate). Measure the console's 5 V rail under load before
  the first power-up in the slot (new TEST_PLAN item).

## Bus interface, and the one safety rule

- The FPGA decodes **every** window itself (no 74HCT688): it sees A0–A20, /RD, /WR.
- The data translator's **DIR and /OE come from the FPGA.** While the FPGA is
  unconfigured (power-up, reprogramming) its pins float, so:
  **/OE has a pull-up and DIR a pull toward "console → FPGA".** An unconfigured card
  must never drive the console's data bus. The schematic checker enforces both.
- 33 Ω series resistors on D0–D7, console side, as in stage 1.
- `/IRQ2` through an open-drain buffer: the line is shared.
- `/RST` and `HSM` are inputs: reset follows the console, HSM tells the FPGA the
  bus speed.

## FPGA pins

The card drops the Icepi's Pi header, HDMI port and FPGA soft-USB ports, freeing
**49 balls** that the Icepi already routes on 4 layers (all banks at 3.3 V):

| bank | balls freed | used for |
|---|---|---|
| old Pi header (32) | header GPIO | D0–D7, DIR, /OE, A0–A19, /RD, /WR |
| old GPDI pairs (8) | GPDI data | RP2040 link (5), I2S to the DAC (3) |
| old soft-USB / GPDI control (9) | | A20, /RST, HSM, /IRQ2, two spares to test points |

The exact balls are in `FREED` in `hw/card/design.py`.

**Needed 46 of 49.** At 7.16 MHz any ball in a bank serves, so the exact
assignment is the layout's choice. The schematic gives a starting map, swappable
within the bank.

## Open before ordering

| item | how |
|---|---|
| console 5 V headroom | measure (TEST_PLAN) |
| how far a HuCard sticks out of the console, i.e. where the USB-C ports and the jack can sit | measure; it also fixes the outline's outer end |
| power switch card lock clearance | T1d |
| the core port to the ECP5 | the owner |
