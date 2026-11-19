// Stage 1 top level for the Tang Nano 20K: the RAM responder on the expansion bus.
//
// Clock: the on-board 27 MHz -> rPLL -> 108 MHz sampling clock.
//   CLKOUT = 27 x (FBDIV_SEL+1) / (IDIV_SEL+1) = 27 x 4 / 1 = 108 MHz
//   PFD = 27 MHz; VCO = 108 x ODIV(8) = 864 MHz (400-1200 MHz, in range)
// Same rPLL instantiation pattern as PCEHeroTN rtl/clocks.v (built on this board).
//
// Pins: fpga/stage1.cst is GENERATED from hw/stage1/design.py by tools/gen_cst.py,
// the same pin map the schematic was drawn from.
`default_nettype none
module stage1_top #(
    parameter ADDR_BITS = 13               // 13 = 8 KB until TEST_PLAN T5 passes, then 16
) (
    input  wire        clk_27m,
    input  wire [15:0] bus_a,              // A0-A15 via the input translators
    input  wire        bus_rd_n,
    input  wire        bus_wr_n,
    input  wire        bus_sel_n,          // 74HCT688: banks $80-$87
    inout  wire [7:0]  bus_d               // via the SN74LVC8T245
);
    wire gnd = 1'b0, vcc = 1'b1;
    wire clk, locked;

    rPLL pll (
        .CLKOUT(clk), .LOCK(locked), .CLKOUTP(), .CLKOUTD(), .CLKOUTD3(),
        .RESET(gnd), .RESET_P(gnd), .CLKIN(clk_27m), .CLKFB(gnd),
        .FBDSEL({gnd,gnd,gnd,gnd,gnd,gnd}), .IDSEL({gnd,gnd,gnd,gnd,gnd,gnd}),
        .ODSEL({gnd,gnd,gnd,gnd,gnd,gnd}), .PSDA({gnd,gnd,gnd,gnd}),
        .DUTYDA({gnd,gnd,gnd,gnd}), .FDLY({vcc,vcc,vcc,vcc})
    );
    defparam pll.FCLKIN = "27";
    defparam pll.DYN_IDIV_SEL = "false";
    defparam pll.IDIV_SEL = 0;             // /1
    defparam pll.DYN_FBDIV_SEL = "false";
    defparam pll.FBDIV_SEL = 3;            // x4
    defparam pll.DYN_ODIV_SEL = "false";
    defparam pll.ODIV_SEL = 8;
    defparam pll.PSDA_SEL = "0000";
    defparam pll.DYN_DA_EN = "false";
    defparam pll.DUTYDA_SEL = "1000";
    defparam pll.CLKOUT_FT_DIR = 1'b1;
    defparam pll.CLKOUTP_FT_DIR = 1'b1;
    defparam pll.CLKOUT_DLY_STEP = 0;
    defparam pll.CLKOUTP_DLY_STEP = 0;
    defparam pll.CLKFB_SEL = "internal";
    defparam pll.CLKOUT_BYPASS = "false";
    defparam pll.CLKOUTP_BYPASS = "false";
    defparam pll.CLKOUTD_BYPASS = "false";
    defparam pll.DYN_SDIV_SEL = 2;
    defparam pll.CLKOUTD_SRC = "CLKOUT";
    defparam pll.CLKOUTD3_SRC = "CLKOUT";
    defparam pll.DEVICE = "GW2AR-18C";

    wire [7:0] d_out;
    wire       d_oe;
    // Until the PLL locks, the responder must not drive anything.
    assign bus_d = (d_oe && locked) ? d_out : 8'hzz;

    ram_responder #(.ADDR_BITS(ADDR_BITS)) responder (
        .clk(clk), .a(bus_a), .rd_n(bus_rd_n), .wr_n(bus_wr_n), .sel_n(bus_sel_n),
        .d_in(bus_d), .d_out(d_out), .d_oe(d_oe), .write_strobe()
    );
endmodule
`default_nettype wire
