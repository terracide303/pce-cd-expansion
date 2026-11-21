#!/usr/bin/env python3
"""Copy the Icepi Zero's own routing into the card, for the circuit copied from it.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/copy_icepi_copper_card.py <icepi-zero.kicad_pcb>

Run after tools/place_card.py (and the other placement steps), before the router.

Why: the FPGA, SDRAM, flash and power block is placed exactly as on the Icepi
(place_card.py, pad-verified), so the Icepi's copper for that block fits it exactly.
Routing it again gave a worse result: the first full routes could not reach four
decoupling capacitors under the BGA, because the Icepi feeds the 1.1 V core from an
In2 island and vias beside those capacitors, which the router does not invent. And the
SDRAM is the timing-critical part; the Icepi's SDRAM routing is proven on hardware.

What is copied (transformed by the same rotation and shift as the block):
  - every track and via of a net that is IDENTICAL on both boards: the same pads, all on
    kept Icepi parts, and no other pad on our side;
  - for the power nets (GND, +3V3, +1V1, +2V5, PWR_FILTERED_2V5), the copper within 1 mm
    of a block part (the first version took only the copper under the FPGA, and the SDRAM's
    ground and 3.3 V pins were then left to the router); power track ends that lead to a
    dropped part are pruned;
  - the Icepi's +1V1 zones (the In2 island under the core, and its F/B pours).
All of it is locked, so the router keeps it. Then a DRC pass removes any copied item
that clashes with our own parts or copper, and the script prints what it removed.
"""
import collections, pathlib, re, sys, tempfile

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"
POWER = {"GND", "+3V3", "+1V1", "+2V5", "PWR_FILTERED_2V5"}
FM, ToMM = pcbnew.FromMM, pcbnew.ToMM


def load_without_fonts(path):
    t = re.sub(r'\(face "[^"]*"\)', "", pathlib.Path(path).read_text(encoding="utf-8"))
    tmp = pathlib.Path(tempfile.gettempdir()) / "icepi_nofont_copy.kicad_pcb"
    tmp.write_text(t, encoding="utf-8")
    return pcbnew.LoadBoard(str(tmp))


def main(icepi_path):
    b = pcbnew.LoadBoard(str(PCB))
    ice = load_without_fonts(icepi_path)
    ours = {f.GetReference(): f for f in b.GetFootprints()}
    theirs = {f.GetReference(): f for f in ice.GetFootprints()}

    # the block transform, from two parts, checked on every kept part's pads
    def pos(f):
        p = f.GetPosition(); return ToMM(p.x), ToMM(p.y)
    (ix, iy), (cx, cy) = pos(theirs["U1"]), pos(ours["U1"])
    dx, dy = cx - (-iy), cy - ix

    def T(x, y):
        return -y + dx, x + dy
    # the block: parts whose pads all sit where the transform puts the Icepi's (place_card
    # moves a few, e.g. the J5 group, on their own; their nets are not copied)
    block = []
    for r in (r for r in theirs if r in ours):
        a = {p.GetNumber(): pos(p) for p in ours[r].Pads()}
        err = max([abs(T(*pos(p))[0] - a[p.GetNumber()][0]) + abs(T(*pos(p))[1] - a[p.GetNumber()][1])
                   for p in theirs[r].Pads() if p.GetNumber() in a] or [99])
        if err < 0.01:
            block.append(r)
    if "U1" not in block or "U11" not in block:
        sys.exit("the FPGA/SDRAM are not where the block transform puts them: run place_card.py first")
    print(f"block: {len(block)} parts at the Icepi's positions (transform checked pad by pad)")
    block = set(block)

    # net map: an Icepi net is copied when it is the same pad set on both boards
    ipads, opads = collections.defaultdict(set), collections.defaultdict(set)
    for f in ice.GetFootprints():
        for p in f.Pads():
            if p.GetNetname():
                ipads[p.GetNetname()].add((f.GetReference(), p.GetNumber()))
    for f in b.GetFootprints():
        for p in f.Pads():
            if p.GetNetname():
                opads[p.GetNetname()].add((f.GetReference(), p.GetNumber()))
    padnet = {(f.GetReference(), p.GetNumber()): p.GetNetname() for f in b.GetFootprints() for p in f.Pads()}
    same, power = {}, {}
    for n, s in ipads.items():
        inb = {k for k in s if k[0] in block}
        targets = {padnet.get(k) for k in inb}
        if len(targets) == 1 and next(iter(targets)) in POWER:
            power[n] = targets.pop()                 # power: the pads inside the block agree
            continue
        if inb != s:
            continue
        if len(targets) != 1 or None in targets:
            continue
        t = targets.pop()
        if t in POWER:
            power[n] = t
        elif opads[t] == s:
            same[n] = t
    print(f"identical signal nets: {len(same)}; power nets copied under the FPGA: {sorted(set(power.values()))}")

    # power copper is copied where the block is: within 1 mm of a block part's courtyard
    boxes = []
    for r in block:
        for lay in (pcbnew.F_CrtYd, pcbnew.B_CrtYd):
            c = ours[r].GetCourtyard(lay)
            if c.OutlineCount():
                bb = c.BBox(); bb.Inflate(FM(1.0)); boxes.append(bb)

    def inside(x, y):
        q = pcbnew.VECTOR2I(FM(x), FM(y))
        return any(bb.Contains(q) for bb in boxes)

    added = []
    for t in ice.GetTracks():
        n = t.GetNetname()
        if n not in same and n not in power:
            continue
        net = b.FindNet(same.get(n) or power[n])
        if t.GetClass() == "PCB_VIA":
            x, y = T(*pos(t))
            if n in power and not inside(x, y):
                continue
            v = pcbnew.PCB_VIA(b)
            v.SetPosition(pcbnew.VECTOR2I(FM(x), FM(y)))
            v.SetWidth(t.GetWidth(pcbnew.F_Cu)); v.SetDrill(t.GetDrillValue())
            item = v
        else:
            (x0, y0), (x1, y1) = T(ToMM(t.GetStart().x), ToMM(t.GetStart().y)), T(ToMM(t.GetEnd().x), ToMM(t.GetEnd().y))
            if n in power and not (inside(x0, y0) and inside(x1, y1)):
                continue
            if t.GetClass() == "PCB_ARC":
                m = t.GetMid(); xm, ym = T(ToMM(m.x), ToMM(m.y))
                item = pcbnew.PCB_ARC(b)
                item.SetMid(pcbnew.VECTOR2I(FM(xm), FM(ym)))
            else:
                item = pcbnew.PCB_TRACK(b)
            item.SetStart(pcbnew.VECTOR2I(FM(x0), FM(y0))); item.SetEnd(pcbnew.VECTOR2I(FM(x1), FM(y1)))
            item.SetWidth(t.GetWidth()); item.SetLayer(t.GetLayer())
        item.SetNet(net); item.SetLocked(True)
        b.Add(item); added.append(item)
    print(f"copied {len(added)} tracks and vias")

    # power copper that now leads nowhere (it went to a part the card dropped): prune
    # track ends that touch no pad, via or other track of their net, until none is left
    def prune():
        pw = {i.m_Uuid.AsString(): i for i in added if i.GetNetname() in POWER}
        gone = set()
        while True:
            live = [i for k, i in pw.items() if k not in gone]
            pads_by_net = collections.defaultdict(list)
            for f in b.GetFootprints():
                for p in f.Pads():
                    pads_by_net[p.GetNetCode()].append(p)
            items = [t for t in b.GetTracks() if t.m_Uuid.AsString() not in gone]
            dead = []
            for i in live:
                if i.GetClass() == "PCB_VIA":
                    continue
                for e in (i.GetStart(), i.GetEnd()):
                    ok = any(p.IsOnLayer(i.GetLayer()) and p.HitTest(e) for p in pads_by_net[i.GetNetCode()])
                    if not ok:
                        for o in items:
                            if o.m_Uuid.AsString() == i.m_Uuid.AsString() or o.GetNetCode() != i.GetNetCode():
                                continue
                            if o.GetClass() == "PCB_VIA":
                                if (o.GetPosition() - e).EuclideanNorm() <= o.GetWidth(pcbnew.F_Cu) // 2:
                                    ok = True; break
                            elif o.GetLayer() == i.GetLayer() and o.GetEffectiveShape().Collide(e, i.GetWidth() // 2):
                                ok = True; break
                    if not ok:
                        dead.append(i); break
            if not dead:
                return gone
            for i in dead:
                gone.add(i.m_Uuid.AsString())
    # copied vias in an SMD pad the card does not accept (tools/fabcheck_card.py allows only
    # the listed Icepi pads under the BGA, exposed thermal pads and bare test points), and
    # vias closer to the board edge than the fab's 0.3 mm: removed; the router reconnects
    sys.path.insert(0, str(ROOT / "tools"))
    from fabcheck_card import via_pad_allowed
    edge = b.GetBoardEdgesBoundingBox()
    edge.Inflate(-FM(0.05))                         # the box includes half the outline stroke
    smd = [(f, p) for f in b.GetFootprints() for p in f.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    drop = []
    for i in added:
        if i.GetClass() != "PCB_VIA":
            continue
        c, r = i.GetPosition(), i.GetDrillValue() // 2
        for f, p in smd:
            L = pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu
            if p.GetEffectiveShape(L).Collide(c, r) and not via_pad_allowed(f, p):
                drop.append((i, f"{f.GetReference()}.{p.GetNumber()}")); break
        else:
            m = i.GetWidth(pcbnew.F_Cu) // 2 + FM(0.3)
            if min(c.x - edge.GetLeft(), edge.GetRight() - c.x, c.y - edge.GetTop(), edge.GetBottom() - c.y) < m:
                drop.append((i, "edge"))
    for i, why in drop:
        b.Remove(i); added.remove(i)
    if drop:
        print(f"removed {len(drop)} copied vias: {sorted(w for _, w in drop)}")
    gone = prune()
    for i in list(added):
        if i.m_Uuid.AsString() in gone:
            b.Remove(i); added.remove(i)
    print(f"pruned {len(gone)} power track pieces that led to dropped parts")

    nz = 0
    for z in ice.Zones():
        if z.GetIsRuleArea() or z.GetNetname() != "+1V1":
            continue
        q = pcbnew.ZONE(b)
        q.SetLayerSet(z.GetLayerSet()); q.SetNet(b.FindNet("+1V1"))
        q.SetLocalClearance(z.GetLocalClearance() or FM(0.1)); q.SetMinThickness(z.GetMinThickness())
        q.SetPadConnection(z.GetPadConnection()); q.SetAssignedPriority(50 + z.GetAssignedPriority())
        q.SetZoneName("Icepi +1V1 (copied)"); q.SetLocked(True)
        o, no = z.Outline(), q.Outline()
        no.NewOutline()
        for i in range(o.COutline(0).PointCount()):
            p = o.COutline(0).CPoint(i); x, y = T(ToMM(p.x), ToMM(p.y)); no.Append(FM(x), FM(y))
        b.Add(q); nz += 1
    print(f"copied {nz} +1V1 zones")

    # clashes with our own parts and copper: copied copper must not touch another net
    pads = [(f.GetReference(), p) for f in b.GetFootprints() for p in f.Pads()]
    ids = {it.m_Uuid.AsString() for it in added}
    others = [t for t in b.GetTracks() if t.m_Uuid.AsString() not in ids]
    gap = FM(0.1)
    removed = collections.Counter()
    keep = []
    for it in added:
        lay = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu] if it.GetClass() == "PCB_VIA" else [it.GetLayer()]
        bad = False
        for L in lay:
            sh = it.GetEffectiveShape(L)
            for ref, p in pads:
                if p.GetNetCode() != it.GetNetCode() and p.IsOnLayer(L) and p.GetEffectiveShape(L).Collide(sh, gap):
                    bad = True; break
            if bad:
                break
            for o in others:
                if o.GetNetCode() != it.GetNetCode() and o.IsOnLayer(L) and o.GetEffectiveShape(L).Collide(sh, gap):
                    bad = True; break
            if bad:
                break
        if bad:
            removed[it.GetNetname()] += 1
        else:
            keep.append(it)
    kept_ids = {it.m_Uuid.AsString() for it in keep}
    for it in added:
        if it.m_Uuid.AsString() not in kept_ids:
            b.Remove(it)
    if removed:
        print(f"removed {sum(removed.values())} copied items that clash with the card's own copper/pads: {dict(removed)}")
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    b.Save(str(PCB))
    print(f"saved {PCB.relative_to(ROOT)}: {len(keep)} copied items kept, locked")


if __name__ == "__main__":
    main(sys.argv[1])
