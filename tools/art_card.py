#!/usr/bin/env python3
"""Silkscreen artwork on the FRONT: what the card is, and who made it.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/art_card.py

    PC Engine / TurboGrafx
    CD-ROM²            (the 2 is a separate, smaller, raised text)
    TERRACIDE303
    rev 0.1 · 2026

Placed in the free strip between the SDRAM and the test points. The console names
are a compatibility statement, not a logo. KiCad's built-in stroke font only, so the
board needs no installed fonts and the gerbers come out the same on every machine.
Everything is in a group called "art"; running again replaces it. Run after
tools/silk_card.py, then look at the render and run DRC.
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

    front = pcbnew.F_SilkS

    def text(s, x, y, h, stroke, italic=False, bold_stroke=None):
        tx = pcbnew.PCB_TEXT(board)
        tx.SetText(s)
        tx.SetLayer(front)
        tx.SetTextSize(pcbnew.VECTOR2I(pcbnew.FromMM(h), pcbnew.FromMM(h)))
        tx.SetTextThickness(pcbnew.FromMM(stroke))
        tx.SetItalic(italic)
        tx.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
        tx.SetPosition(mm(x, y))
        add(tx)
        return tx

    def line(x0, y0, x1, y1, w):
        sh = pcbnew.PCB_SHAPE(board)
        sh.SetShape(pcbnew.SHAPE_T_SEGMENT)
        sh.SetStart(mm(x0, y0))
        sh.SetEnd(mm(x1, y1))
        sh.SetWidth(pcbnew.FromMM(w))
        sh.SetLayer(front)
        add(sh)

    cx = 36.6                                  # centre of the free strip, mm
    text("PC Engine / TurboGrafx", cx, 53.2, 1.0, 0.15)
    rom = text("CD-ROM", cx - 0.7, 56.4, 2.4, 0.38, italic=True)
    # the small raised 2: just right of CD-ROM's last letter, aligned to its top
    bb = rom.GetBoundingBox()
    right, top = pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetY())
    two = text("2", 0, 0, 1.2, 0.2, italic=True)
    two.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
    two.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
    two.SetPosition(mm(right + 0.05, top + 0.1))
    line(cx - 8.5, 58.6, cx + 8.5, 58.6, 0.2)
    text("TERRACIDE303", cx, 60.6, 1.4, 0.22)
    text("rev 0.1 · 2026", cx, 62.6, 1.0, 0.15)    # 1.0 mm / 0.15 mm: the fab minimum

    board.Save(str(PCB))
    print(f"art: {len(list(group.GetItems()))} silkscreen items in group 'art' (front)")


if __name__ == "__main__":
    main()
