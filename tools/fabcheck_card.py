#!/usr/bin/env python3
"""Board checks KiCad's DRC does not make, for tools/fab_card.py. Prints one JSON line.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/fabcheck_card.py [board]

- vias_in_pads: vias whose hole touches an SMD pad. An open via there wicks
  solder from the joint; filling and capping costs extra at both fabs.
- via_sizes: every via size on the board (the card allows one: 0.45/0.2 mm).
- locked_ground: the pre-routed ground-finger copper is still there (tools/preroute_card.py).
"""
import collections, json, pathlib, sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "hw" / "card" / "pce_card.kicad_pcb"


def main():
    b = pcbnew.LoadBoard(str(PCB))
    mm = pcbnew.ToMM
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    sizes = collections.Counter(f"{mm(v.GetWidth(pcbnew.F_Cu)):g}/{mm(v.GetDrillValue()):g}" for v in vias)
    in_pads = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
                continue
            layer = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            shape, box = p.GetEffectiveShape(layer), p.GetBoundingBox()
            for v in vias:
                r = v.GetDrillValue() // 2
                c = v.GetPosition()
                near = box.GetX() - r <= c.x <= box.GetRight() + r and box.GetY() - r <= c.y <= box.GetBottom() + r
                if near and shape.Collide(c, r):
                    in_pads.append(f"{fp.GetReference()}.{p.GetNumber()}")
    locked_gnd = sum(1 for t in b.GetTracks() if t.IsLocked() and t.GetNetname() == "GND")
    print(json.dumps({"vias_in_pads": sorted(set(in_pads)), "via_sizes": dict(sizes), "locked_ground": locked_gnd}))


if __name__ == "__main__":
    main()
