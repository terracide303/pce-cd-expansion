#!/usr/bin/env python3
"""Copper laid by rule before the router runs, locked so the router routes around it.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/preroute_card.py

Run after tools/place_card.py (and the silkscreen steps), before routing.

THE GROUND FINGER. Pin 18 is the HuCard connector's only ground (tools/hucard_bus.py),
so every return current of the card goes through it. The router treated it as one
more pad: on the first full run it was the last net left open, boxed in by bus
lines crossing over it inside the slot zone, where no via is allowed. Here it gets
a 0.5 mm track straight up out of the slot zone and two vias into the In1 GND plane,
locked, before any signal is routed.

Re-runnable: removes its own previous copper first (locked GND copper in the
finger column).
"""
import pathlib

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
H, SLOT = 85.4, 8.6
GND_FINGER = "18"
TRACK_W, VIA = 0.5, (0.45, 0.2)


def V(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    board = pcbnew.LoadBoard(str(PCB))
    pad = next(p for p in board.FindFootprintByReference("J101").Pads() if p.GetNumber() == GND_FINGER)
    gnd, x = pad.GetNet(), pcbnew.ToMM(pad.GetPosition().x)
    top = pcbnew.ToMM(pad.GetBoundingBox().GetY())
    via_y = H - SLOT - 0.5                       # the via's copper ends 0.275 mm before the no-via zone

    # a previous run's copper: locked GND items in this finger's column
    old = [t for t in board.GetTracks() if t.GetNetname() == gnd.GetNetname() and t.IsLocked()
           and abs(pcbnew.ToMM(t.GetBoundingBox().GetCenter().x) - x) < 1.0
           and pcbnew.ToMM(t.GetBoundingBox().GetBottom()) > via_y - 1.5]
    for t in old:                                # after the scan: removing while iterating breaks the bindings
        board.Remove(t)

    def track(x0, y0, x1, y1, w):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(V(x0, y0)); t.SetEnd(V(x1, y1)); t.SetWidth(pcbnew.FromMM(w))
        t.SetLayer(pcbnew.F_Cu); t.SetNet(gnd); t.SetLocked(True)
        board.Add(t)

    def via(x0, y0):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(V(x0, y0)); v.SetWidth(pcbnew.FromMM(VIA[0])); v.SetDrill(pcbnew.FromMM(VIA[1]))
        v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
        v.SetNet(gnd); v.SetLocked(True)
        board.Add(v)

    track(x, top + 0.6, x, via_y, TRACK_W)       # from inside the finger, straight up
    via(x, via_y)
    track(x, via_y, x + 0.6, via_y - 0.6, 0.4)   # a second via beside the first, away from
    via(x + 0.6, via_y - 0.6)                    # the series resistors on the left
    board.Save(str(PCB))
    print(f"ground finger {GND_FINGER} (x {x:.3f}): {TRACK_W} mm track to y {via_y:.2f}, 2 vias into In1, "
          f"locked (replaced {len(old)} old items)")


if __name__ == "__main__":
    main()
