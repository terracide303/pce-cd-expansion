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
import math, pathlib, sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
ICEPI = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
sys.path.insert(0, str(ROOT / "hw" / "card"))
import design  # noqa: E402

W, H, SLOT = 54.1, 85.4, 8.6
ICEPI_EDGE_LEFT, ICEPI_EDGE_BOTTOM = 115.975, 120.025       # Icepi board edges (x of the SD edge, y of the USB edge)
J5_GROUP = ["J5", "U10", "R36", "R37", "TP13", "TP14"]


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


def main():
    board = pcbnew.LoadBoard(str(PCB))
    icepi = pcbnew.LoadBoard(str(ICEPI))
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
    dx, dy = 0 - px, 0 - py          # the corner (SD edge, USB edge) -> card (0, 0)
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

    # connectors on the outer edge, openings up (rot 180 = the USB4105 opening at -y)
    put("J102", 31.0, 2.275, 180)
    put("J103", 48.1, 8.5, 0)        # plug opening (the snout, -y) flush with the outer edge
    # bus row right behind the slot zone (y < 76.8)
    put("U101", 13.0, 71.5, 90)
    put("U105", 26.0, 71.5, 90)
    put("U102", 38.5, 71.5, 90)
    put("U103", 48.5, 71.5, 90)
    put("U104", 4.0, 70.0, 0)
    put("U106", 4.0, 74.5, 0)
    # companion, audio, power in the free column beside the block
    put("U107", 33.0, 19.0, 0)
    put("U108", 46.0, 22.5, 0)
    put("Y101", 38.5, 13.0, 0)
    put("U110", 40.0, 38.0, 0)
    put("D101", 47.0, 52.0, 0)
    put("D102", 47.0, 55.5, 0)
    put("D103", 47.0, 59.0, 0)

    fixed = {"J102", "J103", "U101", "U102", "U103", "U104", "U105", "U106", "U107", "U108", "Y101", "U110",
             "D101", "D102", "D103"}
    anchor = {}
    for p in design.PARTS:
        r = p["ref"]
        if p["origin"] != "card" or r in fixed or r.startswith("#") or r == "J101":
            continue
        net = {n for n in p["pins"].values() if n} - {"GND", "+3V3"}
        sheet = p["sheet"]
        if r.startswith("TP10"):
            a = (30.0, 63.0)
        elif r in ("R110", "R111", "R112", "R113", "R114", "R115", "R116", "R117"):
            a = (26.0, 75.5)
        elif r in ("R101", "R102", "C105", "C106"):
            a = (26.0, 66.0)
        elif r in ("C101", "C102", "C103", "C104"):
            a = {"C101": (13, 66), "C102": (38.5, 66), "C103": (48.5, 66), "C104": (8, 70)}[r]
        elif r in ("C107", "R103"):
            a = (8.0, 75.0)
        elif r in ("R125", "R126", "R127", "R128", "U109", "C136"):
            a = (31.0, 10.5)
        elif sheet == "companion":
            a = (33.0, 19.0)
        elif sheet == "audio":
            a = (40.0, 38.0)
        else:
            a = (45.0, 55.0)
        anchor[r] = a

    def free(box, side="F"):
        x0, y0, x1, y1 = box
        if x0 < 0.4 or x1 > W - 0.4 or y0 < 0.4 or y1 > H - SLOT - 0.3:
            return False
        for o in occupied[side]:
            if x0 < o[2] + 0.2 and x1 > o[0] - 0.2 and y0 < o[3] + 0.2 and y1 > o[1] - 0.2:
                return False
        return True

    order = sorted(anchor, key=lambda r: (anchor[r], r))
    unplaced = []
    for ref in order:
        fp = fps[ref]
        ax, ay = anchor[ref]
        done = False
        for rot in (0, 90):
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(mm(ax, ay))
            cx0, cy0, cx1, cy1 = courtyard(fp)
            ox, oy = ax - cx0, ay - cy0          # courtyard offset from the anchor point
            w, h = cx1 - cx0, cy1 - cy0
            best = None
            for ring in range(0, 120):
                step = 0.25 * ring
                cands = [(ax + dx, ay + dy) for dx in (-step, 0, step) for dy in (-step, 0, step)] if ring else [(ax, ay)]
                for k in range(-ring, ring + 1):
                    cands += [(ax + 0.25 * k, ay - step), (ax + 0.25 * k, ay + step), (ax - step, ay + 0.25 * k), (ax + step, ay + 0.25 * k)]
                for (x, y) in cands:
                    box = (x - ox, y - oy, x - ox + w, y - oy + h)
                    if free(box):
                        d = math.hypot(x - ax, y - ay)
                        if best is None or d < best[0]:
                            best = (d, x, y, box)
                if best:
                    break
            if best:
                fp.SetPosition(mm(best[1], best[2]))
                occupied["F"].append(best[3])
                done = True
                break
        if not done:
            unplaced.append(ref)
    if unplaced:
        print("NOT PLACED (no room near the anchor):", unplaced)
    board.Save(str(PCB))
    print(f"saved {PCB.relative_to(ROOT).as_posix()}: {len(kept)} Icepi parts as a block, "
          f"{len(anchor) + len(fixed)} card parts placed")


if __name__ == "__main__":
    main()
