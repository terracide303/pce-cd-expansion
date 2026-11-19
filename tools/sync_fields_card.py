#!/usr/bin/env python3
"""Copy each part's LCSC number from the design data to its footprint, nothing else.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/sync_fields_card.py [board]

For when hw/card/design.py gains part numbers after the board is placed or routed:
schematic parity compares the fields, and rebuilding the board would wipe placement.
Default board: hw/card/pce_card.kicad_pcb.
"""
import pathlib, sys

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hw" / "card"))
import design  # noqa: E402

PCB = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "hw" / "card" / "pce_card.kicad_pcb"


def main():
    board = pcbnew.LoadBoard(str(PCB))
    want = {p["ref"]: p.get("lcsc", "") for p in design.PARTS}
    changed = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if ref not in want:
            continue
        have = fp.GetFieldText("LCSC") if fp.HasField("LCSC") else None
        if have != want[ref]:
            fp.SetField("LCSC", want[ref])
            fp.GetField("LCSC").SetVisible(False)
            changed.append(ref)
    board.Save(str(PCB))
    print(f"LCSC fields updated on {len(changed)} footprints")


if __name__ == "__main__":
    main()
