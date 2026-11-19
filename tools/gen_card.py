#!/usr/bin/env python3
"""Generate the card's KiCad project from hw/card/design.py.

    python tools/gen_card.py

Writes hw/card/: pce_card.kicad_sch (root) + one sub-sheet per block, the project
file, the card-edge symbol and footprint (pce_card.kicad_sym, pce_card.pretty/), and
the library tables. Every pin gets a GLOBAL label at its connection point, so nets
join across sheets by name and there are no hand-drawn wires to get wrong. Multi-unit
symbols (the ECP5) are placed unit by unit on the sheets design.UNIT_SHEET names.

Then run tools/check_card.py: it reads KiCad's own netlist back and checks it.
"""
import csv, math, os, pathlib, re, sys, uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "hw" / "card"
sys.path.insert(0, str(OUT))
import design  # noqa: E402

KICAD_SYM = pathlib.Path(os.environ.get("KICAD_SYMBOL_DIR", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\share\kicad\symbols"))
VENDOR_SYM = OUT / "reference" / "icepi-zero-v1.4" / "icepi-embedded.kicad_sym"
PROJECT = "pce_card"
NS = uuid.UUID("0c5d7a1e-91b2-4c3d-8e4f-a5b6c7d8e9f0")
FONT = 1.27
CHAR = 1.0          # mm per label character, generous


def uid(*parts):
    return str(uuid.uuid5(NS, "/".join(map(str, parts))))


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"')


def fmt(v):
    return f"{round(v, 4):g}"


def snap(v, g=2.54):
    return round(v / g) * g


# ---------------------------------------------------------------- symbols
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


_cache = {}
BODY = {}       # lib_id -> {unit: [(x, y) of graphics]}


def lib_text(lib):
    if lib not in _cache:
        if lib == "pce_card":
            _cache[lib] = CUSTOM_LIB
        elif lib == "icepi":
            _cache[lib] = VENDOR_SYM.read_text(encoding="utf-8")
        else:
            _cache[lib] = (KICAD_SYM / f"{lib}.kicad_sym").read_text(encoding="utf-8")
    return _cache[lib]


def flatten(lib_id):
    """The library symbol with 'extends' resolved, top level renamed lib:name for embedding."""
    lib, name = lib_id.split(":")
    text = lib_text(lib)
    body = find_symbol(text, name)
    ext = re.search(r'\(extends "([^"]+)"\)', body)
    if ext:
        base = find_symbol(text, ext.group(1))
        base = base.replace(f'(symbol "{ext.group(1)}_', f'(symbol "{name}_')
        props = dict(re.findall(r'(\(property "(?:Value|Footprint|Datasheet|Description)".*?\n\t\t\))', body, re.S) and [])
        body = base.replace(f'(symbol "{ext.group(1)}"', f'(symbol "{name}"', 1)
    return body.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)


def prop_at(sym_text, key):
    m = re.search(r'\(property "%s" "[^"]*"\s*\(at ([-\d.]+) ([-\d.]+)' % key, sym_text)
    return (float(m.group(1)), float(m.group(2))) if m else (0.0, 0.0)


def units_of(sym_text, lib_id):
    """{unit: {pin number: (x, y, rot, name)}} from the sub-symbols NAME_unit_style (style 1 only)."""
    name = lib_id.split(":")[1]
    out = {}
    for m in re.finditer(r'\(symbol "%s_(\d+)_(\d+)"' % re.escape(name), sym_text):
        u, style = int(m.group(1)), int(m.group(2))
        if style not in (0, 1):
            continue
        sub = block(sym_text, m.start())
        for pm in re.finditer(r'\(pin \w+ \w+\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\).*?\(name "([^"]*)".*?\(number "([^"]+)"', sub, re.S):
            out.setdefault(u, {})[pm.group(5)] = (float(pm.group(1)), float(pm.group(2)), int(float(pm.group(3))), pm.group(4))
    # the drawn body of each unit (unit 0 graphics are shared by all units)
    gfx = {}
    for m in re.finditer(r'\(symbol "%s_(\d+)_(\d+)"' % re.escape(name), sym_text):
        sub = block(sym_text, m.start())
        pts = [(float(a), float(b)) for a, b in re.findall(r'\((?:start|end|xy|at|center|mid) ([-\d.]+) ([-\d.]+)', sub)]
        gfx.setdefault(int(m.group(1)), []).extend(pts)
    BODY[lib_id] = gfx
    if 0 in out:
        if len(out) > 1:
            common = out.pop(0)
            for u in out:
                out[u].update(common)
            if len(out) > 1:
                raise SystemExit(f"{lib_id}: pins common to several units are not supported")
        else:
            out[1] = out.pop(0)
    return out


# ---------------------------------------------------------------- the card edge: symbol and footprint
HUCARD = list(csv.DictReader(open(ROOT / "docs" / "hucard_pinout.csv", encoding="utf-8")))


def pin_sx(num, name, x, y, rot):
    return (f'\t\t\t(pin passive line (at {fmt(x)} {fmt(y)} {rot}) (length 2.54)\n'
            f'\t\t\t\t(name "{esc(name)}" (effects (font (size {FONT} {FONT}))))\n'
            f'\t\t\t\t(number "{esc(num)}" (effects (font (size {FONT} {FONT})))))\n')


def edge_symbol():
    left = [(r["pin"], r["signal"]) for r in HUCARD if int(r["pin"]) <= 19]
    right = [(r["pin"], r["signal"]) for r in HUCARD if int(r["pin"]) > 19]
    w, top = 20.32, 9 * 2.54
    pins = "".join(pin_sx(n, s, -w / 2 - 2.54, top - i * 2.54, 0) for i, (n, s) in enumerate(left))
    pins += "".join(pin_sx(n, s, w / 2 + 2.54, top - i * 2.54, 180) for i, (n, s) in enumerate(right))
    y0, y1 = top + 2.54, top - 19 * 2.54
    return (f'\t(symbol "HUCARD_EDGE" (exclude_from_sim no) (in_bom no) (on_board yes)\n'
            f'\t\t(property "Reference" "J" (at 0 {fmt(y0 + 2.54)} 0) (effects (font (size {FONT} {FONT}))))\n'
            f'\t\t(property "Value" "HUCARD_EDGE" (at 0 {fmt(y1 - 2.54)} 0) (effects (font (size {FONT} {FONT}))))\n'
            f'\t\t(property "Footprint" "pce_card:HuCard_Edge_38" (at 0 0 0) (effects (font (size {FONT} {FONT})) (hide yes)))\n'
            f'\t\t(property "Datasheet" "docs/hucard_pinout.csv" (at 0 0 0) (effects (font (size {FONT} {FONT})) (hide yes)))\n'
            f'\t\t(symbol "HUCARD_EDGE_0_1" (rectangle (start {fmt(-w / 2)} {fmt(y0)}) (end {fmt(w / 2)} {fmt(y1)})\n'
            f'\t\t\t(stroke (width 0.254) (type default)) (fill (type background))))\n'
            f'\t\t(symbol "HUCARD_EDGE_1_1"\n{pins}\t\t)\n\t)\n')


CUSTOM_LIB = '(kicad_symbol_lib (version 20241209) (generator "pce_card_gen")\n' + edge_symbol() + ")\n"


def edge_footprint():
    """38 gold fingers, 1.27 mm pitch, 0.75 mm wide, on F.Cu with the mask open
    (docs/STAGE1-CARD.md §1: repro HuCard geometry, to confirm with T1b/T1d).
    Origin = the card's edge, centred. Fingers 1 and 38 are 5.5 mm, 21 is 6.0 mm, the rest 5.0 mm.
    Pin 1 at -x. The board outline belongs to the PCB, not this footprint."""
    pads = ""
    for n in range(1, 39):
        x = (n - 19.5) * 1.27
        ln = 5.5 if n in (1, 38) else 6.0 if n == 21 else 5.0
        pads += (f'\t(pad "{n}" connect rect (at {fmt(x)} {fmt(-ln / 2)}) (size 0.75 {fmt(ln)})\n'
                 f'\t\t(layers "F.Cu" "F.Mask") (uuid "{uid("edge", n)}"))\n')
    keep = (f'\t(fp_rect (start -27.05 -8.6) (end 27.05 0) (stroke (width 0.1) (type dash)) (fill none) '
            f'(layer "F.Fab") (uuid "{uid("edge", "zone")}"))\n'
            f'\t(fp_text user "slot insertion 8.6 mm: no parts, no vias" (at 0 -7.6) (layer "F.Fab") (uuid "{uid("edge", "t")}")\n'
            f'\t\t(effects (font (size 0.8 0.8) (thickness 0.12))))\n')
    return ('(footprint "HuCard_Edge_38" (version 20240108) (generator "pce_card_gen") (layer "F.Cu")\n'
            '\t(descr "HuCard edge connector, 38 fingers at 1.27 mm (PC Engine). Geometry from a working repro card, '
            'docs/STAGE1-CARD.md; print 1:1 and check against a real HuCard before ordering (TEST_PLAN T1b).")\n'
            '\t(attr smd)\n'
            f'\t(fp_text reference "REF**" (at 0 -9.6) (layer "F.SilkS") (uuid "{uid("edge", "ref")}") (effects (font (size 1 1) (thickness 0.15))))\n'
            f'\t(fp_text value "HuCard_Edge_38" (at 0 -6.4) (layer "F.Fab") (uuid "{uid("edge", "val")}") (effects (font (size 1 1) (thickness 0.15))))\n'
            + keep + pads + ")\n")


# ---------------------------------------------------------------- layout of one sheet
def label_angle(rot):
    # pin rotation = direction from the connection point INTO the body; the label points away
    return {0: (180, "right"), 180: (0, "left"), 90: (270, "left"), 270: (90, "left")}[rot % 360]


def unit_box(pins, body=()):
    """Bounding box of a unit including its drawn body and room for its labels:
    (x0, y0, x1, y1) in sheet coordinates (y down) relative to the symbol origin."""
    xs = [p[0] for p in pins.values()] + [b[0] for b in body] or [0]
    ys = [-p[1] for p in pins.values()] + [-b[1] for b in body] or [0]
    x0, x1, y0, y1 = min(xs) - 5, max(xs) + 5, min(ys) - 5, max(ys) + 5
    for net_len, (px, py, rot) in pins_with_len(pins):
        room = 6 + net_len * CHAR
        if rot % 360 == 0:
            x0 = min(x0, px - room)
        elif rot % 360 == 180:
            x1 = max(x1, px + room)
        elif rot % 360 == 90:          # pin points up into the body: label goes down
            y1 = max(y1, -py + room)
        else:
            y0 = min(y0, -py - room)
    return x0, y0, x1, y1


def pins_with_len(pins):
    return [(p[4] if len(p) > 4 else 12, p[:3]) for p in pins.values()]


def pack(blocks, width):
    """Shelf packing. blocks: [(key, w, h)] -> {key: (x, y)} top-left, and the used size."""
    pos, x, y, shelf = {}, 0.0, 0.0, 0.0
    for key, w, h in sorted(blocks, key=lambda b: -b[2]):
        if x > 0 and x + w > width:
            x, y, shelf = 0.0, y + shelf + 10, 0.0
        pos[key] = (x, y)
        x += w + 10
        shelf = max(shelf, h)
    return pos, y + shelf


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pce_card.kicad_sym").write_text(CUSTOM_LIB, encoding="utf-8")
    (OUT / "pce_card.pretty").mkdir(exist_ok=True)
    (OUT / "pce_card.pretty" / "HuCard_Edge_38.kicad_mod").write_text(edge_footprint(), encoding="utf-8")
    (OUT / "sym-lib-table").write_text(
        '(sym_lib_table (version 7)\n'
        '  (lib (name "pce_card")(type "KiCad")(uri "${KIPRJMOD}/pce_card.kicad_sym")(options "")(descr "PCE card: edge connector"))\n'
        '  (lib (name "icepi")(type "KiCad")(uri "${KIPRJMOD}/reference/icepi-zero-v1.4/icepi-embedded.kicad_sym")(options "")(descr "Icepi Zero v1.4 symbols, Solderpad v2.1"))\n'
        ')\n', encoding="utf-8")
    (OUT / "fp-lib-table").write_text(
        '(fp_lib_table (version 7)\n'
        '  (lib (name "pce_card")(type "KiCad")(uri "${KIPRJMOD}/pce_card.pretty")(options "")(descr "PCE card"))\n'
        '  (lib (name "icepi-lib")(type "KiCad")(uri "${KIPRJMOD}/reference/icepi-zero-v1.4/icepi-lib.pretty")(options "")(descr "Icepi Zero v1.4 footprints, Solderpad v2.1"))\n'
        ')\n', encoding="utf-8")

    root_uuid = uid("root")
    syms, unitmaps = {}, {}
    for p in design.PARTS:
        if p["sym"] not in syms:
            syms[p["sym"]] = flatten(p["sym"])
            unitmaps[p["sym"]] = units_of(syms[p["sym"]], p["sym"])

    # what goes on each sheet: (part, unit)
    placed = {s: [] for s in design.SHEETS}
    for p in design.PARTS:
        units = unitmaps[p["sym"]]
        allpins = {n for u in units.values() for n in u}
        if allpins != set(p["pins"]):
            sys.exit(f"{p['ref']}: design pins don't match {p['sym']}: missing {sorted(allpins - set(p['pins']))[:10]}, "
                     f"unknown {sorted(set(p['pins']) - allpins)[:10]}")
        for u in sorted(units):
            sheet = design.UNIT_SHEET[u] if len(units) > 1 else p["sheet"]
            placed[sheet].append((p, u))

    sheet_blocks, page = [], 2
    for si, sname in enumerate(design.SHEETS):
        block_uuid = uid("sheetblock", sname)
        path = f"/{root_uuid}/{block_uuid}"
        boxes = []
        for p, u in placed[sname]:
            pins = {n: (*v, len(p["pins"][n] or "")) for n, v in unitmaps[p["sym"]][u].items()}
            pins = {n: (v[0], v[1], v[2], v[3], v[4]) for n, v in pins.items()}
            g = BODY[p["sym"]]
            x0, y0, x1, y1 = unit_box(pins, g.get(u, []) + g.get(0, []))
            boxes.append(((p["ref"], u), x1 - x0, y1 - y0, x0, y0))
        area = sum(w * h for _, w, h, _, _ in boxes)
        width = max(max(w for _, w, _, _, _ in boxes) + 5, math.sqrt(area) * 1.6)
        pos, used_h = pack([(k, w, h) for k, w, h, _, _ in boxes], width)
        off = {k: (x0, y0) for k, _, _, x0, y0 in boxes}
        margin = 25.4
        W = snap(width + 2 * margin, 25.4)
        H = snap(used_h + 2 * margin + 20, 25.4)
        items, libs_here = [], {}
        for p, u in placed[sname]:
            key = (p["ref"], u)
            bx, by = pos[key]
            X = snap(margin + bx - off[key][0])
            Y = snap(margin + 20 + by - off[key][1])
            sym = syms[p["sym"]]
            libs_here[p["sym"]] = sym
            ref = p["ref"]
            hidden = "(hide yes)"
            is_flag = ref.startswith("#")
            (rx, ry), (vx, vy) = prop_at(sym, "Reference"), prop_at(sym, "Value")
            props = [("Reference", ref, X + rx, Y - ry, hidden if is_flag else ""),
                     ("Value", p["value"], X + vx, Y - vy, hidden if is_flag else ""),
                     ("Footprint", p["fp"], X, Y, hidden), ("Datasheet", "", X, Y, hidden),
                     ("LCSC", p.get("lcsc", ""), X, Y, hidden)]
            prop_sx = "".join(f'\t\t(property "{k}" "{esc(v)}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size {FONT} {FONT})) {h}))\n'
                              for k, v, x, y, h in props)
            unit_pins = unitmaps[p["sym"]][u]
            pin_sx_ = "".join(f'\t\t(pin "{esc(n)}" (uuid "{uid(ref, "pin", n)}"))\n' for n in unit_pins)
            in_bom = "no" if (is_flag or ref.startswith("TP")) else "yes"
            items.append(f'\t(symbol (lib_id "{p["sym"]}") (at {fmt(X)} {fmt(Y)} 0) (unit {u})\n'
                         f'\t\t(exclude_from_sim no) (in_bom {in_bom}) (on_board {"no" if is_flag else "yes"}) (dnp no)\n'
                         f'\t\t(uuid "{uid(ref, "unit", u)}")\n{prop_sx}{pin_sx_}'
                         f'\t\t(instances (project "{PROJECT}" (path "{path}" (reference "{esc(ref)}") (unit {u}))))\n\t)\n')
            for n, (px, py, rot, _name) in unit_pins.items():
                x, y = X + px, Y - py
                net = p["pins"][n]
                if net is None:
                    items.append(f'\t(no_connect (at {fmt(x)} {fmt(y)}) (uuid "{uid(ref, "nc", n)}"))\n')
                else:
                    ang, just = label_angle(rot)
                    items.append(f'\t(global_label "{esc(net)}" (shape passive) (at {fmt(x)} {fmt(y)} {ang}) (fields_autoplaced yes)\n'
                                 f'\t\t(effects (font (size {FONT} {FONT})) (justify {just}))\n\t\t(uuid "{uid(ref, "lbl", n)}")\n'
                                 f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {fmt(x)} {fmt(y)} 0)\n'
                                 f'\t\t\t(effects (font (size {FONT} {FONT})) (hide yes))))\n')
        lib_sx = "".join("\t\t" + v.replace("\n", "\n\t\t").rstrip("\t") + "\n" for v in libs_here.values())
        title = design.SHEET_TITLES[sname]
        sch = (f'(kicad_sch (version 20260306) (generator "pce_card_gen") (generator_version "10.0")\n'
               f'\t(uuid "{uid("sheetfile", sname)}")\n\t(paper "User" {fmt(W)} {fmt(H)})\n'
               f'\t(title_block (title "PCE card - {esc(title)}") (date "2026-11-19") (rev "0.1")\n'
               f'\t\t(comment 1 "GENERATED by tools/gen_card.py from hw/card/design.py - edit the data, not this file")\n'
               f'\t\t(comment 2 "FPGA core derived from Icepi Zero v1.4, (c) Chengyin Yao, Solderpad Hardware License v2.1")\n'
               f'\t\t(comment 3 "Checked by tools/check_card.py against KiCad\'s own netlist and the Icepi netlist"))\n'
               f'\t(lib_symbols\n{lib_sx}\t)\n' + "".join(items) + '\t(embedded_fonts no)\n)\n')
        (OUT / f"{sname}.kicad_sch").write_text(sch, encoding="utf-8")
        bx, by = 25.4 + (si % 3) * 76.2, 50.8 + (si // 3) * 38.1
        sheet_blocks.append(
            f'\t(sheet (at {fmt(bx)} {fmt(by)}) (size 50.8 20.32) (fields_autoplaced yes)\n'
            f'\t\t(stroke (width 0.1524) (type solid)) (fill (color 0 0 0 0.0000))\n'
            f'\t\t(uuid "{block_uuid}")\n'
            f'\t\t(property "Sheetname" "{sname}" (at {fmt(bx)} {fmt(by - 0.7)} 0) (effects (font (size {FONT} {FONT})) (justify left bottom)))\n'
            f'\t\t(property "Sheetfile" "{sname}.kicad_sch" (at {fmt(bx)} {fmt(by + 20.92)} 0) (effects (font (size {FONT} {FONT})) (justify left top)))\n'
            f'\t\t(instances (project "{PROJECT}" (path "/{root_uuid}" (page "{page}"))))\n\t)\n')
        page += 1

    rootsch = (f'(kicad_sch (version 20260306) (generator "pce_card_gen") (generator_version "10.0")\n'
               f'\t(uuid "{root_uuid}")\n\t(paper "A4")\n'
               f'\t(title_block (title "PCE CD expansion - the card") (date "2026-11-19") (rev "0.1")\n'
               f'\t\t(comment 1 "GENERATED by tools/gen_card.py from hw/card/design.py - edit the data, not this file")\n'
               f'\t\t(comment 2 "FPGA core derived from Icepi Zero v1.4, (c) Chengyin Yao, Solderpad Hardware License v2.1")\n'
               f'\t\t(comment 3 "Architecture: docs/CARD.md"))\n'
               f'\t(lib_symbols)\n' + "".join(sheet_blocks) +
               '\t(sheet_instances (path "/" (page "1")))\n\t(embedded_fonts no)\n)\n')
    (OUT / f"{PROJECT}.kicad_sch").write_text(rootsch, encoding="utf-8")
    pro = OUT / f"{PROJECT}.kicad_pro"
    if not pro.exists():
        pro.write_text('{\n  "meta": {"filename": "%s.kicad_pro", "version": 3},\n  "sheets": [["%s", "Root"]]\n}\n'
                       % (PROJECT, root_uuid), encoding="utf-8")
    n_pins = sum(len(p["pins"]) for p in design.PARTS)
    print(f"wrote hw/card/{PROJECT}.kicad_sch + {len(design.SHEETS)} sheets: {len(design.PARTS)} parts, {n_pins} pins")


if __name__ == "__main__":
    main()
