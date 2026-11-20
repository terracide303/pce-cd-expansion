#!/usr/bin/env python3
"""Board checks KiCad's DRC does not make, for tools/fab_card.py. Prints one JSON line.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/fabcheck_card.py [board]

- vias_in_pads: vias whose hole touches an SMD pad. An open via there wicks
  solder from the joint; filling and capping costs extra at both fabs.
- via_sizes: every via size on the board (the card allows one: 0.45/0.2 mm).
- locked_ground: the pre-routed ground-finger copper is still there (tools/preroute_card.py).
- edge: the finger order matches the working HuCARD-repro card. Seen from F.Cu with the
  fingers at the bottom, pin 38 (+5 V) is leftmost and pin 1 rightmost, and pin 18 (the
  only ground) is the finger nearest the edge. Mirrored, the console's +5 V lands on a
  ground finger. Empty when correct.
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
    print(json.dumps({"vias_in_pads": sorted(set(in_pads)), "via_sizes": dict(sizes), "locked_ground": locked_gnd,
                      "edge": edge(b)}))


def edge(b):
    j = b.FindFootprintByReference("J101")
    if j is None:
        return ["no J101"]
    pads = {p.GetNumber(): p for p in j.Pads()}
    x = {n: p.GetPosition().x for n, p in pads.items()}
    nearest = max(pads.values(), key=lambda p: p.GetBoundingBox().GetBottom()).GetNumber()
    problems = []
    if j.IsFlipped() or any(not p.IsOnLayer(pcbnew.F_Cu) for p in pads.values()):
        problems.append("fingers not on F.Cu")
    if min(x, key=x.get) != "38" or max(x, key=x.get) != "1":
        problems.append(f"leftmost finger is {min(x, key=x.get)}, rightmost {max(x, key=x.get)} (want 38 and 1)")
    if pads["38"].GetNetname() != "+5V_CON" or pads["18"].GetNetname() != "GND":
        problems.append("pin 38 is not +5V_CON or pin 18 is not GND")
    if nearest != "18":
        problems.append(f"finger nearest the edge is {nearest}, want 18 (ground mates first)")
    return problems


if __name__ == "__main__":
    main()
