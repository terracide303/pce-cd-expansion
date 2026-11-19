#!/usr/bin/env python3
"""The HuCard slot, as data, parsed from the one committed source.

    python tools/hucard_bus.py            # check the slot is complete, write docs/hucard_pinout.csv
    python tools/hucard_bus.py --selftest # prove the checks catch a wrong pin first

ONE SOURCE OF TRUTH. docs/hucard_pinout.csv is GENERATED here; the pin budget,
the schematic generator and the board checker read that file. Nobody types a pin
number twice.

ONE SOURCE ONLY, and it says so:
  docs/datasheets/pcedev-wiki-HuCard_pinout-2026-11-19.txt (PCEdev wiki, fetched
  2026-11-19). Unlike the expansion port, there is no second committed source for
  the card edge yet: the console schematic's CN202 has not been transcribed, and
  nobody has put a meter on a slot. So this file can only check that the pinout is
  STRUCTURALLY complete (all 21 address lines, all 8 data lines, both strobes,
  power, ground once each) -- not that it matches the console. That comparison is
  TEST_PLAN T1c: continuity from these card fingers to the already-verified rear
  port pins, which is the cross-check this file does not have.

Direction is the CARD's view, from the wiki's arrows:
  <-  console drives it (card input)      ->  card drives it (card output)
  <>  bidirectional                       --  power or ground
"""
import csv, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WIKI = ROOT / "docs" / "datasheets" / "pcedev-wiki-HuCard_pinout-2026-11-19.txt"
OUT = ROOT / "docs" / "hucard_pinout.csv"

DIRECTION = {"<-": "in", "->": "out", "<>": "inout", "--": "power"}

# Signals that must appear exactly once, with the direction the card sees.
REQUIRED = {f"A{i}": "in" for i in range(21)}
REQUIRED.update({f"D{i}": "inout" for i in range(8)})
REQUIRED.update({
    "/RD": "in", "/WR": "in", "/RST": "in", "HSM": "in",
    # The card drives these three: it grounds /CD (card detect), it puts audio
    # into the console, and it raises IRQ2.
    "/CD": "out", "AUDIO_IN": "out", "/IRQ2": "out",
    "+5V": "power", "GND": "power",
})

NOTES = {
    "/CD": "card detect: grounded by a HuCard; on the rear port it is /CARD (c3)",
    "AUDIO_IN": "mono, mixed into both console channels -- no stereo on this connector",
    "+5V": "a real digital supply, unlike the rear port's +5A",
    "/IRQ2": "the card can raise IRQ2 (open drain on the console side)",
    "HSM": "high speed mode, asserted by the CPU at 7.16 MHz",
    "GND": "the only ground on the connector",
}


def canonical(text):
    """The wiki's prose name -> the name used everywhere downstream."""
    t = text.strip()
    m = re.match(r"^CPU (PA)?P?(\d+)$", t)
    if m:
        return f"A{int(m.group(2))}"
    m = re.match(r"^CPU D(\d+)", t)
    if m:
        return f"D{int(m.group(1))}"
    if t.startswith("CPU /"):
        return "/" + t[5:]
    return {"AUDIO IN": "AUDIO_IN"}.get(t, t)


def parse(text):
    """38 rows of '  15 |<>| CPU D0 (PCE) or D7 (TG16)  [ascii art]'."""
    pins = {}
    for line in text.splitlines():
        m = re.match(r"^\s*(\d+)\s*\|([<>-]{2})\|(.*)$", line)
        if not m:
            continue
        number, arrow, rest = int(m.group(1)), m.group(2), m.group(3).strip()
        # The wiki's orientation diagram is glued onto some lines: the signal is
        # whatever precedes the first run of two or more spaces.
        name = re.split(r"\s{2,}", rest)[0].strip()
        if not name or number in pins:
            continue
        pins[number] = {
            "pin": number,
            "signal": canonical(name),
            "direction": DIRECTION.get(arrow, arrow),
            "wiki_text": name,
            "note": "",
        }
    return pins


def check(pins):
    problems = []
    if sorted(pins) != list(range(1, 39)):
        problems.append(f"found {len(pins)} pins, expected 38 numbered 1-38")
    for want, direction in REQUIRED.items():
        hits = [p for p in pins.values() if p["signal"] == want]
        if len(hits) != 1:
            problems.append(f"{want} appears {len(hits)} times, expected once")
        elif hits[0]["direction"] != direction:
            problems.append(f"{want} is {hits[0]['direction']}, expected {direction}")
    for p in pins.values():
        if p["signal"] == "GND" and p["direction"] != "power":
            problems.append(f"pin {p['pin']}: GND is {p['direction']}, expected power")
    return problems


def selftest(pins):
    import copy
    cases = []
    p = copy.deepcopy(pins); p[14]["signal"], p[15]["signal"] = p[15]["signal"], p[14]["signal"]
    cases.append(("A0 and A1 swapped", p))
    p = copy.deepcopy(pins); p[26]["signal"] = "A0"
    cases.append(("pin 26 /RD misread as A0", p))
    p = copy.deepcopy(pins); del p[38]
    cases.append(("pin 38 (+5V) missing", p))
    p = copy.deepcopy(pins); p[34]["direction"] = "out"
    cases.append(("/WR read as a card output", p))
    p = copy.deepcopy(pins); p[2]["signal"] = "AUDIO_IN"; p[2]["direction"] = "inout"
    cases.append(("AUDIO_IN marked bidirectional", p))
    ok = True
    print("SELFTEST -- each line must say CAUGHT")
    for label, broken in cases:
        got = bool(check(broken)); ok &= got
        print(f"  {'CAUGHT' if got else 'MISSED'}  {label}")
    return ok


def main():
    pins = parse(WIKI.read_text(encoding="utf-8"))
    if "--selftest" in sys.argv:
        if not selftest(pins):
            sys.exit("SELFTEST FAILED")
        print()
    problems = check(pins)
    if problems:
        print(f"{len(problems)} PROBLEM(S) with the parsed card edge:")
        for p in problems:
            print("  FAIL ", p)
        sys.exit(1)
    for p in pins.values():
        p["note"] = NOTES.get(p["signal"], "")
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")   # LF on every platform: the CSV stays byte-identical
        w.writerow(["pin", "signal", "card_direction", "wiki_text", "note"])
        for n in sorted(pins):
            p = pins[n]
            w.writerow([p["pin"], p["signal"], p["direction"], p["wiki_text"], p["note"]])
    addr = sum(1 for p in pins.values() if re.fullmatch(r"A\d+", p["signal"]))
    data = sum(1 for p in pins.values() if re.fullmatch(r"D\d+", p["signal"]))
    print(f"card edge is structurally complete: {addr} address, {data} data, "
          f"both strobes, +5V, ground; wrote {OUT.relative_to(ROOT).as_posix()}")
    print("not on this connector: K7, RDY, DCK (a clock), /NMI, stereo audio")


if __name__ == "__main__":
    main()
