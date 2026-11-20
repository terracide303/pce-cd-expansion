#!/usr/bin/env python3
"""Insert the polyfuse F101 into an already routed card, without routing it again.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/fuse_card.py IN.kicad_pcb OUT.kicad_pcb

F101 was added after the full route (owner decision, docs/REVIEW-2026-11-20.md). On the
routed board the 5 V run from finger 38 has no branch until the data translator, so the
fuse goes on the back, behind U103 near the finger (B.Cu at 4.0, 67.0: a survey of the
routed board found no copper there; tools/place_card.py uses the same spot). This script:
  1. moves finger 38 to the new net +5V_SLOT and places F101 (+5V_SLOT -> +5V_CON),
     linked to its schematic symbol;
  2. removes the unbranched +5V_CON chain from finger 38 up to its first branch;
  3. removes other nets' copper under F101 and prints those nets.
Then route the printed nets (and +5V_SLOT, +5V_CON) with the router's route.py.
"""
import collections, sys

import pcbnew

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from make_card_pcb import netlist, load_fp, mm  # noqa: E402

AT, ROT, BACK = (4.0, 67.0), 0, True
ToMM = pcbnew.ToMM


def key(p):
    return (round(ToMM(p.x), 3), round(ToMM(p.y), 3))


def main(src, dst):
    b = pcbnew.LoadBoard(src)
    pins, paths = netlist()
    if pins.get(("J101", "38")) != "+5V_SLOT" or pins.get(("F101", "2")) != "+5V_CON":
        sys.exit("the schematic has no F101 between +5V_SLOT and +5V_CON: run tools/gen_card.py first")
    if b.FindFootprintByReference("F101"):
        sys.exit("F101 is already on this board")
    con = b.FindNet("+5V_CON")
    slot = pcbnew.NETINFO_ITEM(b, "+5V_SLOT")
    b.Add(slot)

    # 2. the chain from finger 38: walk track ends until a node has a branch or a pad
    j = b.FindFootprintByReference("J101")
    p38 = next(p for p in j.Pads() if p.GetNumber() == "38")
    segs = collections.defaultdict(list)            # node -> track segments ending there
    vias = {}                                        # node -> via (a via joins the layers at a node)
    for t in b.GetTracks():
        if t.GetNetCode() != con.GetNetCode():
            continue
        if t.GetClass() == "PCB_VIA":
            vias[key(t.GetPosition())] = t

    def snap(pt):                                    # a track may end anywhere on a via's pad
        for v in vias.values():
            if (pt - v.GetPosition()).EuclideanNorm() <= v.GetWidth(pcbnew.F_Cu) // 2:
                return key(v.GetPosition())
        return key(pt)
    for t in b.GetTracks():
        if t.GetNetCode() == con.GetNetCode() and t.GetClass() != "PCB_VIA":
            segs[snap(t.GetStart())].append(t); segs[snap(t.GetEnd())].append(t)
    pads = [p for f in b.GetFootprints() for p in f.Pads()
            if p.GetNetCode() == con.GetNetCode() and f.GetReference() != "J101"]
    padpts = {n for n in segs if any(p.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(n[0]), pcbnew.FromMM(n[1]))) for p in pads)}
    start = [n for n in segs if p38.HitTest(pcbnew.VECTOR2I(pcbnew.FromMM(n[0]), pcbnew.FromMM(n[1])))]
    if len(start) != 1:
        sys.exit(f"finger 38 has {len(start)} track ends on it, expected 1")
    chain, node, seen = [], start[0], set()
    while True:
        nxt = [t for t in segs[node] if id(t) not in seen]
        if len(nxt) != 1 or node in padpts or (seen and len(segs[node]) != 2):
            break
        t = nxt[0]; seen.add(id(t)); chain.append(t)
        node = snap(t.GetEnd()) if snap(t.GetStart()) == node else snap(t.GetStart())
        if node in vias and len(segs[node]) == 2 and node not in padpts:
            chain.append(vias[node])
    print(f"removing {len(chain)} items of the finger-38 chain, stopped at {node}")
    for t in chain:
        b.Remove(t)
    p38.SetNet(slot)

    # 1. the fuse
    part = next(pp for pp in __import__("design").PARTS if pp["ref"] == "F101")
    fp = load_fp(part["fp"])
    fp.SetReference("F101"); fp.SetValue(part["value"])
    fp.SetField("LCSC", part.get("lcsc", "")); fp.GetField("LCSC").SetVisible(False)
    fp.SetPath(pcbnew.KIID_PATH(paths["F101"]))
    fp.SetOrientationDegrees(ROT); fp.SetPosition(mm(*AT))
    b.Add(fp)
    if BACK:                                         # flip once it is on the board (crashes before)
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for pad in fp.Pads():
        pad.SetNet(slot if pins[("F101", pad.GetNumber())] == "+5V_SLOT" else con)

    # 3. other copper on the fuse's side under it (courtyard grown by 0.2 mm)
    box = fp.GetCourtyard(pcbnew.B_CrtYd if BACK else pcbnew.F_CrtYd).BBox()
    box.Inflate(pcbnew.FromMM(0.2))
    hit, nets = [], set()
    for t in b.GetTracks():
        same_side = t.GetClass() == "PCB_VIA" or t.GetLayer() == (pcbnew.B_Cu if BACK else pcbnew.F_Cu)
        if same_side and t.GetBoundingBox().Intersects(box):
            hit.append(t); nets.add(t.GetNetname())
    for t in hit:
        b.Remove(t)
    print(f"removed {len(hit)} items under F101; nets to route again:")
    print(" ".join(sorted(nets | {"+5V_SLOT", "+5V_CON"})))
    b.Save(dst)


if __name__ == "__main__":
    main(*sys.argv[1:3])
