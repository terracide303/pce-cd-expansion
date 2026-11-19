#!/usr/bin/env python3
"""Check the card schematic: KiCad's own netlist against the design, against the
working Icepi Zero, and against the card's electrical rules. Then ERC.

    python tools/check_card.py              # all checks
    python tools/check_card.py --selftest   # first prove each check catches a planted fault

1. FIDELITY  every part and pin in KiCad's netlist is what hw/card/design.py says.
2. ICEPI     every kept Icepi part is connected exactly as on the Icepi Zero v1.4
             (the owner has one working, with the 45F), except the documented
             changes: dropped parts, the +5V rename, J5's VBUS, the freed FPGA balls.
3. RULES     derived independently of design.py where possible:
             - the card edge matches docs/hucard_pinout.csv;
             - no console (5 V) net touches the FPGA;
             - every console input reaches exactly one FPGA ball through a translator;
             - the data translator cannot drive the bus while the FPGA is unconfigured
               (/OE pulled up, DIR pulled toward the FPGA), IRQ likewise;
             - the console's 5 V and the USB VBUS lines meet only through diodes;
             - every FPGA I/O bank is at 3.3 V.
4. ERC       kicad-cli's electrical rules check, with a short allowlist.
"""
import collections, copy, csv, json, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CARD = ROOT / "hw" / "card"
sys.path.insert(0, str(CARD))
import design  # noqa: E402

KICAD_CLI = pathlib.Path(r"C:\Users\terra\AppData\Local\Programs\KiCad\10.0\bin\kicad-cli.exe")
KICAD_FP = KICAD_CLI.parent.parent / "share" / "kicad" / "footprints"
SCH = CARD / "pce_card.kicad_sch"


def kicad_netlist():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "card.net"
        subprocess.run([str(KICAD_CLI), "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(SCH)],
                       check=True, capture_output=True)
        return design.load_netlist(out)


def pin_map(nets):
    return {(r, p): n for n, nodes in nets.items() for r, p in nodes}


# ---------------------------------------------------------------- 1. fidelity
def check_fidelity(comps, nets):
    problems = []
    want = {p["ref"]: p for p in design.PARTS if not p["ref"].startswith("#")}
    for ref in sorted(set(want) - set(comps)):
        problems.append(f"{ref} missing from KiCad's netlist")
    for ref in sorted(set(comps) - set(want)):
        problems.append(f"{ref} in KiCad's netlist but not in the design")
    pm = pin_map(nets)
    for ref, p in want.items():
        if ref not in comps:
            continue
        if comps[ref]["value"] != p["value"]:
            problems.append(f"{ref}: value {comps[ref]['value']!r}, design {p['value']!r}")
        if comps[ref]["footprint"] != p["fp"]:
            problems.append(f"{ref}: footprint {comps[ref]['footprint']!r}, design {p['fp']!r}")
        for pin, net in p["pins"].items():
            got = pm.get((ref, pin))
            got = None if got is None or got.startswith("unconnected-") else got.lstrip("/")
            if got != net:
                problems.append(f"{ref}.{pin}: KiCad has {got}, design says {net}")
    return problems


# ---------------------------------------------------------------- 2. the Icepi
def check_icepi(nets):
    """Partition equality on kept Icepi pins, outside the documented changes."""
    problems = []
    changed = ({("U1", b) for b in design.FREED} | set(design.PIN_OVERRIDE)
               | {(r, pin) for r, (_, ren) in design.SYMBOL_SWAP.items() for kv in ren.items() for pin in kv})
    kept = {r for r in design.ICEPI_COMPS if r not in design.DROP}
    card = {k: v.lstrip("/") for k, v in pin_map(nets).items()}
    for inet, nodes in design.ICEPI_NETS.items():
        if inet.startswith("unconnected-"):
            continue
        pins = {(r, p) for r, p in nodes if r in kept and (r, p) not in changed}
        if not pins:
            continue
        cnets = {card.get(rp) for rp in pins}
        if len(cnets) != 1 or None in cnets:
            problems.append(f"Icepi net {inet}: its pins are split over {sorted(map(str, cnets))} on the card")
            continue
        cnet = cnets.pop()
        cpins = {(r, p) for r, p in nets.get("/" + cnet, nets.get(cnet, [])) if r in kept and (r, p) not in changed}
        if cpins != pins:
            extra = sorted(cpins - pins)[:6]
            problems.append(f"Icepi net {inet} -> card {cnet}: Icepi pins also joined: {extra}")
    for r, (_, ren) in design.SYMBOL_SWAP.items():
        for a, b in ren.items():
            inet = next((n for n, nodes in design.ICEPI_NETS.items() if (r, a) in nodes), None)
            if inet and not inet.startswith("unconnected-") and card.get((r, b)) != design._card_net(inet):
                problems.append(f"{r}.{b} (Icepi pin {a}) is {card.get((r, b))}, Icepi had {inet}")
    # the freed balls really were header / GPDI / soft-USB on the Icepi
    for ball in design.FREED:
        inet = next((n for n, nodes in design.ICEPI_NETS.items() if ("U1", ball) in nodes), "")
        if not re.search(r"GPIO\d+$|/GPDI/|USB\d_PULL|/D[01][+-]$", inet):
            problems.append(f"U1.{ball} is freed for the card, but on the Icepi it is {inet!r}")
    return problems


# ---------------------------------------------------------------- 3. rules
HUCARD = list(csv.DictReader(open(ROOT / "docs" / "hucard_pinout.csv", encoding="utf-8")))
CONSOLE_POWER = {"+5V_CON", "+5V_CARD", "VBUS_FT", "VBUS_RP"}


def check_rules(comps, nets):
    problems = []
    card = {k: v.lstrip("/") for k, v in pin_map(nets).items()}
    bynet = collections.defaultdict(set)
    for (r, p), n in card.items():
        bynet[n].add((r, p))

    # the edge, derived here from the CSV (not from design.py)
    for row in HUCARD:
        s = row["signal"]
        want = {"GND": "GND", "+5V": "+5V_CON", "/CD": "GND", "AUDIO_IN": "BUS_AUDIO"}.get(
            s, "BUS_" + s.replace("/", "") + ("_N" if s.startswith("/") else ""))
        if card.get(("J101", row["pin"])) != want:
            problems.append(f"J101.{row['pin']} ({s}) is {card.get(('J101', row['pin']))}, expected {want}")

    # no console net on the FPGA
    for (r, p), n in card.items():
        if r == "U1" and (n.startswith("BUS_") or n in CONSOLE_POWER):
            problems.append(f"U1.{p} is on {n}: a 5 V console net on the FPGA")

    # every console input reaches exactly one FPGA ball, through one translator
    for row in HUCARD:
        s = row["signal"]
        if s in ("GND", "+5V", "/CD", "AUDIO_IN", "/IRQ2") or s.startswith("D"):
            continue
        bus = "BUS_" + s.replace("/", "") + ("_N" if s.startswith("/") else "")
        f = "F_" + bus[4:]
        tr = {r for r, _ in bynet[bus]} - {"J101", "TP101", "TP102", "TP103", "TP104"}
        if len(tr) != 1 or not re.match(r"U10[1-4]$", next(iter(tr))):
            problems.append(f"{bus} reaches {sorted(tr)}, expected one input translator")
        balls = [p for r, p in bynet[f] if r == "U1"]
        if len(balls) != 1:
            problems.append(f"{f} reaches FPGA balls {balls}, expected exactly one")
        if not ({r for r, _ in bynet[f]} & tr):
            problems.append(f"{f} is not on the same translator as {bus}")
    for i in range(8):
        if not any(r == "U1" for r, _ in bynet[f"F_D{i}"]) or ("U105", str(3 + i)) not in bynet[f"F_D{i}"]:
            problems.append(f"F_D{i}: not FPGA <-> U105 A{i + 1}")
        r = [x for x, _ in bynet[f"BUS_D{i}"] if x.startswith("R")]
        if len(r) != 1 or ((r[0], "1") not in bynet[f"T_D{i}"] and (r[0], "2") not in bynet[f"T_D{i}"]):
            problems.append(f"BUS_D{i}: no single series resistor to the translator")

    # unconfigured FPGA = card off the bus
    def pulled(net, rail):
        for r, p in bynet[net]:
            if comps.get(r, {}).get("part") == "R":
                other = card.get((r, "2" if p == "1" else "1"))
                if other == rail:
                    return True
        return False
    if card.get(("U105", "22")) != "F_DOE_N" or not pulled("F_DOE_N", "+3V3"):
        problems.append("U105 /OE (pin 22) is not pulled up to +3V3: an unconfigured FPGA could enable the data bus")
    if card.get(("U105", "2")) != "F_DDIR" or not pulled("F_DDIR", "GND"):
        problems.append("U105 DIR (pin 2) is not pulled down: an unconfigured FPGA could point the data bus at the console")
    if card.get(("U105", "1")) != "+3V3" or card.get(("U105", "23")) != "+5V_CON" or card.get(("U105", "24")) != "+5V_CON":
        problems.append("U105 supplies: VCCA must be +3V3 (FPGA side), VCCB the console's +5V_CON")
    if not pulled("F_IRQ2_N", "+3V3"):
        problems.append("F_IRQ2_N is not pulled up: an unconfigured FPGA could raise IRQ2")

    # power: console 5 V and USB meet only through diodes; the console's 5 V feeds only bus parts
    for src in ("+5V_CON", "VBUS_FT", "VBUS_RP"):
        diodes = [r for r, p in bynet[src] if r.startswith("D") and p == "2"]
        if len(diodes) != 1 or card.get((diodes[0], "1")) != "+5V_CARD":
            problems.append(f"{src} does not reach +5V_CARD through exactly one diode (anode on {src})")
    for r, p in bynet["+5V_CON"]:
        if not (r in ("J101", "U105") or r.startswith(("C", "D", "#"))):
            problems.append(f"{r}.{p} on +5V_CON: only the edge, the data translator, diodes and capacitors belong there")

    # FPGA banks at 3.3 V
    for (r, p), n in card.items():
        if r == "U1" and p in design_vccio():
            if n != "+3V3":
                problems.append(f"U1.{p} (VCCIO) is {n}, expected +3V3")
    return problems


def design_vccio():
    sym = (CARD / "reference" / "icepi-zero-v1.4" / "icepi-embedded.kicad_sym").read_text(encoding="utf-8")
    return set(re.findall(r'\(name "VCCIO\d+[^"]*".*?\(number "([A-Z]+\d+)"', sym, re.S))


def check_footprints():
    problems = []
    libs = {"pce_card": CARD / "pce_card.pretty", "icepi-lib": CARD / "reference" / "icepi-zero-v1.4" / "icepi-lib.pretty"}
    for p in design.PARTS:
        if not p["fp"]:
            continue
        lib, name = p["fp"].split(":", 1)
        d = libs.get(lib, KICAD_FP / f"{lib}.pretty")
        f = d / f"{name}.kicad_mod"
        if not f.exists():
            problems.append(f"{p['ref']}: footprint {p['fp']} not found")
            continue
        pads = {x for x in re.findall(r'\(pad "([^"]*)"', f.read_text(encoding="utf-8")) if x}
        if set(p["pins"]) - pads:
            problems.append(f"{p['ref']}: pins {sorted(set(p['pins']) - pads)} have no pad in {p['fp']}")
    return problems


# ---------------------------------------------------------------- 4. ERC
ERC_ALLOW = {
    "pin_not_driven",            # bus inputs are driven from the card edge (passive connector pins)
    "power_pin_not_driven",      # rails enter through connectors and diodes; PWR_FLAGs mark them
    "lib_symbol_mismatch",       # vendored Icepi symbols are embedded copies, by design
    # The two below only say kicad-cli on this PC has no global library tables; every
    # footprint is checked to exist on disk by check_footprints() instead.
    "lib_symbol_issues",
    "footprint_link_issues",
    "global_label_dangling",
}


def run_erc():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "erc.json"
        subprocess.run([str(KICAD_CLI), "sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(SCH)],
                       capture_output=True)
        data = json.loads(out.read_text(encoding="utf-8"))
    counts = collections.Counter()
    shown = []
    for sheet in data.get("sheets", []):
        for v in sheet.get("violations", []):
            counts[(v["type"], v["severity"])] += 1
            if v["type"] not in ERC_ALLOW and len(shown) < 12:
                shown.append(f"{v['type']} ({v['severity']}): {v['description']} @ "
                             + "; ".join(i.get("description", "") for i in v.get("items", []))[:160])
    return counts, shown


# ---------------------------------------------------------------- self-test
def selftest(comps, nets):
    base = set(check_icepi(nets) + check_rules(comps, nets))

    def mutated(fn):
        n = copy.deepcopy(nets)
        fn(n)
        return set(check_icepi(n) + check_rules(comps, n)) - base

    def move(n, ref, pin, to):
        for k in list(n):
            n[k] = [x for x in n[k] if x != (ref, pin)]
        n.setdefault(to, []).append((ref, pin))

    def swap(n, a, b):
        na = next(k for k, v in n.items() if a in v)
        nb = next(k for k, v in n.items() if b in v)
        move(n, *a, nb); move(n, *b, na)

    cases = [
        ("SDRAM data lines swapped (Icepi fidelity)", lambda n: swap(n, ("U11", "2"), ("U11", "4"))),
        ("config flash CS moved (Icepi fidelity)", lambda n: move(n, "U12", "1", "/GND")),
        ("data translator /OE pull-up removed", lambda n: move(n, "R101", "2", "/GND")),
        ("DIR pulled up instead of down", lambda n: move(n, "R102", "2", "/+3V3")),
        ("a console address line on the FPGA", lambda n: move(n, "U1", "G3", "/BUS_A0")),
        ("card edge A0/A1 swapped", lambda n: swap(n, ("J101", "13"), ("J101", "14"))),
        ("USB VBUS shorted to the console's 5 V", lambda n: move(n, "J102", "A4", "/+5V_CON")),
        ("translator powered from the card rail", lambda n: move(n, "U105", "23", "/+5V_CARD")),
        ("FPGA bank at 2.5 V", lambda n: move(n, "U1", "F6", "/+2V5")),
    ]
    ok = True
    print("SELFTEST -- each line must say CAUGHT")
    for label, fn in cases:
        got = bool(mutated(fn)); ok &= got
        print(f"  {'CAUGHT' if got else 'MISSED'}  {label}")
    return ok


def main():
    comps, nets = kicad_netlist()
    if "--selftest" in sys.argv:
        if not selftest(comps, nets):
            sys.exit("SELFTEST FAILED")
        print()
    results = [("fidelity: KiCad netlist = hw/card/design.py", check_fidelity(comps, nets)),
               ("icepi: core wired as the working Icepi Zero v1.4", check_icepi(nets)),
               ("rules: edge, 5 V isolation, safe defaults, power, banks", check_rules(comps, nets)),
               ("footprints exist, every pin has a pad", check_footprints())]
    failed = False
    for name, probs in results:
        print(f"{'PASS' if not probs else 'FAIL'}  {name}" + (f"  ({len(probs)})" if probs else ""))
        for p in probs[:15]:
            print("       ", p)
        failed |= bool(probs)
    counts, shown = run_erc()
    bad = {k: v for k, v in counts.items() if k[0] not in ERC_ALLOW}
    print(f"{'PASS' if not bad else 'FAIL'}  ERC: " + ", ".join(f"{t}/{s} x{c}" for (t, s), c in sorted(counts.items())))
    for s in shown:
        print("       ", s)
    failed |= bool(bad)
    pins = sum(len(v) for v in nets.values())
    print(f"\n{'ALL CHECKS PASSED' if not failed else 'CHECKS FAILED'}: {len(comps)} parts, {pins} pins, {len(nets)} nets")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
