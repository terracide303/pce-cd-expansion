# The FPGA: Lattice ECP5 45F, on the card

**Decision (owner, 2026-11-19):** the owner ports their PC Engine core to a Lattice
ECP5, because it costs less than the bigger Gowin modules. The card carries an
**LFE5U-45F in the CABGA256 package**, the same package as the 25F on the
inspiration board, so the 25F board's pinout carries over.

## The inspiration board: Icepi Zero

[cheyao/icepi-zero](https://github.com/cheyao/icepi-zero), read 2026-11-19:

| | |
|---|---|
| FPGA | LFE5U-25F, CABGA256 (`gateware/board.mk`: `--25k --package CABGA256`) |
| size | Raspberry Pi Zero, 65 × 30 mm |
| memory | 256 Mbit SDRAM (16-bit), 128 Mbit flash, microSD, 112 KiB block RAM |
| other | 50 MHz oscillator, on-board USB-JTAG/UART, mini HDMI-style video, 3 × USB-C |
| user I/O on the 40-pin header | **28**, LVCMOS33 (`gateware/v1.4/icepi-zero-v1_4.lpf`) |
| PCB | 4-layer, JLC04121H-7628 stack-up, 1.2 or 1.6 mm, KiCad sources in `hardware/v1.0`–`v1.4` |
| licence | **Solderpad Hardware License v2.1**, a wrapper around Apache-2.0: reuse allowed with attribution and the licence notice |

## What changes for this project

- **The pin shortage disappears**, but only with the chip **on the card**. A plug-in
  Icepi Zero would bring just 28 header I/Os (barely more than the Tang's 24 safe
  pins). The bare chip in CABGA256 has far more user I/O than the card can use, so
  the card can do what the EverDrive does: the FPGA answers the whole bus itself
  (A0–A20, D0–D7, /RD, /WR) and has pins left for SDRAM, SD and audio.
- **Board A and board B become one board.** The SRAM-carrier workaround (board B)
  existed only because of the pin count.
- **Level shifters stay.** The ECP5's I/O is 3.3 V and not 5 V tolerant; the console
  bus is 5 V. The translator stage, decoder and 33 Ω resistors from stage 1 carry over.
- **Size**: the Icepi Zero fits its FPGA, SDRAM, flash and SD on 65 × 30 mm. Our
  limit is 54.1 × 94.4 mm with ~8.6 mm of fingers, so this fits with room left.
- **Manufacture**: a 0.8 mm-pitch BGA and 4 layers. The board is **fab-assembled**
  (the Icepi Zero's gerbers are made for JLCPCB), not hand-soldered. Our KiCad flow
  and PCB HERO still apply; the BGA fan-out follows the Icepi Zero's layout.

## To check before the schematic

| question | how |
|---|---|
| is the LFE5U-45F in CABGA256 truly drop-in for the 25F (same ball map, power and config pins)? | Lattice ECP5 pinout files for both devices, compared ball by ball (a script, like `ext_bus.py`) |
| the 45F's block RAM and LUTs (more than the 25F's 24k LUT / 112 KiB) | Lattice ECP5 family datasheet |
| price and stock of the 45F BG256 at the fab's assembly service | the fab's parts library |
| toolchain for the port: the MiSTer CD logic is **VHDL**; the open flow (Yosys + nextpnr) needs the GHDL plugin for VHDL, Lattice Diamond reads it natively | the Icepi Zero's `gateware/DIAMOND.md` and a test synthesis of `cd.vhd` |
| the Gowin-specific parts of the core to replace (PLL, block RAM, HDMI serialiser, SDRAM timing) | a list from the PCEHeroTN sources |

## What still holds

The card edge and its dimensions, the translator stage, the stage-1 RTL and its
55 ns simulation result, the test plan, the MiSTer CD reference and the EverDrive
reference all stay valid. The Tang Nano 20K board A stays possible as a cheap bench
test of the bus, but it is no longer on the path to the product.
