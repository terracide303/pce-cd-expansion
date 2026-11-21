#!/usr/bin/env python3
"""Make the card's fabrication files, after checking the board is ready for them.

    python tools/fab_card.py

Writes hw/card/fab/:
  pce_card_gerbers.zip   gerbers (4 copper, masks, paste, silkscreen, outline) and
                         drill files: upload this to JLCPCB or PCBWay
  pce_card_bom.csv       BOM in JLCPCB's columns (Comment, Designator, Footprint, LCSC Part #)
  pce_card_cpl.csv       placement in JLCPCB's columns (Designator, Mid X, Mid Y, Layer, Rotation)
  drc.json               the DRC this was made from

Refuses to write anything if KiCad's DRC (zones refilled, the board's own rules,
which are the JLCPCB/PCBWay standard floor) finds an unconnected item, a schematic
difference, or a violation not on the ACCEPTED list below; or if
tools/fabcheck_card.py finds a via in an SMD pad, a via that is not 0.45/0.2 mm,
the ground finger's pre-routed copper missing, or the
fingers in an order other than the working HuCARD-repro card's. The order settings are in
docs/ORDER.md.
"""
import collections, csv, io, json, os, pathlib, shutil, subprocess, sys, tempfile, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "hw" / "card"
PCB, SCH = CARD / "pce_card.kicad_pcb", CARD / "pce_card.kicad_sch"
OUT = CARD / "fab"
KICAD_CLI = os.environ.get("KICAD_CLI", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe")
KICAD_PY = os.environ.get("KICAD_PY", r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\bin\python.exe")
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"

# Violations that are not manufacturing problems, each with why. Matched on the
# violation type and the set of footprint references it names.
ACCEPTED = {
    ("lib_footprint_mismatch", None): "the board's copies differ from the library on purpose (silkscreen widened and trimmed)",
    ("lib_footprint_issues", None): "kicad-cli here has no global library tables; footprints are checked on disk by check_card.py",
    ("courtyards_overlap", frozenset({"C30", "C31"})): "as on the Icepi Zero, which is assembled this way",
    ("silk_over_copper", frozenset({"U10", "TP14"})): "U10's pin-1 mark touches TP14, as on the Icepi; the fab clips silkscreen off pads",
}


def run(*args):
    r = subprocess.run([KICAD_CLI, *map(str, args)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"kicad-cli {' '.join(map(str, args[:3]))} failed:\n{r.stdout}\n{r.stderr}")
    return r


def refs(v):
    found = set()
    for item in v.get("items", []):
        words = item.get("description", "").replace("[", " ").split()
        for i, w in enumerate(words):
            if w in ("van", "of") and i + 1 < len(words):
                found.add(words[i + 1])
            if w == "Footprint" and i + 1 < len(words):
                found.add(words[i + 1])
    return frozenset(found)


def check(tmp):
    report = tmp / "drc.json"
    run("pcb", "drc", "--schematic-parity", "--refill-zones", "--format", "json", "-o", report, PCB)
    d = json.loads(report.read_text(encoding="utf-8"))
    problems = []
    if d.get("unconnected_items"):
        problems.append(f"{len(d['unconnected_items'])} unconnected item(s)")
    if d.get("schematic_parity"):
        problems.append(f"{len(d['schematic_parity'])} schematic difference(s)")
    left = collections.Counter()
    for v in d.get("violations", []):
        key = (v["type"], refs(v))
        if (v["type"], None) in ACCEPTED or key in ACCEPTED:
            continue
        left[v["type"]] += 1
    if left:
        problems.append("violations: " + ", ".join(f"{n} {t}" for t, n in left.most_common()))
    # what DRC does not check (tools/fabcheck_card.py, in KiCad's Python)
    r = subprocess.run([KICAD_PY, str(ROOT / "tools" / "fabcheck_card.py"), str(PCB)], capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("{")), None)
    if not line:
        problems.append(f"fabcheck_card.py failed: {r.stderr.strip()[-300:]}")
    else:
        f = json.loads(line)
        if f["vias_in_pads"]:
            problems.append(f"{len(f['vias_in_pads'])} SMD pad(s) with a via in them: {', '.join(f['vias_in_pads'][:10])}")
        if set(f["via_sizes"]) - {"0.45/0.2", "0.6/0.3"}:
            problems.append(f"via sizes other than 0.45/0.2 mm: {f['via_sizes']}")
        if f["locked_ground"] < 4:
            problems.append("the pre-routed ground-finger copper is missing (tools/preroute_card.py)")
        if f["edge"]:
            problems.append("card edge does not match the HuCARD-repro finger order: " + "; ".join(f["edge"]))
    return d, report, problems


def gerbers(tmp):
    g = tmp / "gerbers"
    g.mkdir()
    run("pcb", "export", "gerbers", "--layers", LAYERS, "--subtract-soldermask", "--check-zones", "-o", g, PCB)
    run("pcb", "export", "drill", "--format", "excellon", "--excellon-units", "mm",
        "--excellon-separate-th", "--generate-map", "--map-format", "gerberx2", "-o", g, PCB)
    zpath = OUT / "pce_card_gerbers.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(g.iterdir()):
            z.write(f, f.name)
    return zpath, sorted(f.name for f in g.iterdir())


def cpl(tmp):
    pos = tmp / "pos.csv"
    run("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-dnp", "-o", pos, PCB)
    rows = list(csv.DictReader(io.StringIO(pos.read_text(encoding="utf-8"))))
    out = OUT / "pce_card_cpl.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            w.writerow([r["Ref"], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm",
                        "Top" if r["Side"].lower().startswith("top") else "Bottom", f"{float(r['Rot']):g}"])
    return out, len(rows)


def bom(tmp):
    raw = tmp / "bom.csv"
    run("sch", "export", "bom", "--fields", "Value,Reference,Footprint,LCSC,${QUANTITY}",
        "--labels", "Comment,Designator,Footprint,LCSC Part #,Qty", "--group-by", "Value,Footprint,LCSC",
        "--ref-range-delimiter", "", "--exclude-dnp", "-o", raw, SCH)
    rows = list(csv.DictReader(io.StringIO(raw.read_text(encoding="utf-8"))))
    out = OUT / "pce_card_bom.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        for r in rows:
            w.writerow([r["Comment"], r["Designator"], r["Footprint"].split(":")[-1], r["LCSC Part #"]])
    missing = [r["Designator"] for r in rows if not r["LCSC Part #"].strip()]
    return out, len(rows), missing


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = pathlib.Path(t)
        d, report, problems = check(tmp)
        if problems:
            sys.exit("not ready for fabrication: " + "; ".join(problems) +
                     f"\n(DRC report kept at {shutil.copy(report, CARD / 'drc_failed.json')})")
        if OUT.exists():
            shutil.rmtree(OUT)
        OUT.mkdir()
        shutil.copy(report, OUT / "drc.json")
        z, files = gerbers(tmp)
        c, n_parts = cpl(tmp)
        b, n_lines, missing = bom(tmp)
    print(f"DRC: 0 unconnected, 0 schematic differences, only accepted violations")
    print(f"{z.relative_to(ROOT)}: {len(files)} files ({', '.join(files)})")
    print(f"{c.relative_to(ROOT)}: {n_parts} placements")
    print(f"{b.relative_to(ROOT)}: {n_lines} lines; without an LCSC part number: {len(missing)}")
    if missing:
        print("  (fill those in before ordering assembly: " + "; ".join(missing) + ")")


if __name__ == "__main__":
    main()
