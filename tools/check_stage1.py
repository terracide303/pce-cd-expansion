#!/usr/bin/env python3
"""Check the stage-1 schematic against the design and against the rules.

    python tools/check_stage1.py             # check hw/stage1/pce_exp_stage1.kicad_sch
    python tools/check_stage1.py --selftest  # first prove each check fires on a broken netlist

It does NOT trust the generator. It asks KiCad (kicad-cli) for the netlist of
the schematic as KiCad itself reads it, then checks that netlist:

  1. FIDELITY  every pin is on exactly the net hw/stage1/design.py says (catches a
               label that landed on the wrong pin, or two nets merged by touching pins)
  2. RULES     derived again, independently, from the two CSVs and the datasheets:
               the port pins, the Tang pins we may and may not use, every chip's
               supplies, translator directions, the decoder, 5 V never wired
               straight to the FPGA, every FPGA net point-to-point
  3. ERC       KiCad's electrical rule check: no errors, and only warnings on an
               explicit, reasoned allowlist
Exit 0 = all pass.
"""
import csv, json, os, pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCH = ROOT / "hw" / "stage1" / "pce_exp_stage1.kicad_sch"
sys.path.insert(0, str(ROOT / "hw" / "stage1"))
import design  # noqa: E402

KICAD_CLI = os.environ.get("KICAD_CLI", "kicad-cli")
fails: list[str] = []


def check(ok, msg):
    if not ok:
        fails.append(msg)


# ---------------------------------------------------------------- KiCad's view

def kicad_netlist(sch):
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "n.net"
        r = subprocess.run([KICAD_CLI, "sch", "export", "netlist", "--format", "kicadsexpr", "-o", str(out), str(sch)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if not out.exists():
            sys.exit(f"kicad-cli could not export the netlist:\n{r.stdout}{r.stderr}")
        text = out.read_text(encoding="utf-8")
    pins = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', text, re.S):
        name = m.group(1).lstrip("/")
        if name.startswith("unconnected-"):
            name = None
        for ref, pin in re.findall(r'\(node\s+\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', m.group(2)):
            pins[(ref, pin)] = name
    return pins


def kicad_erc(sch):
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "erc.json"
        subprocess.run([KICAD_CLI, "sch", "erc", "--format", "json", "--severity-all", "-o", str(out), str(sch)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
        data = json.loads(out.read_text(encoding="utf-8"))
    return [v for s in data["sheets"] for v in s["violations"]]


# ---------------------------------------------------------------- the checks

def check_fidelity(actual):
    for p in design.PARTS:
        if p["ref"].startswith("#"):
            continue
        for pin, net in p["pins"].items():
            got = actual.get((p["ref"], pin), None)
            check(got == net, f"FIDELITY {p['ref']}.{pin}: design says {net}, KiCad has {got}")


def nets(actual):
    out = {}
    for (ref, pin), net in actual.items():
        if net:
            out.setdefault(net, []).append((ref, pin))
    return out


def check_rules(actual):
    on = lambda ref, pin: actual.get((ref, pin))
    by_net = nets(actual)

    # The port, re-derived from the cross-checked pinout (not from design.py).
    used = {f"A{i}" for i in range(21)} | {f"D{i}" for i in range(8)} | {"/RD", "/WR"}
    for r in csv.DictReader(open(ROOT / "docs" / "ext_bus_pinout.csv", encoding="utf-8")):
        sig, got = r["signal"], on("J1", r["pin"])
        if sig in used:
            want = "BUS_" + sig.lstrip("/") + ("_N" if sig.startswith("/") else "")
            check(got == want, f"PORT {r['pin']} ({sig}) must be on {want}, is on {got}")
        elif sig in ("+5VA", "GND"):
            check(got == sig, f"PORT {r['pin']} ({sig}) must be on {sig}, is on {got}")
        else:
            check(got is None, f"PORT {r['pin']} ({sig}) is not used in stage 1 but is on {got}")

    # The Tang headers, from the header CSV.
    for r in csv.DictReader(open(ROOT / "docs" / "tang_nano_20k_header.csv", encoding="utf-8")):
        ref = "J2" if r["header_pos"].startswith("L") else "J3"
        got = on(ref, r["header_pos"][1:])
        tag = f"TANG {r['header_pos']} ({r['io_name']} {r['fpga_pin']})"
        if r["io_name"] == "5V":
            check(got is None, f"{tag}: the Tang's USB 5 V must not connect to anything, is on {got}")
        elif r["io_name"] == "3V3":
            check(got == "+3V3", f"{tag}: must be on +3V3, is on {got}")
        elif r["io_name"] == "GND":
            check(got == "GND", f"{tag}: must be on GND, is on {got}")
        elif got is not None:
            check(r["stage1_status"] in ("free", "usable", "unverified"),
                  f"{tag}: status '{r['stage1_status']}' ({r['why']}) but used for {got}")
            check(got.startswith("F_"), f"{tag}: an FPGA pin may only carry an F_ (3.3 V) net, carries {got}")

    # 5 V never reaches the FPGA directly.
    for net, nodes in by_net.items():
        refs = {r for r, _ in nodes}
        if net == "GND":
            continue          # the one net that must be shared: the two boards' common ground
        check(not ({"J2", "J3"} & refs and "J1" in refs), f"5V->FPGA: net {net} joins the console port straight to the Tang")

    # Every FPGA net is point to point: one Tang pin and one driver/resistor.
    for net, nodes in by_net.items():
        if net.startswith("F_"):
            tang = [n for n in nodes if n[0] in ("J2", "J3")]
            check(len(tang) == 1 and len(nodes) == 2, f"F-NET {net}: expected one Tang pin + one translator/resistor pin, got {nodes}")

    # Supplies.
    for ref, pin, want in [("U1", "20", "+5VA"), ("U1", "10", "GND"), ("U2", "1", "+5VA"), ("U2", "23", "+3V3"),
                           ("U2", "24", "+3V3"), ("U2", "11", "GND")] + \
                          [(u, "20", "+3V3") for u in ("U3", "U4", "U5")] + [(u, "10", "GND") for u in ("U3", "U4", "U5")]:
        check(on(ref, pin) == want, f"SUPPLY {ref}.{pin} must be {want}, is {on(ref, pin)}")

    # The data translator: A side = bus (VCCA 5 V), DIR = /RD, /OE = our select.
    check(on("U2", "2") == "BUS_RD_N", f"DIR U2.2 must be BUS_RD_N (FPGA drives only while /RD is low), is {on('U2', '2')}")
    check(on("U2", "22") == "SEL_N", f"/OE U2.22 must be SEL_N (only our banks), is {on('U2', '22')}")
    for i in range(8):
        check(on("U2", str(3 + i)) == f"BUS_D{i}", f"U2 A{i + 1} must be BUS_D{i}, is {on('U2', str(3 + i))}")
        check(on("U2", str(21 - i)) == f"T_D{i}", f"U2 B{i + 1} must be T_D{i}, is {on('U2', str(21 - i))}")

    # The input translators: fixed A->B (bus to FPGA), always enabled.
    for u in ("U3", "U4", "U5"):
        check(on(u, "1") == "+3V3", f"DIR {u}.1 must be +3V3 (A->B, bus to FPGA), is {on(u, '1')}")
        check(on(u, "19") == "GND", f"/OE {u}.19 must be GND (always on), is {on(u, '19')}")
        for i in range(8):
            a, b = on(u, str(2 + i)), on(u, str(18 - i))
            check(a is not None, f"{u} A{i + 1} is floating (a floating CMOS input oscillates)")
            check(a in (None, "GND", "SEL_N") or a.startswith("BUS_"), f"{u} A{i + 1} (bus side) carries {a}")
            check(b is None or b.startswith("F_"), f"{u} B{i + 1} (FPGA side) carries {b}")

    # The decoder: P=R low exactly for A20..A16 = 1 0000.
    for i, pin in enumerate(["2", "4", "6", "8", "11"]):
        check(on("U1", pin) == f"BUS_A{16 + i}", f"DECODE U1.{pin} (P{i}) must be BUS_A{16 + i}, is {on('U1', pin)}")
    for pin, want in [("3", "GND"), ("5", "GND"), ("7", "GND"), ("9", "GND"), ("12", "+5VA"), ("1", "GND"), ("19", "SEL_N")]:
        check(on("U1", pin) == want, f"DECODE U1.{pin} must be {want}, is {on('U1', pin)}")
    for p_, r_ in [("13", "14"), ("15", "16"), ("17", "18")]:
        check(on("U1", p_) == on("U1", r_), f"DECODE unused P/R pair U1.{p_}/{r_} must be equal")


# Warnings we accept, each with its reason. Anything else fails.
ERC_ALLOWED = {
    "lib_symbol_issues": "kicad-cli has no global symbol table; the symbols are embedded in the schematic",
    "footprint_link_issues": "kicad-cli has no global footprint table; resolved when the board is opened in KiCad",
}


def check_erc(violations):
    for v in violations:
        kind = v["type"]
        if v["severity"] == "error":
            check(False, f"ERC error {kind}: {v['description']}")
        elif kind == "pin_to_pin" and all("U5" in i["description"] or "FLG" in i["description"] for i in v.get("items", [])):
            continue          # U5's unused inputs tied to GND, which carries a PWR_FLAG: intended
        elif kind not in ERC_ALLOWED:
            check(False, f"ERC warning {kind}: {v['description']} {[i['description'] for i in v.get('items', [])]}")


# ---------------------------------------------------------------- selftest

def selftest(actual):
    def mutated(fn):
        a = dict(actual)
        fn(a)
        return a

    def merge(a, x, y):          # every pin on net y moves to net x
        for k, v in list(a.items()):
            if v == y:
                a[k] = x

    cases = [
        ("two port pins swapped (A0 <-> A1)", lambda a: a.update({("J1", "b12"): "BUS_A1", ("J1", "c13"): "BUS_A0"})),
        ("two nets merged by touching pins (F_D0 + T_D1)", lambda a: merge(a, "F_D0", "T_D1")),
        ("data translator VCCA on 3.3 V", lambda a: a.update({("U2", "1"): "+3V3"})),
        ("an input translator turned round (DIR low)", lambda a: a.update({("U3", "1"): "GND"})),
        ("a 5 V bus line wired straight to the Tang", lambda a: a.update({("J3", "5"): "BUS_A0"})),
        ("a kept pin used (WS2812 pin 79)", lambda a: a.update({("J3", "14"): "F_A0"})),
        ("the Tang's USB 5 V tied to +5VA", lambda a: a.update({("J3", "1"): "+5VA"})),
        ("decoder looking at the wrong address line", lambda a: a.update({("U1", "11"): "BUS_A15"})),
        ("an unused translator input left floating", lambda a: a.update({("U5", "9"): None})),
    ]
    print("SELFTEST -- each line must say CAUGHT")
    ok = True
    # Only failures the mutation ADDS count: a board that already fails must not
    # make every case look caught.
    fails.clear()
    check_rules(actual)
    check_fidelity(actual)
    baseline = set(fails)
    if baseline:
        print(f"  (the board already has {len(baseline)} failure(s); only NEW failures count below)")
    for label, fn in cases:
        fails.clear()
        a = mutated(fn)
        check_rules(a)
        check_fidelity(a)
        new = [f for f in fails if f not in baseline]
        got = bool(new)
        ok &= got
        print(f"  {'CAUGHT' if got else 'MISSED'}  {label}" + (f"\n            -> {new[0]}" if got else ""))
    fails.clear()
    print()
    return ok


def main():
    actual = kicad_netlist(SCH)
    if "--selftest" in sys.argv and not selftest(actual):
        sys.exit("SELFTEST FAILED -- a check did not fire")
    check_fidelity(actual)
    check_rules(actual)
    check_erc(kicad_erc(SCH))
    n = len([1 for k in actual if not k[0].startswith("#")])
    print(f"checked {SCH.relative_to(ROOT).as_posix()}: {n} pins, {len(nets(actual))} nets, as KiCad reads it")
    if fails:
        print(f"\n{len(fails)} FAILURE(S):")
        for f in fails:
            print("  FAIL ", f)
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
