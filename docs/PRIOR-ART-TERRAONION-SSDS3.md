# Prior art: Terraonion Super SD System 3 (closed product, rear expansion port)

Sources: Terraonion product page (https://terraonion.com/en/product/super-sd-system-3/index.html), a board photo of the SD System 3 (2019, retrostuff.org; photo not stored here), RGB Inside review. Chip markings below are read from the photo and are a best reading.

## What it does (product page)
- Plugs into the rear expansion port; CD-ROM emulation from microSD (.cue images) plus HuCard images (.pce).
- Integrated System Cards for CD-ROM2, Super CD-ROM2 and Arcade CD-ROM2 (no real System Card needed).
- RGB AV out with composite video and stereo sound. Compatible with CoreGrafx, CoreGrafx II and SuperGrafx (page says only "compatible").

## What is on the board (photo)
- FPGA: Lattice LFXP2-5E (LatticeXP2, ~5K LUT) in a large QFP. => CD-ROM, System Card and Arcade Card emulation fits a small FPGA.
- ARM microcontroller: ST (an STM32; Dennis says Cortex-M4; exact type not readable). => microSD, menu, USB, disc image loading.
- One ISSI memory chip next to the FPGA (type not readable).
- Three TI 16-bit level-shifter chips: 2x LVCH16373A (latches, probably the address bus) and 1x LVCH16T245 (data bus transceiver): 5 V console <-> 3.3 V logic.
- THS7374 video amplifier (RGB output); microSD slot; USB-B port; two regulators.

## Consequences for this project
- CD-only build fits a small FPGA; the ECP5-45F is far more than needed (Tang Nano 9K was already named as fitting).
- ARM/companion MCU + FPGA split matches the plan in HANDOFF-2026-11-19.md.
- Level-shift plan (address latches, data transceiver) matches the hand-off's hardware notes.
- The Krikzz Turbo EverDrive Pro shows CD-ROM emulation from the HuCard slot is also possible (Cyclone IV + 16 MB PSRAM, mono CD audio per reviews). Compare expansion port vs card slot pinouts before choosing.
