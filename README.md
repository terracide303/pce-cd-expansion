# PCE CD Expansion (idea, not started)

An open-source CD-ROM² / Super CD-ROM² emulator that plugs into the rear expansion port of the PC Engine / TurboGrafx-16, built on a Tang Nano 20K and derived from a stripped-down [PCEHeroTN](https://github.com/terracide303/PCEHeroTN-Beta).

**Status: future project. Nothing is built.** The first document is the design hand-off from a planning chat on 2026-11-19: [docs/HANDOFF-2026-11-19.md](docs/HANDOFF-2026-11-19.md).

## Staged plan (from the hand-off)
1. De-risk: the 20K on the expansion port as a 64 KB RAM responder at banks $80-$87; memory test from a HuCard.
2. CD-only build: bus interface, CD controller, ADPCM, CD-DA, RAM, microSD link via the companion MCU. Get games booting.
3. Shadow VDC/VCE/PSG snooped from the bus, HDMI output.

## Open points
- Licence not chosen yet. The reference HDL for the CD logic (MiSTer TurboGrafx-16 core) is GPL.
- The System Card BIOS is not shipped; the user supplies it.
- Expansion-port pinout and which lines show every bus cycle are still to be verified.
- Everything in the hand-off is unverified design notes.
