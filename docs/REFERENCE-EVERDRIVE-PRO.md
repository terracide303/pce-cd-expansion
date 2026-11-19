# Reference: the Turbo EverDrive PRO sources (MIT)

krikzz publishes development sources for the cartridges —
[github.com/krikzz/turbo-ed-pro-pub](https://github.com/krikzz/turbo-ed-pro-pub),
**MIT licensed** — and a firmware changelog
([krikzz.com/pub/support/turbo-everdrive/pro-series/firmware/](https://krikzz.com/pub/support/turbo-everdrive/pro-series/firmware/)).
This is a **shipping HuCard-slot FPGA cartridge**, so read as: what the bus
contract really is, and what actually breaks in this kind of device.

**What is not in there:** the CD-ROM² core. The public sources show only its
socket in `base/everdrive.sv` — `cc_ce` and `cc_dato` join `bus_oe` and the data
mux like any other window — so the *interface* is public and the CD logic is not.

## 1. The bus contract, from `ed_pro/fpga_std/top.sv`

| direction | signals |
|---|---|
| into the FPGA | `TG_A[20:0]`, `TG_D[7:0]`, `TG_HSM`, `TG_OEn` (/RD), `TG_WEn` (/WR) |
| out of the FPGA | `TG_IRQ2n`, `TG_RSTFn`, `TG_CARTn`, **`TG_DDIR`**, **`TG_DOEn`** |
| the rest | two 16-bit PSRAMs (22-bit address), an SPI/FCI link to the companion MCU, a `region` input, and an **I2S DAC** (`DAC_LRCK/MCLK/SCLK/SDIN`, a CS4344) |

Three things to copy or deliberately not copy:

1. **The FPGA owns the data buffer**: `TG_DDIR` and `TG_DOEn` are outputs. Our
   [STAGE1.md](archive/STAGE1.md) decision 4 saves two pins by deriving DIR from `/RD` and
   `/OE` from the select. With 24 safe pins that is the right trade here; with a
   bigger module the reference's way is better, because the FPGA tri-states in the
   exact cycle it means to.
2. **Region is eight wires of mapping, in the FPGA.** `cpu_dati_tg` and
   `cpu_dato_tg` are the PC Engine bytes with the bits reversed. That is the
   [BUS_OPTIONS.md](archive/BUS_OPTIONS.md) §5 finding, implemented: no jumper, no second
   board. Their `region` input just picks which side to present.
3. **The card drives IRQ2 and /RST too** (`TG_IRQ2n`, `TG_RSTFn`), not only data.

## 2. What a cartridge may answer — this settles T4b

`base/everdrive.sv`:

```verilog
assign bus_oe = cpu.oe & (reg_ce | huc_ce | exp_ce | cc_ce);
```

The cart drives the data bus **whenever /RD is low and one of its own decoded
windows matches** — the console's `/CE` (which is only A20) plays no part. That is
the assumption [BUS_OPTIONS.md](archive/BUS_OPTIONS.md) §2 needed and no document stated.
The windows it answers, from source:

| window | physical | answered by | in `top.sv`'s decode |
|---|---|---|---|
| HuCard ROM | `$000000–$0FFFFF` | `huc_std`: `rom.ce = cpu.addr[20] == 0` | the classic card window |
| Super System Card ROM | `$000000–$07FFFF` | `huc_ssc`: `cpu.addr[20:19] == 0` | |
| **Super System Card RAM, 192 KB** | **`$0D0000–$0FFFFF`** | `huc_ssc`: `{addr[20:18],18'd0} == 'h0C0000 & addr[17:16] != 0` | confirms [STAGE2_REFERENCE.md](STAGE2_REFERENCE.md) §2 |
| **SSC signature registers** | **`$1FF8C0–$1FF8C7`** | `huc_ssc`: `{addr[20:3],3'd0} == 'h1FF8C0` | **answers an open question, §3** |
| **Backup RAM, 2 KB** | **`$1EE000–$1EE7FF`** | `exp_tnb` (Ten no Koe 2 emulation): `{addr[20:11],11'd0} == 'h1EE000` | confirms §2 |
| **The cart's own registers** | **`$1FFFF0–$1FFFFF`** | `reg_ce` | a 16-byte window at the very top of the address space |

Four of the six are above `A20`, i.e. above anything a "card" is supposed to
answer, and all four are ordinary decode. **T4b is no longer a question about the
architecture** — it is a check of our board.

Note where they put their own registers: `$1FFFF0–$1FFFFF`, the last 16 bytes,
because nothing else claims them. Our design should consider the same spot (or
avoid it deliberately, since it is also where a runaway program lands).

## 3. It answers our $18C1–$18C7 question

[STAGE2_REFERENCE.md](STAGE2_REFERENCE.md) §2 lists as open: "signature bytes
`$1FF8C1–C7` — CD unit or Super System Card? Decides whether we answer." From
`huc/huc_ssc.sv`, the **Super System Card** answers, being a HuCard:

| address | value | note |
|---|---|---|
| `$1FF8C1` | `$AA` | |
| `$1FF8C2` | `$55` | |
| `$1FF8C3` | `$00` | |
| `$1FF8C4` | `$FF` | |
| `$1FF8C5` | `$55` / `$AA` | selected by the `region` input |
| `$1FF8C6` | `$AA` / `$55` | the other way round |
| `$1FF8C7` | `$C0` / `$03` | region byte |

So the SSC's card-detection block is in the **card**, not the CD unit — which is
also why a card-only device can be a "Super System Card" at all. Which end is
Japan and which is the US is not stated in the source; the pair is what matters for
now, and the values are testable against a real card.

## 4. The mappers are here, and one of them is the gap we had

`huc/` contains `huc_std` (plain), `huc_sf2` (**Street Fighter II**, the mapper
[SOURCES_REVIEW.md](archive/SOURCES_REVIEW.md) names as PCEHeroTN's likely SF2 bug),
`huc_pop` (Populous), `huc_384` (dual 256+128 KB), `huc_ssc` (Super System Card),
`huc_sys` (the menu's own mapper), `huc_nom` (no mapper). MIT, so a flash-cart build
can start from these with attribution rather than from a disassembly.

## 5. The register set: a RAM window instead of RAM on the bus

`$1FFFF0`: FIFO data (`$0/$1`), FIFO status (`$2`), system status (`$3`), timer
(`$4/$5`), **RAM I/O data (`$6/$7`), RAM I/O address (`$8/$9`)**, save-state data
and address (`$A–$D`). That last pair is the trick worth remembering: the console
reads and writes the cart's 16 MB of PSRAM **one byte at a time through two
registers**, so no wide RAM window has to exist on the console bus at all.

That is why their cart can be a flash card with a modest pin count. It does **not**
rescue our pin problem: a HuCard ROM is read *linearly by the CPU*, so presenting
one still needs the address lines. The window trick serves the menu and the loaders,
which is where we should use it.

## 6. Audio: the cart has its own DAC

`base/audio.sv` contains `dac_cs4344` driven by `DAC_*` pins in `top.sv`. So the
cart can produce CD-DA and ADPCM in stereo **without the console's mixing circuit**.
That explains the product note — "CD and hucard audio doesn't work via RF output" —
the console's RF modulator only mixes its own sources, and it also explains the
**EDFX** board: the way back into the console's AV chain is the expansion port's
audio pins. Audio never needs to go through the card edge.

For us: this is the third audio option, and arguably the best — a stereo DAC on the
carrier feeding either an EDFX-style port board or our own jack/HDMI. It also means
"the card is mono" was about the *console's* path only, never about the device.

## 7. The changelog is a risk list for stage 2

From the [firmware changelog](https://krikzz.com/pub/support/turbo-everdrive/pro-series/firmware/changelog.txt),
in their words — this is what actually broke in a shipped device of exactly this
kind:

| change | lesson for us |
|---|---|
| ADPCM frequency 32256 → **32118 Hz** (2026) | the ADPCM divider is a de-tuned odd number, not a clean rate: copy the value, not the arithmetic |
| CDDA glitches with some SD cards; cue parser buffer increased | keep the disc-read path over-buffered and test with bad cards |
| "Changes in CD seek time calculations" (twice) | seek timing is empirical, not from a datasheet |
| "Fixed problem with recording to SD card while playing CD games" | the bram/save path and the CD path share the card |
| "Filling memory with zeros at 0x2200–0x2300. Some hacks require it" | software depends on RAM being zeroed in specific spots |
| "Sprite table initialization. For homebrew application which skips initialization" | boot-state parity matters before the first frame |
| "Fixes for US super system card"; "Arcade card fix"; "memory timings optimization" | the browser's edge cases are regional BIOS and Arcade Card modes |
| "EDFX booster detection using expansion port pin B2" | K7 is used as a *signal line* between cart and audio board |

## 8. What we take, and how to cite it

MIT: reuse with the copyright and permission notice. Concretely, worth taking:

- the **window list and decode patterns** (§2) as a checklist for our decode;
- the **`$18C0–$18C7` values** (§3) into our stage-2 register model;
- the **mapper set** (§4) for the flash-cart role;
- the **RAM-I/O register pair** (§5) for our loader and menu;
- the **I2S DAC** (§6) as the audio plan's default.

And one thing to check against our own RTL: their `cpu_io` (in `base/var.sv`)
derives `ce`/`oe`/`we` from the raw pins, which is the same job our
`rtl/ram_responder.v`'s two-stage synchroniser does. Comparing the two is a cheap
review of our edge detection — the thing stage 2 says has to fire exactly once per
cycle.

Verbatim copy of their files is avoidable: we want their *contract* and their
*mapper behaviour*, not their instance of it, and our toolchain is Gowin, not
Quartus.
