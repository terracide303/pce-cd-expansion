"""The card (docs/CARD.md): the circuit, as data.

Two kinds of parts:

1. THE FPGA CORE, DERIVED FROM THE ICEPI ZERO v1.4 NETLIST
   (reference/icepi-zero-v1.4/, Solderpad v2.1). Every kept part keeps its
   reference, value, footprint, LCSC number and every pin's connection. The only
   differences are the ones listed in DROP, RENAME and FREED below, and
   tools/check_card.py proves there are no others.

2. THE CARD'S OWN PARTS (refs >= 100): the card edge, bus translators, IRQ
   buffer, power input, RP2040 companion, audio DAC. Written out pin by pin.

Every part: ref, sym (a "lib:name" symbol), value, fp, lcsc, sheet, pins
{pin number: net or None}. Multi-unit symbols (the ECP5) list all their pins;
the generator places each unit on the sheet given by UNIT_SHEET.

Net names:
  BUS_*      console side, 5 V (card fingers)          F_*   FPGA side, 3.3 V
  T_D*       data translator <-> 33 ohm resistors      CO_*  RP2040 <-> FPGA link
  +5V_CON    the console's 5 V (card pin 38)           +5V_CARD the card's 5 V rail
  ICEPI-derived local nets are prefixed with their Icepi sheet (SDRAM_D0, ...).
"""
import csv, json, pathlib, re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REF = HERE / "reference" / "icepi-zero-v1.4"
ICEPI_SYM = "icepi"           # symbols vendored in reference/icepi-embedded.kicad_sym


# ---------------------------------------------------------------- 1. the Icepi core
def _parse(text):
    tok = re.findall(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+', text)
    stack, cur = [], []
    for t in tok:
        if t == "(":
            stack.append(cur); cur = []
        elif t == ")":
            done = cur; cur = stack.pop(); cur.append(done)
        else:
            cur.append(t[1:-1].replace('\\"', '"').replace("\\\\", "\\") if t.startswith('"') else t)
    return cur[0]


def _find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def _val(node, key):
    f = _find(node, key)
    return f[0][1] if f and len(f[0]) > 1 else ""


def load_netlist(path):
    """KiCad s-expression netlist -> ({ref: {value, footprint, lib, part, sheet}}, {net: [(ref, pin)]})."""
    root = _parse(path.read_text(encoding="utf-8"))
    comps = {}
    for c in _find(_find(root, "components")[0], "comp"):
        ls = dict((x[0], x[1]) for x in _find(c, "libsource")[0][1:])
        sp = _find(c, "sheetpath")
        comps[_val(c, "ref")] = dict(value=_val(c, "value"), footprint=_val(c, "footprint"),
                                     lib=ls.get("lib", ""), part=ls.get("part", ""),
                                     sheet=_val(sp[0], "names") if sp else "/")
    nets = {}
    for n in _find(_find(root, "nets")[0], "net"):
        nets[_val(n, "name")] = [(_val(x, "ref"), _val(x, "pin")) for x in _find(n, "node")]
    return comps, nets


ICEPI_COMPS, ICEPI_NETS = load_netlist(REF / "icepi-zero.net")

# Parts of the Icepi the card does not have, and why.
DROP = {
    "J1": "Raspberry Pi header: its 28 GPIO become the console bus",
    "H1": "mounting hole: a card has none", "H2": "mounting hole", "H3": "mounting hole", "H4": "mounting hole",
    "LOGO1": "OSHW logo: certification belongs to the Icepi, not to this card",
    # GPDI (HDMI-style) output: no video out on the card (owner, 2026-11-19)
    **{r: "GPDI video output" for r, c in ICEPI_COMPS.items() if c["sheet"] == "/GPDI/"},
    # The FPGA's two soft-USB ports (J3, J4) and their pull and ESD networks. J5 + U9 (FT231X) stay.
    # (R20-R35: pulls, 27 ohm series and the J3/J4 CC resistors.)
    **{r: "FPGA soft-USB port" for r in ["J3", "J4", "U7", "U8"] + [f"D{i}" for i in range(6, 14)]
       + [f"R{i}" for i in range(20, 36)]},
}

# Icepi net -> card net, where the card changes the meaning.
RENAME = {
    "+5V": "+5V_CARD",            # the Icepi's USB 5 V becomes the card's own rail, fed through diodes
}
# J5 (the FT231X USB-C) VBUS: on the Icepi it is +5V itself; on the card it is VBUS_FT,
# which reaches +5V_CARD through D102. Pin-level override, below.
PIN_OVERRIDE = {("J5", p): "VBUS_FT" for p in ("A4", "A9", "B4", "B9")}

# The FPGA balls whose Icepi function is gone (header GPIO, GPDI, soft-USB),
# and what they carry on the card. Banks from prjtrellis-db (docs/FPGA-ECP5.md);
# at 7.16 MHz any ball in a bank will do, so layout may swap within a bank.
FREED = {
    # bank 7 (14): A0-A13
    "G3": "F_A0", "K3": "F_A1", "E1": "F_A2", "F3": "F_A3", "G1": "F_A4", "H2": "F_A5", "J1": "F_A6",
    "G2": "F_A7", "J3": "F_A8", "E3": "F_A9", "H3": "F_A10", "F1": "F_A11", "F2": "F_A12", "J2": "F_A13",
    # bank 6 (16): A14-A20, strobes, translator control, IRQ, 2 spares on test points
    "T2": "F_A14", "R2": "F_A15", "R1": "F_A16", "P1": "F_A17", "N1": "F_A18", "R3": "F_A19", "N4": "F_A20",
    "P2": "F_RD_N", "M2": "F_WR_N", "L1": "F_RST_N", "L2": "F_HSM",
    "P3": "F_DDIR", "T3": "F_DOE_N", "T4": "F_IRQ2_N",
    "R5": "F_SPARE0", "P5": "F_SPARE1",
    # bank 3 (9): data
    "R13": "F_D0", "T14": "F_D1", "R15": "F_D2", "T15": "F_D3", "P16": "F_D4", "R16": "F_D5",
    "R12": "F_D6", "T13": "F_D7", "L14": None,
    # bank 2 (7): RP2040 link and two I2S lines
    "E16": "CO_SCK", "F15": "CO_MOSI", "J15": "CO_MISO", "J16": "CO_CS_N", "G15": "CO_IRQ",
    "H14": "F_I2S_BCK", "E14": "F_I2S_LRCK",
    # bank 0 (2), bank 1 (1)
    "D4": "F_I2S_DIN", "E4": None, "E11": None,
}


def _sheet_prefix(sheet):
    s = sheet.strip("/").upper()
    return {"": "", "USB": "USB_", "POWER": "PWR_", "FLASH": "FLASH_", "SDRAM": "SDRAM_", "USD": "SD_"}.get(s, s + "_")


def _card_net(icepi_net):
    """An Icepi net name -> the card's label name. None for unconnected pins."""
    if icepi_net.startswith("unconnected-"):
        return None
    if not icepi_net.startswith("/"):                       # a global (power) net
        return RENAME.get(icepi_net, icepi_net)
    sheet, name = icepi_net.rsplit("/", 1)
    name = re.sub(r"^Net-\((.*)\)$", r"\1", name).replace("-", "_")
    return _sheet_prefix(sheet + "/") + name


def icepi_pins():
    """{ref: {pin: card net}} for every kept Icepi part, after RENAME, PIN_OVERRIDE and FREED."""
    out = {r: {} for r in ICEPI_COMPS if r not in DROP}
    for net, nodes in ICEPI_NETS.items():
        for ref, pin in nodes:
            if ref in out:
                out[ref][pin] = _card_net(net)
    for (ref, pin), net in PIN_OVERRIDE.items():
        out[ref][pin] = net
    for ball, net in FREED.items():
        out["U1"][ball] = net
    return out


BOM = {}
for row in csv.DictReader(open(REF / "bom.csv", encoding="utf-8-sig")):
    for ref in row["Designator"].split(","):
        BOM[ref.strip()] = row["LCSC Part #"]

ICEPI_SHEET = {"/": "fpga", "/Power/": "power", "/Flash/": "flash", "/SDRAM/": "sdram", "/uSD/": "sd", "/USB/": "usb_jtag"}
# The ECP5's ten units (symbol LFE5U-25F-6BG256x; the 45F has the same balls):
# LCSC numbers: copied from the Icepi BOM for its parts, and for new parts only where
# already used in the owner's designs. The rest are left empty ON PURPOSE: fill them
# from the fab's parts library at ordering, not from memory (docs/CARD.md).
UNIT_SHEET = {1: "power", 2: "usb_jtag", 3: "flash", 4: "bus", 5: "usb_jtag", 6: "sdram", 7: "sd",
              8: "bus", 9: "fpga", 10: "fpga"}

PARTS = []
for ref, pins in icepi_pins().items():
    c = ICEPI_COMPS[ref]
    PARTS.append(dict(ref=ref, sym=f"{ICEPI_SYM}:{c['lib']}__{c['part']}", value=c["value"], fp=c["footprint"],
                      lcsc=BOM.get(ref, ""), sheet=ICEPI_SHEET[c["sheet"]], pins=pins, origin="icepi"))
# J5: the Icepi's USB-C symbol names the shield pin "S1"; KiCad 10's footprint names that
# pad "SH", so with the Icepi symbol the shield would connect to nothing. Use KiCad's own
# symbol (same pins, shield = "SH"). check_card.py treats (J5, S1) as a documented change.
SYMBOL_SWAP = {"J5": ("Connector:USB_C_Receptacle_USB2.0_14P", {"S1": "SH"})}
for _p in PARTS:
    if _p["ref"] in SYMBOL_SWAP:
        _p["sym"], _ren = SYMBOL_SWAP[_p["ref"]]
        _p["pins"] = {_ren.get(k, k): v for k, v in _p["pins"].items()}

# The card carries the 45F (owner's decision; ball-compatible, docs/FPGA-ECP5.md).
U1 = next(p for p in PARTS if p["ref"] == "U1")
U1["value"], U1["lcsc"] = "LFE5U-45F-6BG256C", "C1550834"   # LCSC number as used on MiniMistle 0.2


# ---------------------------------------------------------------- 2. the card's own parts
def part(ref, sym, value, fp, sheet, pins, lcsc=""):
    PARTS.append(dict(ref=ref, sym=sym, value=value, fp=fp, lcsc=lcsc, sheet=sheet, pins=pins, origin="card"))


R0603, C0603, C0402 = "Resistor_SMD:R_0603_1608Metric", "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_0402_1005Metric"
R0402 = "Resistor_SMD:R_0402_1005Metric"


def res(ref, val, a, b, sheet, fp=R0402):
    part(ref, "Device:R", val, fp, sheet, {"1": a, "2": b})


def cap(ref, val, a, sheet, b="GND", fp=C0402):
    part(ref, "Device:C", val, fp, sheet, {"1": a, "2": b})


# --- card edge (J101), from docs/hucard_pinout.csv (wiki and console schematic agree, tools/hucard_bus.py)
HUCARD = list(csv.DictReader(open(ROOT / "docs" / "hucard_pinout.csv", encoding="utf-8")))


def edge_net(signal):
    if signal == "GND":
        return "GND"
    if signal == "+5V":
        return "+5V_CON"
    if signal == "/CD":
        return "GND"                       # the card is present: a HuCard grounds /CD
    if signal == "AUDIO_IN":
        return "BUS_AUDIO"
    return "BUS_" + signal.replace("/", "") + ("_N" if signal.startswith("/") else "")


part("J101", "pce_card:HUCARD_EDGE", "HuCard edge (38 fingers)", "pce_card:HuCard_Edge_38", "bus",
     {r["pin"]: edge_net(r["signal"]) for r in HUCARD})


# --- inputs: console 5 V -> FPGA 3.3 V. SN74LVC245A at 3.3 V: 5 V-tolerant inputs, fixed A->B.
def lvc245(ref, inputs, outputs):
    pins = {"1": "+3V3", "19": "GND", "10": "GND", "20": "+3V3"}     # DIR high = A->B, /OE low = on
    for i in range(8):
        pins[str(2 + i)] = inputs[i]
        pins[str(18 - i)] = outputs[i]
    part(ref, "Logic_LevelTranslator:SN74LVC245APW", "SN74LVC245APW", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm",
         "bus", pins)
    cap("C" + ref[1:], "100n", "+3V3", "bus")


lvc245("U101", [f"BUS_A{i}" for i in range(8)], [f"F_A{i}" for i in range(8)])
lvc245("U102", [f"BUS_A{i}" for i in range(8, 16)], [f"F_A{i}" for i in range(8, 16)])
lvc245("U103", [f"BUS_A{i}" for i in range(16, 21)] + ["BUS_RD_N", "BUS_WR_N", "BUS_RST_N"],
       [f"F_A{i}" for i in range(16, 21)] + ["F_RD_N", "F_WR_N", "F_RST_N"])
# HSM: one more input, a single buffer (5 V-tolerant input at 3.3 V)
part("U104", "74xGxx:74LVC1G34", "74LVC1G34", "Package_TO_SOT_SMD:SOT-23-5", "bus",
     {"1": None, "2": "BUS_HSM", "3": "GND", "4": "F_HSM", "5": "+3V3"})
cap("C104", "100n", "+3V3", "bus")

# --- data: SN74LVC8T245. A side = FPGA (VCCA 3.3 V), B side = console (VCCB = console 5 V).
# DIR high = A->B = the card drives the console. DIR and /OE are referenced to VCCA
# and driven by the FPGA. SAFETY: while the FPGA is unconfigured its pins float, so
# /OE is pulled UP (outputs off) and DIR pulled DOWN (toward the FPGA). An
# unconfigured card never drives the console's data bus (check_card.py enforces it).
U105 = {"1": "+3V3", "2": "F_DDIR", "22": "F_DOE_N", "23": "+5V_CON", "24": "+5V_CON",
        "11": "GND", "12": "GND", "13": "GND"}
U105.update({str(3 + i): f"F_D{i}" for i in range(8)})              # A1-A8 = pins 3-10
U105.update({str(21 - i): f"T_D{i}" for i in range(8)})             # B1-B8 = pins 21-14
part("U105", "Logic_LevelTranslator:SN74LVC8T245", "SN74LVC8T245PW", "Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm",
     "bus", U105)
cap("C105", "100n", "+3V3", "bus")
cap("C106", "100n", "+5V_CON", "bus")
res("R101", "10k", "F_DOE_N", "+3V3", "bus")      # /OE pull-up: off until the FPGA says otherwise
res("R102", "10k", "F_DDIR", "GND", "bus")        # DIR pull-down: toward the FPGA
for i in range(8):                                 # 33 ohm on each data line, console side (stage 1)
    res(f"R{110 + i}", "33", f"T_D{i}", f"BUS_D{i}", "bus")

# --- /IRQ2: shared line, open drain. 74LVC1G07 at 3.3 V (its output tolerates 5 V).
# Input pulled up so an unconfigured FPGA cannot raise an interrupt.
part("U106", "74xGxx:74LVC1G07", "74LVC1G07", "Package_TO_SOT_SMD:SOT-23-5", "bus",
     {"1": None, "2": "F_IRQ2_N", "3": "GND", "4": "BUS_IRQ2_N", "5": "+3V3"})
cap("C107", "100n", "+3V3", "bus")
res("R103", "10k", "F_IRQ2_N", "+3V3", "bus")

# --- scope test points on the bus (TEST_PLAN T3/T4b/T9) and the two spare FPGA balls
for ref, net in [("TP101", "BUS_RD_N"), ("TP102", "BUS_WR_N"), ("TP103", "BUS_D0"), ("TP104", "BUS_A20"),
                 ("TP105", "F_DOE_N"), ("TP106", "F_SPARE0"), ("TP107", "F_SPARE1"), ("TP108", "GND")]:
    part(ref, "Connector:TestPoint", net, "TestPoint:TestPoint_Pad_D1.0mm", "bus", {"1": net})

# --- power input: console 5 V and either USB port, OR-ed by Schottky diodes into +5V_CARD.
# USB can never back-feed the console's rail, and the console never feeds a PC.
for ref, src in [("D101", "+5V_CON"), ("D102", "VBUS_FT"), ("D103", "VBUS_RP")]:
    part(ref, "Device:D_Schottky", "B5819W", "Diode_SMD:D_SOD-123", "power", {"1": "+5V_CARD", "2": src})                                                 # pin 1 = K, pin 2 = A
cap("C108", "10u", "+5V_CON", "power", fp=C0603)

# --- RP2040 companion (FPGA-Companion; Raspberry Pi "minimal design"). Link pins are the
# firmware's defaults for a plain RP2040 build (fpga-companion src/rp2040/mcu_hw.c:
# PICO_DEFAULT_SPI pins 16-19, SPI_IRQ_PIN 22), so the firmware needs no board patch.
RP = {"19": "GND", "20": "RP_XIN", "21": "RP_XOUT", "24": "RP_SWCLK", "25": "RP_SWDIO", "26": "RP_RUN",
      "27": "CO_MISO", "28": "CO_CS_N", "29": "CO_SCK", "30": "CO_MOSI", "34": "CO_IRQ", "37": "RP_LED",
      "43": "+3V3", "44": "+3V3", "45": "+1V1_RP", "23": "+1V1_RP", "50": "+1V1_RP",
      "46": "RP_USB_DM", "47": "RP_USB_DP", "48": "+3V3", "57": "GND",
      "51": "RP_QSPI_SD3", "52": "RP_QSPI_SCLK", "53": "RP_QSPI_SD0", "54": "RP_QSPI_SD2",
      "55": "RP_QSPI_SD1", "56": "RP_QSPI_SS"}
for p in ("1", "10", "22", "33", "42", "49"):
    RP[p] = "+3V3"                                                     # IOVDD
for p in ("2", "3", "4", "5", "6", "7", "8", "9", "11", "12", "13", "14", "15", "16", "17", "18",
          "31", "32", "35", "36", "38", "39", "40", "41"):
    RP[p] = None
part("U107", "MCU_RaspberryPi:RP2040", "RP2040", "Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP3.2x3.2mm",
     "companion", RP, lcsc="C2040")
for i, net in enumerate(["+3V3"] * 6 + ["+1V1_RP"] * 2 + ["+3V3", "+3V3"]):   # IOVDD x6, DVDD x2, USB_VDD, ADC_AVDD
    cap(f"C{120 + i}", "100n", net, "companion")
cap("C130", "1u", "+3V3", "companion")             # VREG_VIN
cap("C131", "1u", "+1V1_RP", "companion")          # VREG_VOUT
part("U108", "Memory_Flash:W25Q16JVSS", "W25Q16JVSSIQ", "Package_SO:SOIC-8_5.3x5.3mm_P1.27mm", "companion",
     {"1": "RP_QSPI_SS", "2": "RP_QSPI_SD1", "3": "RP_QSPI_SD2", "4": "GND", "5": "RP_QSPI_SD0",
      "6": "RP_QSPI_SCLK", "7": "RP_QSPI_SD3", "8": "+3V3"})
cap("C132", "100n", "+3V3", "companion")
res("R120", "10k", "RP_QSPI_SS", "+3V3", "companion")       # flash deselected at reset
res("R121", "1k", "RP_QSPI_SS", "RP_BOOT", "companion")     # BOOTSEL: hold SW101 while plugging in -> USB mass storage
part("SW101", "Switch:SW_Push", "BOOTSEL", "icepi-lib:switch_button_TS-1088-AR02016", "companion",
     {"1": "RP_BOOT", "2": "GND"}, lcsc="C720477")
part("Y101", "Device:Crystal_GND24", "12MHz", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", "companion",
     {"1": "RP_XIN", "2": "GND", "3": "RP_XOUT_R", "4": "GND"})
res("R122", "1k", "RP_XOUT", "RP_XOUT_R", "companion")      # series resistor on XOUT (RP2040 minimal design)
cap("C133", "15p", "RP_XIN", "companion")
cap("C134", "15p", "RP_XOUT_R", "companion")
res("R123", "10k", "RP_RUN", "+3V3", "companion")
cap("C135", "100n", "RP_RUN", "companion")
res("R124", "1k", "RP_LED", "RP_LED_A", "companion")         # GPIO25: the firmware's status LED
part("D104", "Device:LED", "GREEN", "LED_SMD:LED_0603_1608Metric", "companion", {"1": "GND", "2": "RP_LED_A"},
     )
for ref, net in [("TP110", "RP_SWCLK"), ("TP111", "RP_SWDIO"), ("TP112", "RP_RUN")]:
    part(ref, "Connector:TestPoint", net, "TestPoint:TestPoint_Pad_D1.0mm", "companion", {"1": net})
# RP2040 USB-C: firmware updates (UF2) and the companion's debug console
part("J102", "Connector:USB_C_Receptacle_USB2.0_14P", "USB-C (companion)",
     "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "companion",
     {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "A4": "VBUS_RP", "A9": "VBUS_RP", "B4": "VBUS_RP",
      "B9": "VBUS_RP", "A5": "RP_CC1", "B5": "RP_CC2", "A6": "RP_DP", "B6": "RP_DP", "A7": "RP_DM", "B7": "RP_DM",
      "SH": "GND"}, lcsc="C2765186")
res("R125", "5.1k", "RP_CC1", "GND", "companion")
res("R126", "5.1k", "RP_CC2", "GND", "companion")
res("R127", "27", "RP_USB_DP", "RP_DP", "companion")
res("R128", "27", "RP_USB_DM", "RP_DM", "companion")
part("U109", f"{ICEPI_SYM}:Power_Protection__TPD2EUSB30A", "TPD2EUSB30A", "icepi-lib:Texas_DRT-3", "companion",
     {"1": "RP_DP", "2": "RP_DM", "3": "GND"}, lcsc="C3011197")
cap("C136", "10u", "VBUS_RP", "companion", fp=C0603)

# --- audio: PCM5102A stereo DAC (I2S from the FPGA, no master clock: SCK tied low ->
# internal PLL from BCK). Ground-centred outputs -> 470 ohm / 2.2 nF filter -> jack.
# Mono to the console: L and R summed through 10k each, AC-coupled into card pin 2.
# The level into the console is a first guess: R133 is "tune at bring-up" (TEST_PLAN).
part("U110", "Audio:PCM5102A", "PCM5102APWR", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", "audio",
     {"1": "+3V3", "2": "DAC_CAPP", "3": "GND", "4": "DAC_CAPM", "5": "DAC_VNEG", "6": "DAC_OUTL",
      "7": "DAC_OUTR", "8": "+3V3", "9": "GND", "10": "GND", "11": "GND", "12": "GND",
      "13": "F_I2S_BCK", "14": "F_I2S_DIN", "15": "F_I2S_LRCK", "16": "GND", "17": "DAC_XSMT",
      "18": "DAC_LDOO", "19": "GND", "20": "+3V3"})
cap("C140", "2.2u", "DAC_CAPP", "audio", b="DAC_CAPM", fp=C0603)   # charge pump flying cap
cap("C141", "2.2u", "DAC_VNEG", "audio", fp=C0603)
cap("C142", "1u", "DAC_LDOO", "audio")
cap("C143", "100n", "+3V3", "audio")   # CPVDD
cap("C144", "100n", "+3V3", "audio")   # AVDD
cap("C145", "100n", "+3V3", "audio")   # DVDD
cap("C146", "10u", "+3V3", "audio", fp=C0603)
res("R130", "10k", "DAC_XSMT", "+3V3", "audio")              # soft-mute off: play
res("R131", "470", "DAC_OUTL", "AUD_L", "audio")
res("R132", "470", "DAC_OUTR", "AUD_R", "audio")
cap("C147", "2.2n", "AUD_L", "audio")
cap("C148", "2.2n", "AUD_R", "audio")
part("J103", "Connector_Audio:AudioJack3", "3.5 mm stereo", "Connector_Audio:Jack_3.5mm_CUI_SJ1-3523N_Horizontal",
     "audio", {"T": "AUD_L", "R": "AUD_R", "S": "GND"})
res("R134", "10k", "AUD_L", "AUD_MIX", "audio")
res("R135", "10k", "AUD_R", "AUD_MIX", "audio")
res("R133", "4.7k", "AUD_MIX", "GND", "audio")               # level into the console: tune at bring-up
cap("C149", "10u", "AUD_MIX", "audio", b="BUS_AUDIO", fp=C0603)

# --- tell ERC who drives each rail
for i, net in enumerate(["+5V_CON", "+5V_CARD", "VBUS_FT", "VBUS_RP", "+3V3", "+2V5", "+1V1",
                         "PWR_FILTERED_2V5", "GND"]):
    part(f"#FLG1{i:02d}", "power:PWR_FLAG", "PWR_FLAG", "", "power", {"1": net})

SHEETS = ["bus", "power", "fpga", "flash", "sdram", "sd", "usb_jtag", "companion", "audio"]
SHEET_TITLES = {"bus": "Card edge and bus translators", "power": "Power: input OR-ing and Icepi regulators",
                "fpga": "FPGA clock, LEDs, buttons (Icepi)", "flash": "Configuration flash (Icepi)",
                "sdram": "SDRAM (Icepi)", "sd": "microSD (Icepi)", "usb_jtag": "USB-JTAG/UART, FT231X (Icepi)",
                "companion": "RP2040 companion", "audio": "Audio DAC, jack, mono to console"}
