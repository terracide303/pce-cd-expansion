#!/usr/bin/env python3
"""First-pass placement of the card, scripted, for a human to review and refine.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/place_card.py

1. THE ICEPI BLOCK. Every kept Icepi part goes exactly where it is on the Icepi Zero
   v1.4 board (position, rotation, side), and the whole block is then rotated 90 deg
   so the Icepi's SD-card edge becomes the card's outer edge (y = 0). Each footprint's
   pads are compared with the Icepi board's pads before the move: the copy must be exact.
2. J5 GROUP. The FT231X's USB-C (J5) sits on the Icepi's bottom edge, which would be
   the card's side, inside the console. J5 with U10, R36, R37, TP13, TP14 is moved as a
   unit to the outer edge, keeping its own arrangement.
3. THE CARD'S OWN PARTS. Connectors on the outer edge; translators in a row right
   behind the slot zone; RP2040, audio and power in the free column beside the block.
   Main chips at fixed spots, their small parts packed greedily as close as possible
   to them, never overlapping a courtyard on the same side.

Reads and writes hw/card/pce_card.kicad_pcb. Close the board in KiCad first.
"""
import math, pathlib, re, sys, tempfile

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
ICEPI = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
sys.path.insert(0, str(ROOT / "hw" / "card"))
import design  # noqa: E402

W, H, SLOT = 54.1, 85.4, 8.6
ICEPI_EDGE_LEFT, ICEPI_EDGE_BOTTOM = 115.975, 120.025       # Icepi board edges (x of the SD edge, y of the USB edge)
J5_GROUP = ["J5", "U10", "R36", "R37", "TP13", "TP14"]
BLOCK_INSET = 0.3                # mm the Icepi block sits in from the SD edge (copper to edge)


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def xy(v):
    return pcbnew.ToMM(v.x), pcbnew.ToMM(v.y)


def courtyard(fp):
    """(x0, y0, x1, y1) of the courtyard on the footprint's side, mm."""
    layer = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    try:
        bb = fp.GetCourtyard(layer).BBox()
        if bb.GetWidth() > 0:
            return (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    except Exception:
        pass
    bb = fp.GetBoundingBox(False)
    return (pcbnew.ToMM(bb.GetX()), pcbnew.ToMM(bb.GetY()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))


def pads_abs(fp):
    return sorted((p.GetNumber(), round(pcbnew.ToMM(p.GetPosition().x), 3), round(pcbnew.ToMM(p.GetPosition().y), 3))
                  for p in fp.Pads())


def rotate_about(fp, cx, cy, deg):
    fp.Rotate(mm(cx, cy), pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T))


def load_without_fonts(path):
    """Load a board with its text fonts removed. The Icepi names "Fira Code" for one
    text; where that font is not installed, KiCad's Python opens a "font not found"
    dialog and waits for a click, so a script hangs. Positions and pads do not depend
    on fonts."""
    text = re.sub(r'\s*\(face "[^"]*"\)', "", pathlib.Path(path).read_text(encoding="utf-8"))
    tmp = pathlib.Path(tempfile.mkdtemp()) / pathlib.Path(path).name
    tmp.write_text(text, encoding="utf-8")
    return pcbnew.LoadBoard(str(tmp))


def main():
    board = pcbnew.LoadBoard(str(PCB))
    icepi = load_without_fonts(ICEPI)
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    src = {fp.GetReference(): fp for fp in icepi.GetFootprints()}
    kept = [p["ref"] for p in design.PARTS if p["origin"] == "icepi"]

    # 1. copy the Icepi placement exactly, then verify pad by pad
    bad = []
    for ref in kept:
        fp, s = fps[ref], src[ref]
        if fp.IsFlipped() != s.IsFlipped():
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        fp.SetPosition(s.GetPosition())
        fp.SetOrientation(s.GetOrientation())
        a = pads_abs(fp)
        b = pads_abs(s)
        if [x[1:] for x in a] != [x[1:] for x in b] or [x[0] for x in a] != [x[0] for x in b]:
            # pad sets can differ only by naming (J5 S1/SH); compare positions as sets
            if sorted(x[1:] for x in a) != sorted(x[1:] for x in b):
                bad.append(ref)
    if bad:
        sys.exit(f"pads do not match the Icepi after copying: {bad}")
    print(f"copied {len(kept)} Icepi placements; pads identical to the Icepi board")

    # the block transform: rotate -90 deg (clockwise on screen) so Icepi +x -> card +y,
    # then translate so the Icepi's SD edge lands on y = 0 and its USB edge on x = 0.
    for ref in kept:
        rotate_about(fps[ref], 0, 0, -90)
    # after rotation, a point (x, y) is at (-y, x)?  Find the translation from a known point.
    probe = pcbnew.VECTOR2I(mm(ICEPI_EDGE_LEFT, ICEPI_EDGE_BOTTOM))
    t = pcbnew.FOOTPRINT(board)
    t.SetPosition(probe)
    t.Rotate(mm(0, 0), pcbnew.EDA_ANGLE(-90, pcbnew.DEGREES_T))
    px, py = xy(t.GetPosition())
    # the corner (SD edge, USB edge) -> card (0, BLOCK_INSET). The inset is the one
    # departure from the Icepi: its microSD socket's shield tabs sit 0.025 mm from the
    # SD edge; JLCPCB and PCBWay need 0.2 mm copper to a milled edge. The whole block
    # moves, so nothing inside it changes.
    dx, dy = 0 - px, 0 - py + BLOCK_INSET
    for ref in kept:
        fps[ref].Move(mm(dx, dy))
    j6 = courtyard(fps["J6"])
    print(f"block placed: J6 (microSD) at x {j6[0]:.1f}-{j6[2]:.1f}, y {j6[1]:.1f}-{j6[3]:.1f}")

    # 2. J5 group to the outer edge, opening up (-y)
    jx, jy = xy(fps["J5"].GetPosition())
    for ref in J5_GROUP:
        rotate_about(fps[ref], jx, jy, -90)
    jx2, jy2 = xy(fps["J5"].GetPosition())
    target = (5.75, 2.275)           # courtyard just clear of the microSD socket J6
    for ref in J5_GROUP:
        fps[ref].Move(mm(target[0] - jx2, target[1] - jy2))

    # 3. the card's own parts
    occupied = {"F": [], "B": []}
    for ref, fp in fps.items():
        if ref in kept or ref == "J101":
            occupied["B" if fp.IsFlipped() else "F"].append(courtyard(fp))

    def put(ref, x, y, rot=0):
        fp = fps[ref]
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(mm(x, y))
        occupied["F"].append(courtyard(fp))

    # Main parts at chosen spots. Signal flow: the bus leaves U1's right side and runs
    # down the free column to the translator row; the RP2040 link and I2S leave U1's
    # upper-left and cross the top of the block to the companion and the DAC.
    put("J102", 31.0, 2.275, 180)     # companion USB-C, opening at the outer edge
    put("J103", 48.1, 8.5, 0)         # jack: plug opening (the snout, -y) flush with the outer edge
    put("U109", 31.0, 10.0, 0)        # USB ESD right behind J102
    put("U107", 33.0, 22.0, 0)        # RP2040
    put("U108", 33.0, 33.5, 0)        # its QSPI flash, below it
    put("U110", 47.0, 27.0, 90)       # DAC under the jack
    put("D101", 47.0, 43.0, 0)        # 5 V OR diodes
    put("D102", 47.0, 46.5, 0)
    put("D103", 47.0, 50.0, 0)
    # The bus row, right behind the slot zone. Each translator sits over the fingers it
    # serves; seen from the front, pin 38 (+5 V) is at the left edge and pin 1 at the
    # right (gen_card.py edge_footprint), so A0-A7 (pins 7-14) are right of centre.
    put("U101", 41.1, 71.5, 90)       # A0-A7
    put("U105", 28.1, 69.3, 90)       # D0-D7. 2.2 mm higher than the others: its 33 ohm resistors go between it and the fingers; clear of the SDRAM
    put("U102", 15.6, 71.5, 90)       # A8-A15
    put("U103", 5.6, 71.5, 90)        # A16-A20, /RD, /WR, /RST
    put("U104", 50.1, 69.5, 0)        # HSM
    put("U106", 50.1, 74.5, 0)        # /IRQ2
    # Translators: turn each one so its CONSOLE-side pins (BUS_* / T_D*) face the fingers
    # (larger y) and its FPGA-side pins face the FPGA. Checked on the placed pads, not assumed.
    for ref in ("U101", "U102", "U103", "U104", "U105", "U106"):
        fp = fps[ref]

        def side_y(fp=fp):
            con = [xy(pd.GetPosition())[1] for pd in fp.Pads() if pd.GetNetname().lstrip("/").startswith(("BUS_", "T_D"))]
            fpga = [xy(pd.GetPosition())[1] for pd in fp.Pads() if pd.GetNetname().lstrip("/").startswith("F_")]
            return sum(con) / len(con), sum(fpga) / len(fpga)
        c, f = side_y()
        if c < f:
            fp.Rotate(fp.GetPosition(), pcbnew.EDA_ANGLE(180, pcbnew.DEGREES_T))
        c, f = side_y()
        print(f"{ref}: console pins at y {c:.1f}, FPGA pins at y {f:.1f} (console side faces the fingers: {c > f})")
    fixed = {"J102", "J103", "U109", "U107", "U108", "U110", "D101", "D102", "D103",
             "U101", "U102", "U103", "U104", "U105", "U106"}

    # Every small part is anchored at the PIN it serves, pushed outward from its chip:
    # decoupling at its own supply pin, pull-ups at their pin, series resistors on
    # their line. CHIP says which chip a part belongs to.
    CHIP = {**{f"C{120 + i}": "U107" for i in range(12)}, "C135": "U107", "R123": "U107", "R124": "U107",
            "D104": "U107", "R122": "U107", "R136": "U107", "Y101": "U107", "C133": "Y101", "C134": "Y101",
            "C132": "U108", "R120": "U108", "R121": "U108", "SW101": "U108",
            "R125": "J102", "R126": "J102", "R127": "U109", "R128": "U109", "C136": "J102",
            **{f"C{140 + i}": "U110" for i in range(7)}, "C150": "U110", "C151": "U110", "R130": "U110", "R131": "U110", "R132": "U110",
            "C147": "J103", "C148": "J103", "R133": "U110", "R134": "U110", "R135": "U110", "C149": "U110",
            "C101": "U101", "C102": "U102", "C103": "U103", "C104": "U104", "C105": "U105", "C106": "U105",
            "R101": "U105", "R102": "U105", "C107": "U106", "R103": "U106", "C108": "D101",
            **{f"R{110 + i}": "U105" for i in range(8)}}
    POWER = {"GND", "+3V3", "+1V1_RP", "+5V_CON", "+5V_CARD"}
    claimed = set()

    def pin_anchor(ref):
        chip = fps[CHIP[ref]]
        cx, cy = xy(chip.GetPosition())
        mine = {pd.GetNetname() for pd in fps[ref].Pads()} - {""}
        best = None
        for pd in chip.Pads():
            n = pd.GetNetname()
            if n not in mine or n.lstrip("/") == "GND":
                continue
            key = (CHIP[ref], pd.GetNumber())
            px, py = xy(pd.GetPosition())
            # a signal net is a firm match; a shared supply pin is claimed one part at a time
            score = (0 if n.lstrip("/") not in POWER else 1, key in claimed, 0)
            if best is None or score < best[0]:
                best = (score, key, px, py)
        if best is None:
            return cx, cy
        if best[0][0] == 1:
            claimed.add(best[1])
        _, _, px, py = best
        dx, dy = px - cx, py - cy
        d = math.hypot(dx, dy) or 1
        return px + 2.2 * dx / d, py + 2.2 * dy / d

    def free(box, side="F"):
        x0, y0, x1, y1 = box
        if x0 < 0.4 or x1 > W - 0.4 or y0 < 0.4 or y1 > H - SLOT - 0.3:
            return False
        for o in occupied[side]:
            if x0 < o[2] + 0.2 and x1 > o[0] - 0.2 and y0 < o[3] + 0.2 and y1 > o[1] - 0.2:
                return False
        return True

    def place_near(ref, ax, ay):
        fp = fps[ref]
        best = None
        for rot in (0, 90):
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(mm(ax, ay))
            cx0, cy0, cx1, cy1 = courtyard(fp)
            ox, oy, w, h = ax - cx0, ay - cy0, cx1 - cx0, cy1 - cy0
            for ring in range(0, 100):
                s = 0.25 * ring
                cands = [(ax, ay)] if ring == 0 else (
                    [(ax + 0.25 * k, ay - s) for k in range(-ring, ring + 1)] + [(ax + 0.25 * k, ay + s) for k in range(-ring, ring + 1)]
                    + [(ax - s, ay + 0.25 * k) for k in range(-ring, ring + 1)] + [(ax + s, ay + 0.25 * k) for k in range(-ring, ring + 1)])
                hit = None
                for (x, y) in cands:
                    box = (x - ox, y - oy, x - ox + w, y - oy + h)
                    if free(box):
                        d = math.hypot(x - ax, y - ay)
                        if hit is None or d < hit[0]:
                            hit = (d, x, y, box)
                if hit:
                    if best is None or hit[0] < best[0]:
                        best = (hit[0], rot, hit[1], hit[2], hit[3])
                    break
        if best is None:
            return False
        fp.SetOrientationDegrees(best[1])
        fp.SetPosition(mm(best[2], best[3]))
        occupied["F"].append(best[4])
        return True

    unplaced = []
    # Y101 first (its caps anchor to it), then the rest in a stable order
    order = ["Y101"] + sorted(r for r in CHIP if r != "Y101")
    for ref in order:
        if not place_near(ref, *pin_anchor(ref)):
            unplaced.append(ref)
    # test points in a column along the right edge, on a 2.54 mm pitch, reachable on the bench
    tps = sorted(r for r in fps if r.startswith("TP1") and r not in kept)
    for i, ref in enumerate(tps):
        if not place_near(ref, 51.6 - (i // 6) * 2.6, 54.0 + (i % 6) * 2.54):
            unplaced.append(ref)
    rest = [p["ref"] for p in design.PARTS if p["origin"] == "card" and not p["ref"].startswith("#")
            and p["ref"] not in fixed and p["ref"] not in CHIP and p["ref"] not in tps and p["ref"] != "J101"]
    for ref in rest:
        if not place_near(ref, 45.0, 55.0):
            unplaced.append(ref)

    # silkscreen: references of small parts go to the assembly (Fab) layer; the silk
    # keeps chips and connectors, so it stays readable on a dense board
    small = ("R_0402", "R_0603", "C_0402", "C_0603", "C_0805", "L_0805", "LED_0603", "D_SOD", "TestPoint", "R_0201")
    moved = 0
    for fp in fps.values():
        if any(s in fp.GetFPID().GetLibItemName().wx_str() for s in small):
            ref = fp.Reference()
            ref.SetLayer(pcbnew.B_Fab if fp.IsFlipped() else pcbnew.F_Fab)
            moved += 1
    print(f"silkscreen: {moved} small-part references moved to the Fab layer")
    anchor = CHIP
    if unplaced:
        print("NOT PLACED (no room near the anchor):", unplaced)
    board.Save(str(PCB))
    print(f"saved {PCB.relative_to(ROOT).as_posix()}: {len(kept)} Icepi parts as a block, "
          f"{len(anchor) + len(fixed)} card parts placed")


if __name__ == "__main__":
    main()
