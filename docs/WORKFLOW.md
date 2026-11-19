# How the card is designed (the loop)

Everything is generated from data and checked; nothing is drawn by hand. The
general method, and the lessons behind each step, are in PCB HERO's playbook
(`docs/PLAYBOOK.md`) and its case study `docs/case-studies/pce-card.md`.

| step | command | what it proves |
|---|---|---|
| 1. edit the circuit | `hw/card/design.py` | the one place parts and nets are written |
| 2. schematic | `python tools/gen_card.py` | 9 sheets, a global label on every pin |
| 3. check it | `python tools/check_card.py --selftest` | KiCad's netlist = the data; the FPGA core is wired as the working Icepi Zero (except listed changes); edge, 5 V isolation, safe defaults, power, banks; every pin has a pad; ERC. The self-test plants 9 faults first |
| 4. board | `"C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/make_card_pcb.py` | outline, stack-up, rules, fingers, nets from KiCad's netlist (wipes placement) |
| 5. place | `... python.exe tools/place_card.py <icepi-zero.kicad_pcb>` | Icepi block copied and pad-verified, card parts at their pins, translators facing the fingers |
| 5b. silkscreen | `... python.exe tools/silk_card.py` | every reference beside its own part, closer to it than to any other labelled part, never under a part, touching nothing; else to the Fab layer |
| 5c. artwork | `... python.exe tools/art_card.py` | the back panel (disc, stripes, PCE / CD EXPANSION / TERRACIDE303) and the front credit; stroke font only, re-runnable |
| 5d. 3D models | `... python.exe tools/models_card.py` | models for parts whose footprints have none (microSD, buttons, oscillator), aligned to our pads; visual only |
| 6. parity + DRC | `kicad-cli pcb drc --schematic-parity hw/card/pce_card.kicad_pcb` | board = schematic |
| 7. **look at it** | `python ../PCBHero/scripts/snapshot.py hw/card/pce_card.kicad_pcb`, or the panel's Viewer | answer the checklist in writing; fix what the picture shows |
| 8. commit | with what the render showed in the message | |

Steps 4–5 rebuild the board from scratch. Once a human starts editing placement
in KiCad, stop running them and edit in KiCad (or teach `place_card.py` the change).

## Rules learned on this card

- **Pin assignment follows placement.** The FPGA's freed balls (`design.FREED`) are
  assigned by the side they land on: the right side faces the bus channel, the left
  side carries the slow signals. Moving the FPGA means revisiting FREED.
- **Small parts sit at the pin they serve**, not merely near their chip.
- **Chips are turned by checking their placed pads**, never by assuming an orientation.
- **A label must not be readable as another part's**: beside its own part, never under one (hidden once soldered), nearest to its own. If no such spot exists, it goes to the assembly layer; a wrong label is worse than none.
- **Part numbers not looked up stay empty.**
- **Renders are reviewed before a step is called done**: three placement faults
  passed every check and were obvious in a picture.
