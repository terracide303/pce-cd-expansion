# Ordering the card

The files come from `python tools/fab_card.py`. It refuses to write them unless
KiCad's DRC (planes refilled, the board's own rules) shows 0 unconnected items,
0 schematic differences, and only the accepted items it lists. Upload
`hw/card/fab/pce_card_gerbers.zip`.

The design rules are the ones **both JLCPCB and PCBWay make at standard price**
on 4 layers, from their capability pages (checked 2026-11-19):

| rule | the card | JLCPCB 4-layer | PCBWay |
|---|---|---|---|
| track / gap | 0.1 / 0.1 mm | 0.09 / 0.09 mm | 0.1 / 0.1 mm (4 mil) |
| via hole / pad | 0.2 / 0.45 mm, every via | 0.15 / 0.25 mm min (smaller than 0.2 mm costs more) | 0.15 mm min (under 0.2 mm costs more) |
| via hole to foreign copper | 0.2 mm | 0.2 mm | — |
| copper to milled edge | 0.3 mm (not the fingers) | 0.2 mm | 0.2–0.25 mm |
| silkscreen line / text | 0.15 / 1.0 mm | 0.15 / 1.0 mm | 0.15 / 0.8 mm |

## Settings

| setting | value | why |
|---|---|---|
| layers | 4 | |
| size | 54.1 × 85.4 mm | a HuCard |
| thickness | 1.6 mm | the proven repro thickness (STAGE1-CARD.md) |
| stack-up (JLCPCB) | **JLC04161H-7628** (7628 prepreg 0.2104 mm, core 1.065 mm) | the stack-up in the board file, the Icepi Zero's |
| copper | 1 oz outer, 0.5 oz inner | |
| surface finish | **ENIG** | the fingers and the 0.8 mm BGA |
| gold fingers | **yes, 45° bevel** on the finger edge | the slot; hard gold optional |
| min via hole | 0.2 mm | the board's only via size |
| via covering | tented | |
| board outline tolerance | the tighter option if offered (±0.1 mm) | it slides into the console's slot |
| order number on the silkscreen | "remove" or let the fab choose | there is free space beside the artwork |

PCBWay names the same things: *Gold fingers: yes*, *Beveling of G/F: yes (45°)*,
*Min track/spacing: 4/4 mil*, *Min hole size: 0.2 mm*.

## Assembly

`pce_card_bom.csv` and `pce_card_cpl.csv` are in JLCPCB's columns. Parts
without an LCSC number are listed by `fab_card.py`. Fill them in from parts you
have looked up; never from memory (docs/CARD.md). The ECP5 is a 0.8 mm BGA:
order assembly with X-ray inspection, or have it assembled by someone who does BGA.
The rotation of each part is KiCad's. Check JLCPCB's placement preview before
paying, because a few library footprints are rotated against JLCPCB's.

## Before ordering

- Look at the gerbers in the fab's viewer: fingers bare gold to the edge, the
  artwork on the front, no silkscreen on pads.
- Check the finger pitch and the 8.6 mm insertion against a real HuCard
  (TEST_PLAN.md T1d), if not done yet.
