#!/usr/bin/env python3
"""Attach 3D models to footprints that have none (or a missing one), for the 3D view.

    "C:/Users/terra/AppData/Local/Programs/KiCad/10.0/bin/python.exe" tools/models_card.py

Models live in hw/card/3dmodels/ (sources in its README). Offsets were measured by
comparing the model's own footprint pads with ours: the model must sit on our pads.
Purely visual: no pad, net or fab output changes. Re-runnable.
"""
import pathlib

import pcbnew

ROOT = pathlib.Path(__file__).resolve().parent.parent
PCB = ROOT / "hw" / "card" / "pce_card.kicad_pcb"

# footprint name -> (model file in hw/card/3dmodels, offset x, y, z in mm, rotation z in degrees)
# KiCad's model offset uses y UP, so a shift toward the footprint's -y is a positive y here.
MODELS = {
    "microSD_HC_SOFNG_TF-008": ("TF-SMD_TF-008.step", (0.04, 3.37, 0.0), 0),
    "switch_button_TS-1088-AR02016": ("SW-SMD_L3.9-W2.9-H2.0-LS4.8.step", (0.0, 0.0, 0.0), 0),
    "Oscillator_SMD_SiT_PQFN-4Pin_2.5x2.0mm": ("OSC-SMD_4P-L2.5-W2.0-H0.6.step", (0.0, 0.0, 0.0), 0),
}


def main():
    board = pcbnew.LoadBoard(str(PCB))
    done = []
    for fp in board.GetFootprints():
        name = fp.GetFPID().GetLibItemName().wx_str()
        if name not in MODELS:
            continue
        f, (x, y, z), rz = MODELS[name]
        models = fp.Models()
        models.clear()
        m = pcbnew.FP_3DMODEL()
        m.m_Filename = "${KIPRJMOD}/3dmodels/" + f
        m.m_Offset = pcbnew.VECTOR3D(x, y, z)
        m.m_Rotation = pcbnew.VECTOR3D(0, 0, rz)
        m.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
        models.push_back(m)
        done.append(fp.GetReference())
    board.Save(str(PCB))
    print(f"3D models attached: {', '.join(sorted(done))}")


if __name__ == "__main__":
    main()
