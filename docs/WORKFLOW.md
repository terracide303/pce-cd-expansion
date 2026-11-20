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
| 5c. artwork | `... python.exe tools/art_card.py` | front text: PC Engine / TurboGrafx, CD-ROM² (small raised 2), TERRACIDE303, rev; stroke font only, re-runnable |
| 5d. 3D models | `... python.exe tools/models_card.py` | models for parts whose footprints have none (microSD, buttons, oscillator), aligned to our pads; visual only |
| 5e. pre-route | `... python.exe tools/preroute_card.py` | the only ground finger (pin 18) gets a 0.5 mm track and two vias into the GND plane, locked, before any signal |
| 5f. part numbers | `... python.exe tools/sync_fields_card.py` | LCSC fields copied from the design data to the footprints (when they change after placement) |
| 6. parity + DRC | `kicad-cli pcb drc --schematic-parity hw/card/pce_card.kicad_pcb` | board = schematic |
| 7. **look at it** | `python ../PCBHero/scripts/snapshot.py hw/card/pce_card.kicad_pcb`, or the panel's Viewer | answer the checklist in writing; fix what the picture shows |
| 8. route | from `../PCBHero/tools/KiCadRoutingTools`: `python -X utf8 ../../scripts/autoroute_pinned.py in.kicad_pcb out.kicad_pcb` (or the panel) | planes, BGA fanout, every net, at the standard fab floor |
| 9. fab files | `python tools/fab_card.py` | refuses unless DRC (planes refilled) shows 0 unconnected, 0 schematic differences, only accepted items; then gerbers + drill zip, BOM, CPL. Order settings: [ORDER.md](ORDER.md) |
| 10. commit | with what the render showed in the message | |

Steps 4–5 rebuild the board from scratch. Once a human starts editing placement
in KiCad, stop running them and edit in KiCad (or teach `place_card.py` the change).

## Rules learned on this card

- **Pin assignment follows placement.** The FPGA's freed balls (`design.FREED`) are
  assigned by the side they land on: the right side faces the bus channel, the left
  side carries the slow signals. Moving the FPGA means revisiting FREED.
- **A copied footprint is checked by signal, not by pad number.** The edge was copied
  from HuCARD-repro, whose pads are numbered from the other end. Taking those numbers
  as console pins mirrored the card and put the console's +5 V on a ground finger.
  It passed every netlist check: only comparing each finger's *signal* against the
  repro's found it. `fabcheck_card.py` now checks the order.
- **Small parts sit at the pin they serve**, not merely near their chip.
- **Chips are turned by checking their placed pads**, never by assuming an orientation.
- **A label must not be readable as another part's**: beside its own part, never under one (hidden once soldered), nearest to its own. If no such spot exists, it goes to the assembly layer; a wrong label is worse than none.
- **Part numbers not looked up stay empty.**
- **Renders are reviewed before a step is called done**: three placement faults
  passed every check and were obvious in a picture.
- **The rules are the fab's, not ours.** `make_card_pcb.py` holds the floor both
  JLCPCB and PCBWay make at standard price (0.1 mm, 0.45/0.2 mm vias, silkscreen
  1.0 mm text / 0.15 mm lines), written into the board so every DRC checks it.
  A router that relaxes a rule must be caught by that DRC, not trusted.
- **A borrowed board is not automatically buildable.** The Icepi's microSD
  socket had copper 0.025 mm from the edge; the whole block now sits 0.3 mm in.
- **A script that loads a KiCad file must not need a click.** A missing font
  makes KiCad's Python open a dialog and wait; `place_card.py` strips font
  names from the borrowed board before loading it.
- **No via in a pad.** The first standard-floor route put 217 via holes in SMD
  pads (solder wicks down an open via; filling them costs extra). The project
  records `kicad_routing_tools.same_net_pad_clearance = 0.1`, which every router
  step reads.
- **A pin that matters gets its copper by rule, before the router.** The one
  ground finger was the router's last open net twice; now it is pre-routed and
  locked.
