#!/usr/bin/env python3
"""Create the stage-1 PCB: every footprint and every net, ready for placement.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/make_stage1_pcb.py

Must run in KiCad's own Python (it uses pcbnew). Reads the netlist KiCad exports
from the schematic, so the board carries exactly the schematic's connections.

PLACEMENT IS NOT DONE HERE, ON PURPOSE. PCB HERO's rule: a human places parts.
The footprints are staged in labelled groups BESIDE the board, the board outline
is a suggested rectangle, and the design rules are set. Each footprint is linked
to its schematic symbol, so KiCad's "Update PCB from Schematic" (F8) recognises
them instead of adding duplicates.

Also writes the design rules (.kicad_dru), the project rules (.kicad_pro) and
board.json, so PCB HERO's scripts/check_board.py can check the board.
"""
import json, os, pathlib, re, subprocess, sys, tempfile

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "hw" / "stage1"
SCH = OUT / "pce_exp_stage1.kicad_sch"
PCB = OUT / "pce_exp_stage1.kicad_pcb"
KICAD_FP = pathlib.Path(os.environ.get("KICAD_FOOTPRINT_DIR", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\share\kicad\footprints"))
KICAD_CLI = os.environ.get("KICAD_CLI", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe")
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(ROOT / "tools"))
import design  # noqa: E402
from gen_stage1 import uid  # noqa: E402  (the same deterministic symbol uuids the schematic uses)

# JLCPCB 2-layer "standard" floor, from KiCadRoutingTools py_router/fab_tiers.py _FAB_FLOORS[2]['standard'].
FAB = {"name": "JLCPCB 2-layer standard", "track": 0.127, "clearance": 0.127, "via_hole": 0.20,
       "via_dia": 0.45, "hole_to_hole": 0.20, "edge": 0.20}
# What we actually draw: comfortably above the floor (PCB HERO playbook, phase 3).
DESIGN = {"track": 0.25, "clearance": 0.2, "via_dia": 0.6, "via_drill": 0.3, "edge": 0.5, "power_track": 0.5}

# Staging groups, beside (to the right of) the suggested outline. mm.
GROUPS = {
    "port":        (["J1"], (130, 10)),
    "Tang module": (["A1"], (160, 10)),
    "decoder + data": (["U1", "U2"] + [f"R{i}" for i in range(1, 9)], (200, 10)),
    "inputs":      (["U3", "U4", "U5"], (240, 10)),
    "decoupling":  ([f"C{i}" for i in range(1, 9)], (200, 90)),
    "test points": ([f"TP{i}" for i in range(1, 7)], (240, 70)),
}
OUTLINE = (0, 0, 100, 75)       # a suggested starting rectangle; resize it to the placement


def netlist():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "n.net"
        subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(SCH)],
                       capture_output=True, check=False)
        text = out.read_text(encoding="utf-8")
    pins = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', text, re.S):
        name = m.group(1)          # exactly as KiCad names it ("/F_A15", "unconnected-(...)"): parity needs the same names
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins[(ref, pin)] = name
    return pins


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = OUT / "pce_exp.pretty" if lib == "pce_exp" else KICAD_FP / f"{lib}.pretty"
    fp = pcbnew.FootprintLoad(str(path), name)
    if fp is None:
        sys.exit(f"footprint not found: {fpid}")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def mm(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def main():
    pins = netlist()
    board = pcbnew.BOARD()
    nets = {}

    def net(name):
        if name not in nets:
            nets[name] = pcbnew.NETINFO_ITEM(board, name)
            board.Add(nets[name])
        return nets[name]

    where = {}
    for title, (refs, (x0, y0)) in GROUPS.items():
        y = y0
        for ref in refs:
            where[ref] = (x0, y)
            y += 62 if ref in ("J1", "A1") else (14 if ref.startswith("U") else 5)
        txt = pcbnew.PCB_TEXT(board)
        txt.SetText(title)
        txt.SetPosition(mm(x0, y0 - 6))
        txt.SetLayer(pcbnew.Cmts_User)
        board.Add(txt)

    placed = 0
    for p in design.PARTS:
        ref = p["ref"]
        if ref.startswith("#"):
            continue
        fp = load_fp(p["fp"])
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        fp.SetPath(pcbnew.KIID_PATH(f"/{uid(ref)}"))
        fp.SetPosition(mm(*where[ref]))
        board.Add(fp)
        for pad in fp.Pads():
            name = pins.get((ref, pad.GetNumber()))
            if name:
                pad.SetNet(net(name))
        placed += 1

    x0, y0, x1, y1 = OUTLINE
    for (a, b, c, d) in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(mm(a, b))
        seg.SetEnd(mm(c, d))
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(pcbnew.FromMM(0.1))
        board.Add(seg)
    note = pcbnew.PCB_TEXT(board)
    note.SetText("Suggested outline: resize to the placement. Parts are staged to the right, unplaced (placement is human).")
    note.SetPosition(mm(x0 + 50, y1 + 5))
    note.SetLayer(pcbnew.Cmts_User)
    board.Add(note)

    ds = board.GetDesignSettings()
    ds.m_TrackMinWidth = pcbnew.FromMM(DESIGN["track"] / 2)       # board floor: half the drawn width,
    ds.m_MinClearance = pcbnew.FromMM(FAB["clearance"])           # but never below the fab
    pcbnew.SaveBoard(str(PCB), board)
    print(f"wrote {PCB.relative_to(ROOT).as_posix()}: {placed} footprints, {len(nets)} nets, staged (not placed)")
    write_rules()


def write_rules():
    pro_path = OUT / "pce_exp_stage1.kicad_pro"
    pro = json.loads(pro_path.read_text(encoding="utf-8")) if pro_path.exists() else {}
    pro.setdefault("board", {}).setdefault("design_settings", {})["rules"] = {
        "min_clearance": DESIGN["clearance"], "min_track_width": DESIGN["track"],
        "min_via_diameter": DESIGN["via_dia"], "min_through_hole_diameter": DESIGN["via_drill"],
        "min_hole_to_hole": 0.5, "min_copper_edge_clearance": DESIGN["edge"], "min_hole_clearance": 0.25,
        "min_via_annular_width": 0.15,
    }
    pro["net_settings"] = {
        "classes": [
            {"name": "Default", "clearance": DESIGN["clearance"], "track_width": DESIGN["track"],
             "via_diameter": DESIGN["via_dia"], "via_drill": DESIGN["via_drill"]},
            {"name": "Power", "clearance": DESIGN["clearance"], "track_width": DESIGN["power_track"],
             "via_diameter": DESIGN["via_dia"], "via_drill": DESIGN["via_drill"]},
        ],
        "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in ("+5VA", "+3V3", "GND")],
        "meta": {"version": 4},
    }
    pro_path.write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")
    (OUT / "pce_exp_stage1.kicad_dru").write_text(f"""# Stage 1 RAM responder: custom design rules
#
# FAB: {FAB['name']} (KiCadRoutingTools py_router/fab_tiers.py, 2-layer standard tier):
#   track/space {FAB['track']}/{FAB['clearance']} mm, via {FAB['via_dia']}/{FAB['via_hole']} mm,
#   hole-to-hole {FAB['hole_to_hole']} mm, copper to edge {FAB['edge']} mm.
# We draw well above it (PCB HERO playbook phase 3). The bus is 7.16 MHz with
# fast logic edges: no impedance classes, but keep traces short and over ground.
#
# THE RULE NO DRC CAN CHECK: on a 2-layer board, pour GND on the bottom and keep
# it unbroken under the data and address lines between the port and the
# translators. Look at it before ordering.

(version 1)

(rule "minimum track width"
\t(constraint track_width (min {DESIGN['track']}mm))
\t(severity error))

(rule "minimum clearance"
\t(constraint clearance (min {DESIGN['clearance']}mm))
\t(severity error))

(rule "minimum via"
\t(constraint via_diameter (min {DESIGN['via_dia']}mm))
\t(constraint hole_size (min {DESIGN['via_drill']}mm))
\t(severity error))

(rule "hole to hole"
\t(constraint hole_to_hole (min 0.5mm))
\t(severity error))

(rule "copper to board edge"
\t(constraint edge_clearance (min {DESIGN['edge']}mm))
\t(severity error))

(rule "power track width"
\t(constraint track_width (min {DESIGN['power_track']}mm))
\t(condition "A.NetClass == 'Power'"))
""", encoding="utf-8")
    (OUT / "board.json").write_text(json.dumps({
        "_comment": "Read by PCB HERO's scripts/check_board.py. Fab floor from KiCadRoutingTools fab_tiers.py (2-layer standard). No BGA and no differential pairs on this board.",
        "fab": FAB, "bga": [], "diff_classes": [], "min_custom_rules": 5, "ignore_pairlike": [],
    }, indent=2) + "\n", encoding="utf-8")
    print("wrote the .kicad_dru, the project rules and board.json")


if __name__ == "__main__":
    main()
