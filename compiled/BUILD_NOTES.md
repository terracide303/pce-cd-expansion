# Build notes

Newest first. Every build: what it is, the numbers, and whether it has run on hardware.

## pce_exp_stage1_8kb_d3a23a7+.fs — stage 1 RAM responder, 8 KB (2026-11-19)

- **Source:** `d3a23a7` plus the uncommitted fixes in the same commit as this file
  (simulation-only RAM init hidden from synthesis). Built with
  `gw_sh fpga/build_stage1.tcl`, Gowin V1.9.11.03 Education, GW2AR-LV18QN88C8/I7.
- **What it is:** `rtl/stage1_top.v` with `ADDR_BITS=13`: answers banks `$80`
  (`$100000-$101FFF`) as RAM. A13-A15 are read but ignored (test T5 first).
- **Resources:** 19 LUT, 59 registers (18 in I/O cells: the first synchroniser
  stage sits at the pins), 4/46 BSRAM, 1 rPLL, 28 I/O. No latches.
- **Timing:** 108 MHz constraint, **Fmax 271.3 MHz**, setup and hold TNS 0.000 on
  every clock. Logic level 1.
- **Warnings:** one, PR1014 (27 MHz input on general routing to the PLL). PCEHeroTN's
  hardware-proven builds carry the same warning on the same pin.
- **Synth log:** no "Undeclared symbol", no "no driver".
- **SHA-256 (first 16):** 151ad2b068a9188a
- **Hardware:** **not run.** There is no board yet. Flash only after TEST_PLAN T1-T5,
  with the board built and T6/T7 passed.
