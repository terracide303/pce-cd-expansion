# 3D models

Fetched 2026-11-19 from LCSC/EasyEDA with `easyeda2kicad` 1.0.1, by the LCSC numbers in
the Icepi Zero v1.4 BOM. Used only for the 3D view; they do not affect the electrical
design or the fab files. Attached to the footprints by `tools/models_card.py`, with
the offsets measured by comparing EasyEDA's footprint pads with ours.

| file | part | LCSC | on |
|---|---|---|---|
| TF-SMD_TF-008.step | microSD socket TF-008 | C428465 | J6 (offset 0.04, 3.37 mm: EasyEDA's origin is 3.37 mm further back) |
| SW-SMD_L3.9-W2.9-H2.0-LS4.8.step | tactile switch TS-1088 | C720477 | SW1, SW2, SW101 |
| OSC-SMD_4P-L2.5-W2.0-H0.6.step | 50 MHz oscillator SG-8018CG, 2.5 x 2.0 | C390526 | Y1 |
