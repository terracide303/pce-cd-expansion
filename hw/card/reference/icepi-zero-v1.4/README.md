# Icepi Zero v1.4: vendored reference

From [cheyao/icepi-zero](https://github.com/cheyao/icepi-zero) at commit `32c2d122a0a8db4ad3d4d65fbdb84a63b469e29a`,
`hardware/v1.4`. Licence: **Solderpad Hardware License v2.1** ([LICENSE](LICENSE)),
© Chengyin Yao (cheyao). OSHWA certified FR000026.

| file | what |
|---|---|
| `icepi-zero.net` | KiCad netlist exported from the v1.4 schematic (kicad-cli 10.0.6, 2026-11-19) |
| `icepi-embedded.kicad_sym` | every symbol embedded in the v1.4 schematic, as used there (lib ids "lib:name" stored as "lib__name") |
| `icepi-lib.pretty/` | the board's own footprints (upstream folder is spelled `icepi-lib.petty`) |
| `bom.csv` | the production BOM with LCSC part numbers |

The card's FPGA core (power, configuration, flash, SDRAM, microSD, USB-JTAG) is
derived from this netlist by `hw/card/design.py`, and `tools/check_card.py` proves
that the card's copy is connected exactly as here, except for the documented changes.
