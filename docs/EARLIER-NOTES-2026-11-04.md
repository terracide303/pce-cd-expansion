# Earlier notes (2026-11-04 discussion, all UNVERIFIED)

Source: the project memory note from the first discussion (Discord-sourced facts plus recall). Treat as leads, not facts.


Dennis wants an OPEN-SOURCE expansion for the PC Engine's expansion port that does CD-ROM emulation and SuperGrafx (SGX) game support, like the closed Terraonion SuperSD System 3 Pro. Related to PCEHeroTN (core: HuC6280 + huc6270 + huc6260 + PSG on Tang Nano 20K). Only discussed, nothing built; he said "stop talking about pce studio" when this came up — keep the two projects apart.

Facts from his Discord source and my memory (UNVERIFIED): the PSG lives INSIDE the HuC6280 (SGX always uses Rev-A); internal PSG writes never show data on the bus though address lines are set; so sound upgrades need a shadow data path (track A/X/Y + flags from observed bus reads/fetches, or a lock-stepped CPU core fed by the real CPU's bus/outputs) — prove in simulation with PCEHeroTN's core, then a logic-analyser capture on a real console. A line to the VCE disables the VDC clock, so the FPGA can implement two VDCs + VPC + a rebuilt VCE and drive video itself. RAM conflict: 8 KB mirrored on PCE vs 32 KB on SGX -> non-identical upgrade, remap RAM, patch ~6 SGX games (patches applied by users to their own dumps). Taking over audio = own PSG model (Rev-A, no pop) + mixer with CD-DA and ADPCM + DAC/I2S or HDMI audio out; the console's own audio is simply not used. Needs external fast SRAM (System Card RAM, ADPCM RAM, ~140 ns cycle), SD/SDRAM for disc data, 5V<->3.3V level shifting, a bigger-BRAM FPGA (two VDCs = 128 KB VRAM). System Card BIOS not shippable (user supplies). Open questions: expansion-port pinout, IRQ1/VCE-disable line access, whether the pins show every cycle. Licences of the MiSTer-derived cores not checked.


