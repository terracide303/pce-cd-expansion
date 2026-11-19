#!/usr/bin/env python3
"""Place every silkscreen reference so it overlaps nothing.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/silk_card.py

Run after tools/place_card.py. For each reference that is on a silkscreen layer, try
spots beside its part (above, below, left, right, sliding a little), straight and
turned 90 deg, at the
normal size and then smaller, and keep the first where the text touches nothing:
no other text, no silkscreen line, no pad or hole, inside the board with a margin,
outside the slot keep-out, never on top of any part (hidden once soldered), and
closer to its own part than to any other, so it cannot be read as another part's label. A reference that fits nowhere goes to the Fab
(assembly) layer, so it is still on the assembly drawing. Prints what it did.

Library footprints draw their outlines at 0.12 mm; every silkscreen line thinner
than MIN_LINE is widened to it first (filled shapes keep their fill). Where those
lines meet a pad, the fab clips the silkscreen off the copper.
"""
import pathlib, sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
W, H, SLOT = 54.1, 85.4, 8.6
GAP = 0.15                       # clearance kept around every text, mm
SIZES = [(1.0, 0.15)]           # text height, stroke: the fab minimum (JLCPCB: text 1.0 mm, lines 0.15 mm)
MIN_LINE = 0.15                  # silkscreen line width the fabs print reliably


def box(b, grow=0.0):
    return (pcbnew.ToMM(b.GetX()) - grow, pcbnew.ToMM(b.GetY()) - grow,
            pcbnew.ToMM(b.GetRight()) + grow, pcbnew.ToMM(b.GetBottom()) + grow)


def hit(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def main():
    board = pcbnew.LoadBoard(str(PCB))
    fps = list(board.GetFootprints())
    silk = {pcbnew.F_SilkS: "F", pcbnew.B_SilkS: "B"}
    widened = 0
    for fp in fps:
        for item in fp.GraphicalItems():
            if item.GetLayer() in silk and item.GetClass() != "PCB_TEXT" and 0 < item.GetWidth() < pcbnew.FromMM(MIN_LINE):
                item.SetWidth(pcbnew.FromMM(MIN_LINE))
                widened += 1

    # Outline strokes the fab would clip anyway: off the board, on copper, or across
    # another part's silkscreen. Removed, so what DRC sees is what gets printed.
    # Filled shapes (pin-1 marks) are kept: they carry meaning.
    def stroke(item):
        return item.GetLayer() in silk and item.GetClass() == "PCB_SHAPE" and not item.IsSolidFill()

    def copper_of(item):
        return pcbnew.F_Cu if item.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Cu
    pads = [p for fp in fps for p in fp.Pads()]
    removed, doomed = [], []
    for fp in fps:
        for item in list(fp.GraphicalItems()):
            if not stroke(item):
                continue
            b = box(item.GetBoundingBox())
            shape = item.GetEffectiveShape()
            why = None
            if b[0] < 0 or b[1] < 0 or b[2] > W or b[3] > H:
                why = "off the board"
            elif any(p.IsOnLayer(copper_of(item)) and hit(b, box(p.GetBoundingBox()))
                     and shape.Collide(p.GetEffectiveShape(copper_of(item)), 0) for p in pads):
                why = "on copper"
            else:
                for other in fps:
                    if other.GetReference() == fp.GetReference():
                        continue
                    for o in other.GraphicalItems():
                        if any(o.m_Uuid.AsString() == d.m_Uuid.AsString() for _, d in doomed):
                            continue           # already going: it blocks nothing
                        if (o.GetLayer() == item.GetLayer() and o.GetClass() == "PCB_SHAPE"
                                and hit(b, box(o.GetBoundingBox())) and shape.Collide(o.GetEffectiveShape(), 0)):
                            why = f"across {other.GetReference()}'s silkscreen"
                            break
                    if why:
                        break
            if why:
                doomed.append((fp, item))
                removed.append(f"{fp.GetReference()} ({why})")
    for fp, item in doomed:            # after the scan: removing while iterating breaks the bindings
        fp.Remove(item)
    obstacles = {"F": [], "B": []}
    for fp in fps:
        for pad in fp.Pads():
            # copper of a pad on one side blocks that side; through-holes block both
            sides = ["F", "B"] if pad.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else \
                    (["B"] if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else ["F"])
            for s in sides:
                obstacles[s].append(box(pad.GetBoundingBox(), GAP))
        for item in fp.GraphicalItems():
            if item.GetLayer() in silk and item.GetClass() != "PCB_TEXT":
                obstacles[silk[item.GetLayer()]].append(box(item.GetBoundingBox(), GAP))
    for item in board.GetDrawings():
        if item.GetLayer() in silk:
            obstacles[silk[item.GetLayer()]].append(box(item.GetBoundingBox(), GAP))

    # every part's body, for "never on top of a part"; and the bodies of LABELLED parts,
    # for "closest to its own part": a label just outside a ring of unlabelled capacitors
    # still reads as the chip's, since the capacitors carry no label to confuse it with
    bodies = {"F": [], "B": []}
    labelled = {"F": [], "B": []}
    for fp in fps:
        s = "B" if fp.IsFlipped() else "F"
        bodies[s].append((fp, box(fp.GetBoundingBox(False))))
        if fp.Reference().GetLayer() in silk and fp.Reference().IsVisible():
            labelled[s].append((fp, box(fp.GetBoundingBox(False))))

    def dist(a, b):
        dx = max(b[0] - a[2], a[0] - b[2], 0)
        dy = max(b[1] - a[3], a[1] - b[3], 0)
        return (dx * dx + dy * dy) ** 0.5

    def nearest(b, side):
        """The part a reader would think this label names: the closest body on that side."""
        return min(labelled[side], key=lambda fb: dist(b, fb[1]))[0]

    def on_body(b, side):
        return any(hit(b, fb[1]) for fb in bodies[side])

    def legal(b, side):
        if b[0] < 0.5 or b[1] < 0.5 or b[2] > W - 0.5 or b[3] > H - SLOT - 0.3:
            return False
        return not any(hit(b, o) for o in obstacles[side])

    # big parts first: they have the fewest good spots
    todo = [fp for fp in fps if fp.Reference().GetLayer() in silk and fp.Reference().IsVisible()]
    todo.sort(key=lambda fp: -box(fp.GetBoundingBox(False))[2] + box(fp.GetBoundingBox(False))[0])
    moved = shrunk = to_fab = 0
    fabbed = []
    for fp in todo:
        ref = fp.Reference()
        side = silk[ref.GetLayer()]
        cx0, cy0, cx1, cy1 = box(fp.GetBoundingBox(False))
        mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        done = False
        for size, stroke in SIZES:
            ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(size), pcbnew.FromMM(size)))
            ref.SetTextThickness(pcbnew.FromMM(stroke))
            for angle in (0, 90):
                ref.SetTextAngleDegrees(angle)
                ref.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(mx), pcbnew.FromMM(my)))
                tw, th = (lambda b: (b[2] - b[0], b[3] - b[1]))(box(ref.GetBoundingBox()))
                # beside the part, never on it: silkscreen under a part is hidden once it is soldered
                cands = [(mx, cy0 - th / 2 - GAP), (mx, cy1 + th / 2 + GAP),
                         (cx0 - tw / 2 - GAP, my), (cx1 + tw / 2 + GAP, my)]
                for step in (0.5, 1.0, 1.5, 2.0, 2.5):   # then slide along each side
                    cands += [(mx + step, cy0 - th / 2 - GAP), (mx - step, cy0 - th / 2 - GAP),
                              (mx + step, cy1 + th / 2 + GAP), (mx - step, cy1 + th / 2 + GAP),
                              (cx0 - tw / 2 - GAP, my + step), (cx0 - tw / 2 - GAP, my - step),
                              (cx1 + tw / 2 + GAP, my + step), (cx1 + tw / 2 + GAP, my - step)]
                # then further out, past a ring of small parts around the chip
                for out in (1.5, 3.0, 4.5):
                    for step in (0.0, 1.0, -1.0, 2.0, -2.0):
                        cands += [(mx + step, cy0 - th / 2 - GAP - out), (mx + step, cy1 + th / 2 + GAP + out),
                                  (cx0 - tw / 2 - GAP - out, my + step), (cx1 + tw / 2 + GAP + out, my + step)]
                for x, y in cands:
                    ref.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y)))
                    b = box(ref.GetBoundingBox(), GAP)
                    if legal(b, side) and nearest(b, side) is fp and not on_body(b, side):
                        obstacles[side].append(b)
                        done = True
                        moved += 1
                        shrunk += size < 1.0
                        break
                if done:
                    break
            if done:
                break
        if not done:
            ref.SetLayer(pcbnew.B_Fab if side == "B" else pcbnew.F_Fab)
            ref.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(0.8), pcbnew.FromMM(0.8)))
            to_fab += 1
            fabbed.append(fp.GetReference())
    board.Save(str(PCB))
    print(f"silkscreen: {widened} footprint lines widened to {MIN_LINE} mm")
    print(f"silkscreen: {len(removed)} footprint outline strokes removed: {', '.join(removed) or '-'}")
    print(f"silkscreen: {moved} references placed clear of everything ({shrunk} at a smaller size), "
          f"{to_fab} moved to the Fab layer: {', '.join(fabbed) or '-'}")


if __name__ == "__main__":
    main()
