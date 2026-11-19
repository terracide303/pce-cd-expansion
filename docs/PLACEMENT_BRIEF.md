# Placement brief: stage 1 board

**Placement is yours** (PCB HERO's rule: a human places parts). This is the
proposal to place from. Open `hw/stage1/pce_exp_stage1.kicad_pro`, then the
PCB. Every footprint is already on the board with its nets, staged in labelled
groups to the right of a suggested outline. Drag them in.

The board carries exactly the schematic's connections: KiCad's own
schematic-parity check reports **0 differences**.

## The two things that decide everything

1. **J1 (the 3×23 port socket) sits on a board edge** so the board can plug
   onto the console's rear port. Before anything else, settle how the board
   hangs off the console: straight out the back, or folded down. That sets
   which edge J1 is on and whether it goes on the top or bottom side.
   **Do test T1b** (print the footprint 1:1 against the console) once J1's
   position and side are fixed. A mirrored port is the one mistake this board
   can't survive.
2. **The Tang's USB-C end (L1/R1, marked "USB-C" on the silkscreen) faces away
   from the console**, so you can still power and program it with the board
   plugged in. Its HDMI connector is at the other end; keep that end clear too
   if you'll want HDMI later.

## Groups, closest to the port first

| group | parts | keep it | why |
|---|---|---|---|
| **5 V side** | U1 (decoder), U2 (data translator), U3, U4, U5 (input translators) | **next to J1**, in a row along it | every console line runs J1 → one of these. Short 5 V traces mean less ringing on the console's bus. Rough fan-out: A0–A7 → U3, A8–A15 → U4, A16–A20 → U1, D0–D7 → U2, /RD, /WR → U5 and U2 |
| **series resistors** | R1–R8 (33 Ω) | **next to U2's B side** (pins 14–21) | they limit current during a direction change; they belong at the translator |
| **decoupling** | C1 at U1, C2 at U2 pin 1 (VCCA, 5 V), C3 at U2 pin 23/24 (VCCB, 3.3 V), C4/C5/C6 at U3/U4/U5 pin 20 | **each within ~3 mm of its pin**, short via to ground | the translators switch fast; a cap far away does nothing |
| **bulk** | C7 (10 µF, +5VA), C8 (10 µF, +3V3) | C7 near J1's +5A pins (a2, c21), C8 near the Tang's 3V3 pins (L19, R16) | |
| **the Tang** | A1 | after the 5 V side, USB-C outward | the 3.3 V traces to it can be longer: they're behind the translators |
| **test points** | TP1–TP6 | on an edge you can reach with a probe while it's plugged in | TP1 /RD, TP2 D0, TP3 /SEL, TP4 A20, TP5/TP6 ground: what TEST_PLAN T3 and T9 need |

## Rules for the copper (already set in `pce_exp_stage1.kicad_dru`)

- 2 layers, JLCPCB standard. Drawn at 0.25 mm tracks, 0.2 mm clearance,
  0.6/0.3 mm vias, 0.5 mm power tracks; the fab's floor is 0.127/0.127.
- **Bottom layer: one unbroken ground pour**, especially under the lines from
  J1 to the translators. No DRC can check that; look at it.
- J1's GND pins are c8, c17 and c20. GNDA (a21, c2) stays unconnected: it's the
  console's analog ground.

## Rough size

Tang 54 × 23 mm, port 6 × 58 mm, five small chips: about **80 × 65 mm** is a
sensible start. The suggested outline is 100 × 75 mm; shrink it to fit.

## After placement

Tell Claude placement is done. It then routes with PCB HERO (`autoroute.py`,
pinned to the fab floor), grades the result, and checks the ground pour before
you look.
