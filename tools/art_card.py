#!/usr/bin/env python3
"""Silkscreen artwork: the card's name, the maker, a CD and speed stripes.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/art_card.py

Original artwork in a retro console style (not NEC's PC Engine logo, which is a
trademark). KiCad's built-in stroke font only, so the board needs no installed
fonts and the gerbers come out the same on every machine. Everything is put in a
group called "art" on the silkscreen; running again replaces it.

Back: the big panel in the free area beside the FPGA core. Front: a one-line credit.
Run after tools/silk_card.py, then look at the render.
"""
import math, pathlib

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
W = 54.1


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    board = pcbnew.LoadBoard(str(PCB))
    # remove a previous run's artwork: ungroup first, then delete the items
    # (deleting items while they are still in the group crashes KiCad's Python)
    old_items = []
    for g in list(board.Groups()):
        if g.GetName() == "art":
            old_items += list(g.GetItems())
            g.RemoveAll()
            board.Remove(g)
    for item in old_items:
        board.Remove(item)
    group = pcbnew.PCB_GROUP(board)
    group.SetName("art")
    board.Add(group)

    def add(item):
        board.Add(item)
        group.AddItem(item)

    # ---- back panel. Designed as seen FROM THE BACK, where left and right swap:
    # a point at view-x v lands at board x = W - v. Texts are mirrored so they read.
    back = pcbnew.B_SilkS

    def bx(v):
        return W - v

    def text(s, v, y, h, stroke, layer=back, italic=True, angle=0, mirror=True):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetLayer(layer)
        t.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(h), pcbnew.FromMM(h)))
        t.SetTextThickness(pcbnew.FromMM(stroke))
        t.SetItalic(italic)
        t.SetMirrored(mirror)
        t.SetTextAngleDegrees(angle)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        t.SetPosition(mm(bx(v) if layer == back else v, y))
        add(t)

    def circle(v, y, r, width, filled=False):
        c = pcbnew.PCB_SHAPE(board)
        c.SetShape(pcbnew.SHAPE_T_CIRCLE)
        c.SetCenter(mm(bx(v), y))
        c.SetEnd(mm(bx(v) + r, y))
        c.SetWidth(pcbnew.FromMM(width))
        c.SetFilled(filled)
        c.SetLayer(back)
        add(c)

    def arc(v, y, r, a0, a1, width):
        a = pcbnew.PCB_SHAPE(board)
        a.SetShape(pcbnew.SHAPE_T_ARC)
        pts = [(v + r * math.cos(math.radians(t)), y - r * math.sin(math.radians(t))) for t in (a0, (a0 + a1) / 2, a1)]
        a.SetArcGeometry(mm(bx(pts[0][0]), pts[0][1]), mm(bx(pts[1][0]), pts[1][1]), mm(bx(pts[2][0]), pts[2][1]))
        a.SetWidth(pcbnew.FromMM(width))
        a.SetLayer(back)
        add(a)

    def poly(points):
        p = pcbnew.PCB_SHAPE(board)
        p.SetShape(pcbnew.SHAPE_T_POLY)
        p.SetPolyPoints([mm(bx(v), y) for v, y in points])
        p.SetFilled(True)
        p.SetWidth(pcbnew.FromMM(0.1))
        p.SetLayer(back)
        add(p)

    # panel: view-x 3..29 (the board's free right column seen from the back), y 18..74
    cx = 15.5
    # the disc
    circle(cx, 30.0, 8.6, 0.45)
    circle(cx, 30.0, 2.6, 0.7)
    circle(cx, 30.0, 0.9, 0.3)
    for r, a0, a1 in [(4.4, 25, 75), (6.0, 30, 70), (7.3, 35, 62), (4.4, 205, 255), (6.0, 210, 250)]:
        arc(cx, 30.0, r, a0, a1, 0.35)
    # speed stripes, leaning like the lettering, longest first
    y = 41.2
    for i, length in enumerate([22.0, 18.0, 14.0, 10.0]):
        x0 = cx - 11.0 + i * 1.2
        h, lean = 0.7, 0.5
        poly([(x0 + lean, y), (x0 + length + lean, y), (x0 + length, y + h), (x0, y + h)])
        y += 1.25
    # the name
    text("PCE", cx, 51.5, 6.5, 1.1)
    text("CD EXPANSION", cx, 57.0, 2.2, 0.35)
    # underline bar
    poly([(cx - 11.4, 59.4), (cx + 11.6, 59.4), (cx + 11.4, 59.9), (cx - 11.6, 59.9)])
    text("TERRACIDE303", cx, 63.2, 2.4, 0.4)
    text("HuCARD  FPGA  CD-ROM²", cx, 67.0, 1.1, 0.18, italic=False)
    text("rev 0.1  ·  2026", cx, 69.2, 1.0, 0.15, italic=False)

    # ---- front: a one-line credit in the empty bus channel beside the SDRAM
    text("TERRACIDE303 · PCE CD", 38.0, 56.0, 1.0, 0.15, layer=pcbnew.F_SilkS, mirror=False)

    board.Save(str(PCB))
    print(f"art: {len(list(group.GetItems()))} silkscreen items in group 'art' (back panel + front credit)")


if __name__ == "__main__":
    main()
