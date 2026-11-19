#!/usr/bin/env python3
"""Create the card's PCB: HuCard outline, fingers on the edge, every footprint and net.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/make_card_pcb.py

Runs in KiCad's own Python (pcbnew). Reads KiCad's netlist of hw/card/pce_card.kicad_sch,
so the board carries exactly the schematic's connections, and links each footprint
to its symbol so "Update PCB from Schematic" (F8) recognises them.

PLACED HERE: the outline (54.1 x 85.4 mm, a HuCard, docs/CARD.md) and the card edge
J101, whose position is fixed by the slot. A keep-out marks the 8.6 mm the slot
swallows: no vias, no parts there.
NOT PLACED, ON PURPOSE: everything else is staged beside the board in groups by
sheet. Placement is human (PCB HERO's rule), and with a 0.8 mm BGA the FPGA, SDRAM
and regulators should follow the Icepi Zero's proven arrangement.

Also writes the .kicad_dru, the project rules and board.json for PCB HERO's checker.
Stack-up is the Icepi Zero v1.4's (4-layer, 1.6 mm: JLCPCB JLC04161H-7628 -- 7628 prepreg 0.2104 mm, core 1.065 mm); rules are what JLCPCB and
PCBWay both make at standard price (FAB below).
"""
import json, os, pathlib, re, subprocess, sys, tempfile

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "hw" / "card"
SCH = OUT / "pce_card.kicad_sch"
PCB = OUT / "pce_card.kicad_pcb"
ICEPI_PCB = None   # stack-up text is embedded below, copied from the Icepi's .kicad_pcb
KICAD_FP = pathlib.Path(os.environ.get("KICAD_FOOTPRINT_DIR", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints"))
KICAD_CLI = os.environ.get("KICAD_CLI", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe")
sys.path.insert(0, str(OUT))
import design  # noqa: E402

LIBS = {"pce_card": OUT / "pce_card.pretty", "icepi-lib": OUT / "reference" / "icepi-zero-v1.4" / "icepi-lib.pretty"}
W, H = 54.1, 85.4                   # HuCard outline; the finger edge is y = H
SLOT = 8.6                          # how deep the slot takes the card

# What both JLCPCB and PCBWay make on 4 layers at STANDARD price (checked on their
# capability pages, 2026-11-19): JLC 0.09/0.09 mm tracks, PCBWay 0.1/0.1 mm (4 mil);
# vias with a 0.2 mm hole and 0.45 mm pad (a 0.15 mm hole costs extra at both);
# via hole to track 0.2 mm (JLC); copper to a routed edge 0.2-0.25 mm; silkscreen
# lines >= 0.15 mm and text >= 1.0 mm (JLC; PCBWay 0.8). We hold the stricter of each.
FAB = {"name": "JLCPCB or PCBWay, 4-layer standard (no surcharge)", "track": 0.1, "clearance": 0.1,
       "via_hole": 0.2, "via_dia": 0.45, "hole_to_hole": 0.25, "edge": 0.3, "hole_clearance": 0.2,
       "silk_line": 0.15, "silk_text": 1.0}
DESIGN = {"track": 0.1, "clearance": 0.1, "default_track": 0.2, "via_dia": 0.45, "via_drill": 0.2,
          "bga_via_dia": 0.45, "bga_via_drill": 0.2, "edge": 0.3, "power_track": 0.3}

GROUP_ORDER = ["bus", "power", "fpga", "flash", "sdram", "sd", "usb_jtag", "companion", "audio"]


def netlist():
    """{(ref, pin): net} and {ref: footprint path} from KiCad's own netlist export."""
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "n.net"
        subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(SCH)],
                       capture_output=True, check=True)
        text = out.read_text(encoding="utf-8")
    pins, paths = {}, {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)(.*?)(?=\(comp\s+\(ref|\(libparts|\Z)', text, re.S):
        ref, body = m.group(1), m.group(2)
        sheet = re.search(r'\(sheetpath\s*\(names "[^"]*"\)\s*\(tstamps "([^"]*)"\)', body).group(1)
        stamp = re.search(r'\(tstamps "([^"]+)"', body[body.find(")", body.find("(sheetpath")):]).group(1)
        paths[ref] = sheet + stamp.split()[0]
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', text, re.S):
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins[(ref, pin)] = m.group(1)
    return pins, paths


def load_fp(fpid):
    lib, name = fpid.split(":", 1)
    fp = pcbnew.FootprintLoad(str(LIBS.get(lib, KICAD_FP / f"{lib}.pretty")), name)
    if fp is None:
        sys.exit(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    pins, paths = netlist()
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(4)
    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(board, name)
            board.Add(nets[name])
        return nets[name]

    # staging: one column per sheet, to the right of the board
    parts = [p for p in design.PARTS if not p["ref"].startswith("#")]
    col_x = {g: W + 20 + i * 32 for i, g in enumerate(GROUP_ORDER)}
    col_y = {g: 0.0 for g in GROUP_ORDER}
    for g in GROUP_ORDER:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(g)
        t.SetPosition(mm(col_x[g], -8))
        t.SetLayer(pcbnew.Cmts_User)
        board.Add(t)

    for p in parts:
        ref = p["ref"]
        fp = load_fp(p["fp"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        fp.SetField("LCSC", p.get("lcsc", ""))          # schematic parity: same fields on both sides
        fp.GetField("LCSC").SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(paths[ref]))
        if ref == "J101":
            fp.SetPosition(mm(W / 2, H))       # fingers on the edge, fixed by the slot
            fp.SetLocked(True)
        else:
            g = p["sheet"] if ref != "U1" else "fpga"
            bb = fp.GetBoundingBox(True)                   # include the courtyard
            h = pcbnew.ToMM(bb.GetHeight())
            fp.SetPosition(mm(col_x[g], col_y[g] + h / 2))
            col_y[g] += h + 4
        board.Add(fp)
        for pad in fp.Pads():
            name = pins.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net(name))

    def seg(a, b, c, d, layer, width=0.1):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(mm(a, b)); s.SetEnd(mm(c, d))
        s.SetLayer(layer); s.SetWidth(pcbnew.FromMM(width))
        board.Add(s)

    for (a, b, c, d) in [(0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)]:
        seg(a, b, c, d, pcbnew.Edge_Cuts)

    # keep-out: the part of the card inside the slot. Tracks may run to the fingers;
    # no vias, no footprints, no pours there (the slot's contacts wipe that area).
    zone = pcbnew.ZONE(board)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowVias(True)
    zone.SetDoNotAllowFootprints(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(False)
    zone.SetDoNotAllowPads(False)
    zone.SetZoneName("slot insertion: no vias, parts or pours")
    ls = pcbnew.LSET()
    for L in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
        ls.AddLayer(L)
    zone.SetLayerSet(ls)
    o = zone.Outline()
    o.NewOutline()
    for x, y in [(0, H - SLOT), (W, H - SLOT), (W, H), (0, H)]:
        o.Append(pcbnew.FromMM(x), pcbnew.FromMM(y))
    board.Add(zone)

    for text, y in [("PCE CD expansion card - HuCard 54.1 x 85.4 mm, 1.6 mm, 4 layers, ENIG, 45 deg bevel on the finger edge", H + 6),
                    ("Placement is human. Follow the Icepi Zero v1.4 layout for FPGA, SDRAM, flash and regulators.", H + 10),
                    ("Bus: U1 right side (A0-A19, D0-D7, strobes) -> channel right of the SDRAM -> translator row.", H + 14)]:
        t = pcbnew.PCB_TEXT(board)
        t.SetText(text)
        t.SetPosition(mm(0, y))
        t.SetLayer(pcbnew.Cmts_User)
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        board.Add(t)

    ds = board.GetDesignSettings()
    ds.SetBoardThickness(pcbnew.FromMM(1.6))
    ds.m_TrackMinWidth = pcbnew.FromMM(DESIGN["track"])
    ds.m_MinClearance = pcbnew.FromMM(DESIGN["clearance"])
    ds.m_HoleClearance = pcbnew.FromMM(0.18)          # see write_rules(): the USB4105 footprint
    pcbnew.SaveBoard(str(PCB), board)
    add_stackup()
    print(f"wrote {PCB.relative_to(ROOT).as_posix()}: {len(parts)} footprints, {len(nets)} nets; "
          f"J101 fixed on the edge, the rest staged (not placed)")
    write_rules()


STACKUP = """\t\t(stackup
\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))
\t\t\t(layer "F.Paste" (type "Top Solder Paste"))
\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
\t\t\t(layer "F.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 1" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "In1.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 2" (type "core") (thickness 1.065) (material "FR4") (epsilon_r 4.5) (loss_tangent 0.02))
\t\t\t(layer "In2.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "dielectric 3" (type "prepreg") (thickness 0.2104) (material "FR4") (epsilon_r 4.4) (loss_tangent 0.02))
\t\t\t(layer "B.Cu" (type "copper") (thickness 0.035))
\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))
\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))
\t\t\t(copper_finish "ENIG")
\t\t\t(dielectric_constraints no)
\t\t\t(edge_connector bevelled)
\t\t)
"""


def add_stackup():
    """The Icepi Zero v1.4 stack-up (1.6 mm, JLCPCB JLC04161H-7628), plus ENIG and a bevelled edge connector."""
    t = PCB.read_text(encoding="utf-8")
    if "(stackup" not in t:
        t = re.sub(r"\(setup\n", "(setup\n" + STACKUP, t, count=1)
        if "(stackup" not in t:
            t = t.replace("(setup", "(setup\n" + STACKUP, 1)
    t = re.sub(r'\((\d+) "In1\.Cu" signal\)', r'(\1 "In1.Cu" power)', t)
    t = re.sub(r'\((\d+) "In2\.Cu" signal\)', r'(\1 "In2.Cu" power)', t)
    PCB.write_text(t, encoding="utf-8")


def write_rules():
    pro_path = OUT / "pce_card.kicad_pro"
    pro = json.loads(pro_path.read_text(encoding="utf-8")) if pro_path.exists() else {}
    # update, not replace: keep the keys KiCad adds when it saves the project
    pro.setdefault("board", {}).setdefault("design_settings", {}).setdefault("rules", {}).update({
        "min_clearance": DESIGN["clearance"], "min_track_width": DESIGN["track"],
        "min_via_diameter": DESIGN["bga_via_dia"], "min_through_hole_diameter": DESIGN["bga_via_drill"],
        "min_hole_to_hole": FAB["hole_to_hole"], "min_copper_edge_clearance": DESIGN["edge"],
        # 0.18, not 0.25: the USB4105 USB-C footprint (as on the Icepi) has its GND pads
        # 0.194 mm from its own locating-peg holes. JLC's NPTH-to-pad floor is below that.
        "min_hole_clearance": 0.18,
        "min_via_annular_width": 0.1,
        "min_text_height": FAB["silk_text"], "min_text_thickness": FAB["silk_line"],
    })
    power = ["+5V_CON", "+5V_CARD", "VBUS_FT", "VBUS_RP", "+3V3", "+2V5", "+1V1", "+1V1_RP", "PWR_FILTERED_2V5", "GND"]
    pro["net_settings"] = {
        "classes": [
            {"name": "Default", "clearance": DESIGN["clearance"], "track_width": DESIGN["default_track"],
             "via_diameter": DESIGN["via_dia"], "via_drill": DESIGN["via_drill"]},
            {"name": "Power", "clearance": DESIGN["clearance"], "track_width": DESIGN["power_track"],
             "via_diameter": DESIGN["via_dia"], "via_drill": DESIGN["via_drill"]},
        ],
        "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in power],
        "meta": {"version": 4},
    }
    pro_path.write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")
    (OUT / "pce_card.kicad_dru").write_text(f"""# The card: custom design rules
#
# FAB: {FAB['name']}.
#   tracks >= {DESIGN['track']} mm ({DESIGN['default_track']} mm default, {DESIGN['power_track']} mm power), clearance {DESIGN['clearance']} mm,
#   every via {DESIGN['via_dia']}/{DESIGN['via_drill']} mm, hole to foreign copper {FAB['hole_clearance']} mm,
#   copper to edge {DESIGN['edge']} mm (not the fingers), silkscreen text {FAB['silk_text']} mm / lines {FAB['silk_line']} mm.
# In1 = GND plane, In2 = +3V3 plane.
#
# RULES NO DRC CAN CHECK, look before ordering:
#  - the 8.6 mm finger zone holds only fingers and the tracks that leave them (rule area on the board);
#  - every bus line runs over the unbroken In1 GND plane from finger to translator;
#  - the translators sit right behind the finger zone; the 33 ohm resistors between them and the fingers;
#  - the PCM5102A's analogue outputs stay away from the SDRAM and the regulators' switch nodes.

(version 1)

(rule "minimum track width"
	(constraint track_width (min {DESIGN['track']}mm))
	(severity error))

(rule "minimum clearance"
	(constraint clearance (min {DESIGN['clearance']}mm))
	(severity error))

(rule "vias: standard-price size at both fabs"
	(constraint via_diameter (min {DESIGN['via_dia']}mm))
	(constraint hole_size (min {DESIGN['via_drill']}mm))
	(condition "A.Type == 'Via'"))

(rule "hole to hole"
	(constraint hole_to_hole (min {FAB['hole_to_hole']}mm))
	(severity error))

# A library footprint's own pads and pegs (the USB-C sockets' GND pads sit 0.194 mm
# from their pegs) are the part maker's geometry, made by both fabs every day.
(rule "hole to foreign copper"
	(constraint hole_clearance (min {FAB['hole_clearance']}mm))
	(condition "!(A.Type == 'Pad' && B.Type == 'Pad' && A.Parent.Reference == B.Parent.Reference)")
	(severity error))

(rule "copper to board edge"
	(constraint edge_clearance (min {DESIGN['edge']}mm))
	(condition "A.Parent.Reference != 'J101'")
	(severity error))

# Power nets are drawn {DESIGN['power_track']} mm (their net class) but may neck to the
# track minimum where they enter a fine-pitch pad, so no separate minimum for them.

(rule "silkscreen text"
	(constraint text_height (min {FAB['silk_text']}mm))
	(constraint text_thickness (min {FAB['silk_line']}mm))
	(condition "A.Layer == 'F.Silkscreen' || A.Layer == 'B.Silkscreen'"))
""", encoding="utf-8")
    (OUT / "board.json").write_text(json.dumps({
        "_comment": "Read by PCB HERO's scripts/check_board.py. The standard-price floor of JLCPCB and PCBWay, 4 layers.",
        "fab": FAB,
        "bga": [{"ref": "U1", "pitch": 0.8, "via": [DESIGN["bga_via_dia"], DESIGN["bga_via_drill"]]}],
        "diff_classes": [], "min_custom_rules": 6, "ignore_pairlike": ["RP_DP", "RP_DM", "USB_D2+", "USB_D2-"],
    }, indent=2) + "\n", encoding="utf-8")
    print("wrote the .kicad_dru, the project rules and board.json")


if __name__ == "__main__":
    main()
