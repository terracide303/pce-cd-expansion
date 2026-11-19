"""Stage 1 RAM-responder board: the circuit, as data.

Every part and every pin's net, keyed by pin NUMBER (names repeat: GND, VCCB).
tools/gen_stage1.py turns this into a KiCad schematic; tools/check_stage1.py
compares KiCad's own netlist of that schematic back against this file AND
against rules derived independently from docs/ext_bus_pinout.csv and
docs/tang_nano_20k_header.csv. See docs/STAGE1.md for why each choice was made.

Net naming:
  BUS_*  the console's 5 V bus side          (e.g. BUS_A0, BUS_RD_N)
  F_*    the FPGA's 3.3 V side               (e.g. F_A0, F_RD_N)
  T_D*   between the data translator and its series resistors
  SEL_N  our decoded bank select, 5 V, active low
  +5VA   the console's analog 5 V (bus-side supply), +3V3 the Tang's 3.3 V, GND
  None   not connected (gets a no-connect flag)
"""
import csv, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------- the port (J1)
# Built from the cross-checked pinout so the connector can't disagree with it.
USED_BUS = {f"A{i}" for i in range(21)} | {f"D{i}" for i in range(8)} | {"/RD", "/WR", "+5VA", "GND"}


def bus_net(signal):
    if signal == "+5VA" or signal == "GND":
        return signal
    if signal not in USED_BUS:
        return None                        # video, audio, IRQ, reset ...: not used in stage 1
    return "BUS_" + signal.replace("/", "") + ("_N" if signal.startswith("/") else "")


EXT_BUS = list(csv.DictReader(open(ROOT / "docs" / "ext_bus_pinout.csv", encoding="utf-8")))
J1_PINS = {r["pin"]: bus_net(r["signal"]) for r in EXT_BUS}

# ---------------------------------------------------------------- the Tang Nano 20K (A1)
# FPGA pin -> net. Data on "free" pins (bidirectional, nothing else on them);
# address on LED / amp / EDID pins (inputs only, harmless); A13-A15 on three
# BL616 lines that are UNVERIFIED (docs/STAGE1.md: 8 KB until test T5 passes).
FPGA = {
    27: "F_D0", 28: "F_D1", 25: "F_D2", 26: "F_D3", 29: "F_D4", 30: "F_D5", 31: "F_D6", 77: "F_D7",
    42: "F_A0", 41: "F_A1", 48: "F_A2", 49: "F_A3",
    15: "F_A4", 16: "F_A5", 17: "F_A6", 18: "F_A7", 19: "F_A8", 20: "F_A9",
    51: "F_A10", 54: "F_A11", 55: "F_A12",
    71: "F_A13", 72: "F_A14", 73: "F_A15",
    56: "F_RD_N", 52: "F_WR_N", 53: "F_SEL_N",
}
HEADER = list(csv.DictReader(open(ROOT / "docs" / "tang_nano_20k_header.csv", encoding="utf-8")))


def header_net(row):
    io = row["io_name"]
    if io == "3V3":
        return "+3V3"
    if io == "GND":
        return "GND"
    if io == "5V":
        return None                        # the Tang's USB 5 V never touches the console
    return FPGA.get(int(row["fpga_pin"]))


# One part for the whole module, pins named by header position (L1..L20, R1..R20),
# so the 20.32 mm row spacing lives in one footprint and can't drift at layout.
A1_PINS = {r["header_pos"]: header_net(r) for r in HEADER}

# ---------------------------------------------------------------- the chips
# U1 74HCT688: P=R goes low when A20..A16 = 1 0000 (banks $80-$87). 5 V side.
U1 = {"1": "GND",                                   # G (enable, active low): always on
      "2": "BUS_A16", "4": "BUS_A17", "6": "BUS_A18", "8": "BUS_A19", "11": "BUS_A20",   # P0-P4
      "3": "GND", "5": "GND", "7": "GND", "9": "GND", "12": "+5VA",                      # R0-R4 = 0,0,0,0,1
      "13": "GND", "14": "GND", "15": "GND", "16": "GND", "17": "GND", "18": "GND",      # P5-P7 = R5-R7
      "19": "SEL_N", "10": "GND", "20": "+5VA"}

# U2 SN74LVC8T245, data. A side = console (VCCA 5 V), B side = FPGA (VCCB 3.3 V).
# DIR high = A->B (bus to FPGA); DIR = /RD, so the FPGA drives the bus only
# while /RD is low. /OE = SEL_N: only for our banks. Both are 5 V signals,
# and DIR and /OE are referenced to VCCA = 5 V.
U2 = {"1": "+5VA", "2": "BUS_RD_N", "22": "SEL_N", "23": "+3V3", "24": "+3V3",
      "11": "GND", "12": "GND", "13": "GND"}
U2.update({str(3 + i): f"BUS_D{i}" for i in range(8)})          # A1-A8 = pins 3-10
U2.update({str(21 - i): f"T_D{i}" for i in range(8)})           # B1-B8 = pins 21-14


def lvc245(inputs, outputs):
    """SN74LVC245A at 3.3 V, fixed A->B (bus to FPGA). Its inputs tolerate 5 V."""
    pins = {"1": "+3V3", "19": "GND", "10": "GND", "20": "+3V3"}  # DIR high = A->B; /OE low = on
    for i in range(8):
        pins[str(2 + i)] = inputs[i]                            # A1-A8 = pins 2-9
        pins[str(18 - i)] = outputs[i]                          # B1-B8 = pins 18-11
    return pins


U3 = lvc245([f"BUS_A{i}" for i in range(8)], [f"F_A{i}" for i in range(8)])
U4 = lvc245([f"BUS_A{i}" for i in range(8, 16)], [f"F_A{i}" for i in range(8, 16)])
# Unused inputs are tied low (a floating CMOS input oscillates); their outputs are left open.
U5 = lvc245(["BUS_RD_N", "BUS_WR_N", "SEL_N", "GND", "GND", "GND", "GND", "GND"],
            ["F_RD_N", "F_WR_N", "F_SEL_N", None, None, None, None, None])

# ---------------------------------------------------------------- everything, with symbols and footprints
PARTS = [
    dict(ref="J1", sym="pce_exp:PCE_EXT_BUS", value="PCE EXT BUS (3x23 female)",
         fp="pce_exp:PinSocket_3x23_P2.54mm_Vertical", pins=J1_PINS),
    dict(ref="A1", sym="pce_exp:TANG_NANO_20K", value="Tang Nano 20K (on 2x 1x20 female headers)",
         fp="pce_exp:TangNano20K_Sockets", pins=A1_PINS),
    dict(ref="U1", sym="74xx:74HCT688", value="74HCT688", fp="Package_SO:SOIC-20W_7.5x12.8mm_P1.27mm", pins=U1),
    dict(ref="U2", sym="Logic_LevelTranslator:SN74LVC8T245", value="SN74LVC8T245",
         fp="Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm", pins=U2),
    dict(ref="U3", sym="Logic_LevelTranslator:SN74LVC245APW", value="SN74LVC245APW",
         fp="Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", pins=U3),
    dict(ref="U4", sym="Logic_LevelTranslator:SN74LVC245APW", value="SN74LVC245APW",
         fp="Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", pins=U4),
    dict(ref="U5", sym="Logic_LevelTranslator:SN74LVC245APW", value="SN74LVC245APW",
         fp="Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", pins=U5),
]
# Series resistors limit current during the few ns the data direction flips.
for i in range(8):
    PARTS.append(dict(ref=f"R{i + 1}", sym="Device:R", value="33", fp="Resistor_SMD:R_0603_1608Metric",
                      pins={"1": f"T_D{i}", "2": f"F_D{i}"}))
# Decoupling: 100 nF at every supply pin, 10 uF bulk per rail.
for ref, net, val, fp in [("C1", "+5VA", "100n", "C_0603_1608Metric"), ("C2", "+5VA", "100n", "C_0603_1608Metric"),
                          ("C3", "+3V3", "100n", "C_0603_1608Metric"), ("C4", "+3V3", "100n", "C_0603_1608Metric"),
                          ("C5", "+3V3", "100n", "C_0603_1608Metric"), ("C6", "+3V3", "100n", "C_0603_1608Metric"),
                          ("C7", "+5VA", "10u", "C_0805_2012Metric"), ("C8", "+3V3", "10u", "C_0805_2012Metric")]:
    PARTS.append(dict(ref=ref, sym="Device:C", value=val, fp=f"Capacitor_SMD:{fp}", pins={"1": net, "2": "GND"}))
# Scope test points for docs/TEST_PLAN.md T3 and T9.
for ref, net in [("TP1", "BUS_RD_N"), ("TP2", "BUS_D0"), ("TP3", "SEL_N"), ("TP4", "BUS_A20"), ("TP5", "GND"), ("TP6", "GND")]:
    PARTS.append(dict(ref=ref, sym="Connector:TestPoint", value=net, fp="TestPoint:TestPoint_THTPad_D1.5mm_Drill0.7mm",
                      pins={"1": net}))
# Tell ERC who supplies each rail (they come in through connectors).
for i, net in enumerate(["+5VA", "+3V3", "GND"]):
    PARTS.append(dict(ref=f"#FLG0{i + 1}", sym="power:PWR_FLAG", value="PWR_FLAG", fp="", pins={"1": net}))
