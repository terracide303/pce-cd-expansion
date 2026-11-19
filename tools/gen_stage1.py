#!/usr/bin/env python3
"""Generate the stage-1 KiCad project from hw/stage1/design.py.

    python tools/gen_stage1.py

Writes hw/stage1/: pce_exp_stage1.kicad_sch / .kicad_pro, the project symbol
library pce_exp.kicad_sym (the port and the Tang headers, built from the CSVs),
pce_exp.pretty/ (the 3x23 port footprint), and the library tables.

Every pin gets a net label at its connection point; connectivity is by label,
so there are no hand-drawn wires to get wrong. Then run tools/check_stage1.py:
it reads KiCad's OWN netlist of this schematic back and checks it.
"""
import os, pathlib, re, sys, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "hw" / "stage1"
sys.path.insert(0, str(OUT))
import design  # noqa: E402

KICAD_SYM = pathlib.Path(os.environ.get("KICAD_SYMBOL_DIR", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols"))
PROJECT = "pce_exp_stage1"
NS = uuid.UUID("6b1e2f0a-3c4d-4e5f-8a9b-0c1d2e3f4a5b")    # deterministic uuids: regenerating gives a stable diff


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def fmt(v):
    return f"{round(v, 4):g}"


# ---------------------------------------------------------------- S-expression helpers

def block(text, start):
    d = 0
    for j in range(start, len(text)):
        if text[j] == "(":
            d += 1
        elif text[j] == ")":
            d -= 1
            if d == 0:
                return text[start:j + 1]
    raise ValueError("unbalanced")


def find_symbol(lib_text, name):
    m = re.search(r'\(symbol "%s"' % re.escape(name), lib_text)
    if not m:
        raise KeyError(name)
    return block(lib_text, m.start())


def flatten(lib, name):
    """A library symbol, with 'extends' resolved, renamed to lib:name for embedding."""
    text = (KICAD_SYM / f"{lib}.kicad_sym").read_text(encoding="utf-8") if lib != "pce_exp" else CUSTOM_LIB
    body = find_symbol(text, name)
    ext = re.search(r'\(extends "([^"]+)"\)', body)
    if ext:
        base = find_symbol(text, ext.group(1))
        base = base.replace(f'(symbol "{ext.group(1)}_', f'(symbol "{name}_')
        body = base.replace(f'(symbol "{ext.group(1)}"', f'(symbol "{name}"', 1)
    return body.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


def prop_at(sym_text, key):
    """Where the library symbol puts a property (symbol coordinates, y up)."""
    m = re.search(r'\(property "%s" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+)' % key, sym_text)
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


def pins_of(sym_text):
    """number -> (x, y, rotation) of each pin's connection point, in symbol coordinates (y up)."""
    out = {}
    for m in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\).*?\(number "([^"]+)"', sym_text, re.S):
        out[m.group(4)] = (float(m.group(1)), float(m.group(2)), int(float(m.group(3))))
    return out


# ---------------------------------------------------------------- custom symbols, from the CSVs

def pin_sx(num, name, x, y, rot, kind="passive"):
    return (f'\t\t\t(pin {kind} line (at {fmt(x)} {fmt(y)} {rot}) (length 2.54)\n'
            f'\t\t\t\t(name "{esc(name)}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{esc(num)}" (effects (font (size 1.27 1.27)))))\n')


def box_symbol(name, ref, value, left, right, width=30.48):
    """A rectangle with pins down the left and right. left/right: [(number, name)]."""
    n = max(len(left), len(right))
    top = (n - 1) * 2.54 / 2
    top = round(top / 1.27) * 1.27
    pins = ""
    for i, (num, nm) in enumerate(left):
        pins += pin_sx(num, nm, -width / 2 - 2.54, top - i * 2.54, 0)
    for i, (num, nm) in enumerate(right):
        pins += pin_sx(num, nm, width / 2 + 2.54, top - i * 2.54, 180)
    y0, y1 = top + 2.54, top - n * 2.54
    return (f'\t(symbol "{name}" (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
            f'\t\t(property "Reference" "{ref}" (at 0 {fmt(y0 + 2.54)} 0) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Value" "{esc(value)}" (at 0 {fmt(y1 - 2.54)} 0) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(symbol "{name}_0_1"\n'
            f'\t\t\t(rectangle (start {fmt(-width / 2)} {fmt(y0)}) (end {fmt(width / 2)} {fmt(y1)})\n'
            f'\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background))))\n'
            f'\t\t(symbol "{name}_1_1"\n{pins}\t\t)\n\t)\n')


def build_custom_lib():
    ext = design.EXT_BUS
    a = [(r["pin"], r["signal"]) for r in ext if r["row"] == "a"]
    b = [(r["pin"], r["signal"]) for r in ext if r["row"] == "b"]
    c = [(r["pin"], r["signal"]) for r in ext if r["row"] == "c"]
    syms = [box_symbol("PCE_EXT_BUS", "J", "PCE EXT BUS", a + b, c, width=25.4)]
    for side, name in [("L", "TANG_NANO_20K_LEFT"), ("R", "TANG_NANO_20K_RIGHT")]:
        rows = [r for r in design.HEADER if r["header_pos"].startswith(side)]
        pins = [(r["header_pos"][1:], (f'{r["fpga_pin"]} {r["io_name"]}' if r["fpga_pin"] else r["io_name"])) for r in rows]
        syms.append(box_symbol(name, "J", name.replace("_", " ").title(), pins if side == "L" else [], pins if side == "R" else [], width=33.02))
    return '(kicad_symbol_lib (version 20241209) (generator "pce_exp_gen")\n' + "".join(syms) + ")\n"


CUSTOM_LIB = build_custom_lib()


# ---------------------------------------------------------------- the port footprint

def port_footprint():
    """3 columns (a, b, c) x 23 rows, 2.54 mm. Pad names are the port pin names.
    Orientation must be checked 1:1 against the console before ordering (TEST_PLAN T1b)."""
    pads = ""
    for ci, col in enumerate("abc"):
        for n in range(1, 24):
            shape = "rect" if (col, n) == ("a", 1) else "oval"
            pads += (f'\t(pad "{col}{n}" thru_hole {shape} (at {fmt(ci * 2.54)} {fmt((n - 1) * 2.54)}) (size 1.7 1.7) (drill 1)\n'
                     f'\t\t(layers "*.Cu" "*.Mask") (uuid "{uid("fp", col, n)}"))\n')
    w, h = 2 * 2.54, 22 * 2.54
    line = lambda x0, y0, x1, y1, layer, wd: (f'\t(fp_line (start {fmt(x0)} {fmt(y0)}) (end {fmt(x1)} {fmt(y1)}) '
                                              f'(stroke (width {wd}) (type solid)) (layer "{layer}") (uuid "{uid("fpl", x0, y0, x1, y1, layer)}"))\n')
    out = ""
    for (x0, y0, x1, y1) in [(-1.27, -1.27, w + 1.27, -1.27), (w + 1.27, -1.27, w + 1.27, h + 1.27),
                             (w + 1.27, h + 1.27, -1.27, h + 1.27), (-1.27, h + 1.27, -1.27, -1.27)]:
        out += line(x0, y0, x1, y1, "F.SilkS", 0.12)
    for (x0, y0, x1, y1) in [(-1.8, -1.8, w + 1.8, -1.8), (w + 1.8, -1.8, w + 1.8, h + 1.8),
                             (w + 1.8, h + 1.8, -1.8, h + 1.8), (-1.8, h + 1.8, -1.8, -1.8)]:
        out += line(x0, y0, x1, y1, "F.CrtYd", 0.05)
    text = lambda kind, s, x, y, layer: (f'\t(fp_text {kind} "{s}" (at {fmt(x)} {fmt(y)}) (layer "{layer}") (uuid "{uid("fpt", kind, s)}")\n'
                                         f'\t\t(effects (font (size 1 1) (thickness 0.15))))\n')
    return (f'(footprint "PinSocket_3x23_P2.54mm_Vertical" (version 20240108) (generator "pce_exp_gen") (layer "F.Cu")\n'
            f'\t(descr "PC Engine EXT BUS mate: 3x23 female header, 2.54 mm. Pads named by port pin (a1..c23). '
            f'Columns a/b/c and rows 1..23 as seen looking INTO the console (PCEdev wiki); verify orientation 1:1 before ordering.")\n'
            f'\t(attr through_hole)\n'
            + text("reference", "REF**", w / 2, -3, "F.SilkS") + text("value", "PCE_EXT_BUS", w / 2, h + 3, "F.Fab")
            + text("user", "a", 0, -2.2, "F.SilkS").replace('"user"', 'user') + text("user", "c", w, -2.2, "F.SilkS").replace('"user"', 'user')
            + out + pads + ")\n")


# ---------------------------------------------------------------- placement (mm, A3 landscape)

PLACE = {
    "J1": (45.72, 152.4), "U1": (124.46, 63.5), "U2": (124.46, 144.78),
    "U3": (210.82, 63.5), "U4": (210.82, 132.08), "U5": (210.82, 200.66),
    "J2": (312.42, 88.9), "J3": (373.38, 88.9),
}
for i in range(8):
    PLACE[f"R{i + 1}"] = (254.0 + i * 10.16, 162.56)   # side by side: each one's labels get their own column
for i in range(8):
    PLACE[f"C{i + 1}"] = (101.6 + i * 12.7, 251.46)
for i in range(6):
    PLACE[f"TP{i + 1}"] = (228.6 + i * 15.24, 251.46)
for i in range(3):
    PLACE[f"#FLG0{i + 1}"] = (322.58 + i * 20.32, 251.46)


def label_angle(rot):
    # pin rotation = direction from the connection point INTO the body; put text the other way
    return {0: (180, "right"), 180: (0, "left"), 90: (270, "right"), 270: (90, "left")}[rot % 360]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pce_exp.kicad_sym").write_text(CUSTOM_LIB, encoding="utf-8")
    (OUT / "pce_exp.pretty").mkdir(exist_ok=True)
    (OUT / "pce_exp.pretty" / "PinSocket_3x23_P2.54mm_Vertical.kicad_mod").write_text(port_footprint(), encoding="utf-8")
    (OUT / "sym-lib-table").write_text('(sym_lib_table (version 7)\n  (lib (name "pce_exp")(type "KiCad")(uri "${KIPRJMOD}/pce_exp.kicad_sym")(options "")(descr "PCE CD expansion"))\n)\n', encoding="utf-8")
    (OUT / "fp-lib-table").write_text('(fp_lib_table (version 7)\n  (lib (name "pce_exp")(type "KiCad")(uri "${KIPRJMOD}/pce_exp.pretty")(options "")(descr "PCE CD expansion"))\n)\n', encoding="utf-8")

    sheet = uid("sheet")
    libs, pinmaps = {}, {}
    for p in design.PARTS:
        if p["sym"] not in libs:
            lib, name = p["sym"].split(":")
            libs[p["sym"]] = flatten(lib, name)
            pinmaps[p["sym"]] = pins_of(libs[p["sym"]])

    items = []
    for p in design.PARTS:
        ref, (X, Y) = p["ref"], PLACE[p["ref"]]
        pm = pinmaps[p["sym"]]
        missing = set(pm) - set(p["pins"])
        extra = set(p["pins"]) - set(pm)
        if missing or extra:
            sys.exit(f"{ref}: design pins don't match the symbol {p['sym']}: missing {sorted(missing)}, unknown {sorted(extra)}")
        hidden = "(hide yes)"
        (rx, ry), (vx, vy) = prop_at(libs[p["sym"]], "Reference"), prop_at(libs[p["sym"]], "Value")
        props = [("Reference", ref, X + rx, Y - ry, "" if not ref.startswith("#") else hidden),
                 ("Value", p["value"], X + vx, Y - vy, "" if not ref.startswith("#") else hidden),
                 ("Footprint", p["fp"], X, Y, hidden), ("Datasheet", "", X, Y, hidden)]
        prop_sx = "".join(f'\t\t(property "{k}" "{esc(v)}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) {h}))\n'
                          for k, v, x, y, h in props)
        pin_sx_ = "".join(f'\t\t(pin "{esc(n)}" (uuid "{uid(ref, "pin", n)}"))\n' for n in pm)
        items.append(f'\t(symbol (lib_id "{p["sym"]}") (at {fmt(X)} {fmt(Y)} 0) (unit 1)\n'
                     f'\t\t(exclude_from_sim no) (in_bom {"no" if ref.startswith("#") else "yes"}) (on_board {"no" if ref.startswith("#") else "yes"}) (dnp no)\n'
                     f'\t\t(uuid "{uid(ref)}")\n{prop_sx}{pin_sx_}'
                     f'\t\t(instances (project "{PROJECT}" (path "/{sheet}" (reference "{esc(ref)}") (unit 1))))\n\t)\n')
        for n, (px, py, rot) in pm.items():
            x, y = X + px, Y - py
            net = p["pins"][n]
            if net is None:
                items.append(f'\t(no_connect (at {fmt(x)} {fmt(y)}) (uuid "{uid(ref, "nc", n)}"))\n')
            else:
                ang, just = label_angle(rot)
                items.append(f'\t(label "{esc(net)}" (at {fmt(x)} {fmt(y)} {ang}) (fields_autoplaced yes)\n'
                             f'\t\t(effects (font (size 1.27 1.27)) (justify {just} bottom)) (uuid "{uid(ref, "lbl", n)}"))\n')

    lib_sx = "".join("\t\t" + v.replace("\n", "\n\t\t").rstrip("\t") + "\n" for v in libs.values())
    sch = (f'(kicad_sch (version 20260306) (generator "pce_exp_gen") (generator_version "10.0")\n'
           f'\t(uuid "{sheet}")\n\t(paper "A3")\n'
           f'\t(title_block (title "PCE CD expansion - stage 1 RAM responder") (date "2026-11-19") (rev "0.1")\n'
           f'\t\t(comment 1 "GENERATED by tools/gen_stage1.py from hw/stage1/design.py - edit the data, not this file")\n'
           f'\t\t(comment 2 "Checked by tools/check_stage1.py against KiCad\'s own netlist"))\n'
           f'\t(lib_symbols\n{lib_sx}\t)\n' + "".join(items) +
           '\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')
    (OUT / f"{PROJECT}.kicad_sch").write_text(sch, encoding="utf-8")
    pro = OUT / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text('{\n  "meta": {"filename": "%s.kicad_pro", "version": 3},\n  "sheets": [["%s", "Root"]]\n}\n' % (PROJECT, sheet), encoding="utf-8")
    n_pins = sum(len(p["pins"]) for p in design.PARTS)
    n_nc = sum(1 for p in design.PARTS for v in p["pins"].values() if v is None)
    print(f"wrote {OUT.relative_to(ROOT).as_posix()}/{PROJECT}.kicad_sch: {len(design.PARTS)} parts, {n_pins} pins ({n_nc} not connected)")


if __name__ == "__main__":
    main()
