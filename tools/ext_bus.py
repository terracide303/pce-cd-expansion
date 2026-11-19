#!/usr/bin/env python3
"""The PC Engine rear expansion port (EXT BUS), as data, cross-checked between two sources.

    python tools/ext_bus.py            # check the two sources agree, write docs/ext_bus_pinout.csv
    python tools/ext_bus.py --selftest # prove the check catches a wrong pin first

ONE SOURCE OF TRUTH. docs/ext_bus_pinout.csv is GENERATED here and every later
step (pin budget, schematic generator, board checker) reads that file. Nobody
types a pin number twice.

TWO SOURCES, BOTH COMMITTED:
  A. docs/datasheets/PC_Engine_Schematics_r1.2.pdf, sheet 5, connector CN102
     "Expansion" (KiCad 7 redraw, "adapted from TurboGrafx-16 schematics by
     Cosam, differences reverse engineered from original PWD-623A board").
     Transcribed below by eye from 400 dpi crops in docs/datasheets/evidence/.
  B. docs/datasheets/pcedev-wiki-EXT_BUS_pinout-2026-11-19.txt, the PCEdev
     wiki's table, parsed straight from the committed text.

Physical orientation (source B): looking into the back of the console, AV/RF
port up, power jack down, card slot away from you. The wiki's left / middle /
right columns are the schematic's rows a / b / c; its 23 table rows are pin
numbers 1..23. Neither source is a measurement of a real console: a continuity
check on the actual PC Engine is still required before any board is ordered.
"""
import csv, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WIKI = ROOT / "docs" / "datasheets" / "pcedev-wiki-EXT_BUS_pinout-2026-11-19.txt"
OUT = ROOT / "docs" / "ext_bus_pinout.csv"

# Source A, transcribed from the schematic. Names as printed there.
SCHEMATIC = {
    "a": ["AUDIO-L", "+5VA", "CESEL", "A18", "A14", "A9", "A10", "D6", "DCK", "XVSYNC", "EXTPOW", "VD8",
          "VD7", "EXTPOW", "VD5", "VD4", "VD3", "VD2", "VD1", "VD0", "GNDA", "COMPV", "VIDEOR"],
    "b": ["AUDIO-C", "XB", "HSM", "WR", "XNMI", "A8", "RD", "D7", "D4", "D2", "XHSYNC", "A0",
          "A2", "VD6", "A5", "A7", "A12", "A16", "A20", "RDY", "XIRQ2", "XRESET", "VIDEOG"],
    "c": ["AUDIO-R", "GNDA", "XCARD", "CEK", "A17", "A13", "A11", "SHIELD", "D5", "D3", "D1", "D0",
          "A1", "A3", "A4", "A6", "SHIELD", "A15", "A19", "SHIELD", "+5VA", "SYNCV", "VIDEOB"],
}

# The two sources name some signals differently. Each alias maps a schematic
# name to the wiki's name and to the canonical name used everywhere downstream.
#            schematic   wiki        canonical   why the names differ
ALIASES = {
    "AUDIO-L": ("AudioL", "AUDIO_L", ""), "AUDIO-C": ("AudioC", "AUDIO_C", ""), "AUDIO-R": ("AudioR", "AUDIO_R", ""),
    "+5VA": ("+5A", "+5VA", "analog 5 V for the VCE and video amp; NOT a digital supply"),
    "GNDA": ("0VAG", "GNDA", "analog ground"),
    "SHIELD": ("GND", "GND", "schematic: 'shield on underside connects these pins to ground'"),
    "XB": ("K7", "K7", "schematic net XB = HuC6280 port K7 (CPU pin 8); CD-unit presence detect"),
    "XCARD": ("/CARD", "/CARD", "to HuCard slot pin 1; pulled up in console, grounded by a HuCard"),
    "WR": ("/WR", "/WR", ""), "RD": ("/RD", "/RD", ""), "XNMI": ("/NMI", "/NMI", ""),
    "CEK": ("/CEK", "/CEK", "CPU asserts when addressing the VCE"),
    "XVSYNC": ("/VSYNC", "/VSYNC", ""), "XHSYNC": ("/HSYNC", "/HSYNC", ""),
    "EXTPOW": ("EXTPGW", "EXTPOW", "wiki typo; unregulated ~9 V INTO the console from an expansion unit"),
    "XIRQ2": ("/IRQ2", "/IRQ2", ""), "XRESET": ("/RESET", "/RESET", ""),
    "COMPV": ("CompV", "COMPV", ""), "SYNCV": ("CSync", "CSYNC", "composite sync, 5 V levels"),
    "VIDEOR": ("VideoR", "VIDEO_R", ""), "VIDEOG": ("VideoG", "VIDEO_G", ""), "VIDEOB": ("VideoB", "VIDEO_B", ""),
}


def canonical(sch_name):
    return ALIASES[sch_name][1] if sch_name in ALIASES else sch_name


def wiki_name_for(sch_name):
    return ALIASES[sch_name][0] if sch_name in ALIASES else sch_name


def parse_wiki(text):
    """The wiki's MediaWiki table: 23 rows of 'left || middle || right'."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("|") and "||" in line and not line.startswith("|-") and not line.startswith("{|"):
            cells = [c.strip() for c in line.lstrip("|").split("||")]
            if len(cells) == 3:
                rows.append(cells)
    return rows


def compare(schematic, wiki_rows):
    problems = []
    if len(wiki_rows) != 23:
        problems.append(f"wiki table has {len(wiki_rows)} rows, expected 23")
    for row in "abc":
        if len(schematic[row]) != 23:
            problems.append(f"schematic row {row} has {len(schematic[row])} pins, expected 23")
    if problems:
        return problems          # the per-pin comparison below needs both to be complete
    for i, cells in enumerate(wiki_rows):
        for col, row in zip(cells, "abc"):
            sch = schematic[row][i]
            if wiki_name_for(sch) != col:
                problems.append(f"{row}{i + 1}: schematic says {sch} (= wiki {wiki_name_for(sch)}), wiki says {col}")
    # every bus signal exactly once
    names = [canonical(n) for r in "abc" for n in schematic[r]]
    for want in [f"A{i}" for i in range(21)] + [f"D{i}" for i in range(8)] + [f"VD{i}" for i in range(9)] + ["/RD", "/WR", "/RESET", "/IRQ2", "RDY"]:
        if names.count(want) != 1:
            problems.append(f"{want} appears {names.count(want)} times, expected once")
    return problems


def selftest(wiki_rows):
    import copy
    cases = []
    s = copy.deepcopy(SCHEMATIC); s["b"][11], s["c"][12] = s["c"][12], s["b"][11]; cases.append(("A0 and A1 swapped", s))
    s = copy.deepcopy(SCHEMATIC); s["c"][11] = "D1"; cases.append(("D0 misread as D1", s))
    s = copy.deepcopy(SCHEMATIC); s["a"].pop(); cases.append(("a row one pin short", s))
    w = [r[:] for r in wiki_rows]; w[19][1] = "GND"
    ok = True
    print("SELFTEST -- each line must say CAUGHT")
    for label, sch in cases:
        got = bool(compare(sch, wiki_rows)); ok &= got
        print(f"  {'CAUGHT' if got else 'MISSED'}  {label}")
    got = bool(compare(SCHEMATIC, w)); ok &= got
    print(f"  {'CAUGHT' if got else 'MISSED'}  the wiki side changed (RDY -> GND)")
    return ok


def main():
    wiki_rows = parse_wiki(WIKI.read_text(encoding="utf-8"))
    if "--selftest" in sys.argv:
        if not selftest(wiki_rows):
            sys.exit("SELFTEST FAILED")
        print()
    problems = compare(SCHEMATIC, wiki_rows)
    if problems:
        print(f"{len(problems)} DISAGREEMENT(S) between the schematic and the wiki:")
        for p in problems:
            print("  FAIL ", p)
        sys.exit(1)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pin", "row", "number", "signal", "schematic_name", "wiki_name", "note"])
        for row in "abc":
            for i, sch in enumerate(SCHEMATIC[row]):
                w.writerow([f"{row}{i + 1}", row, i + 1, canonical(sch), sch, wiki_name_for(sch), ALIASES.get(sch, ("", "", ""))[2]])
    print(f"schematic and wiki agree on all 69 pins; wrote {OUT.relative_to(ROOT).as_posix()}")


if __name__ == "__main__":
    main()
