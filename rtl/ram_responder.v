// Stage 1: answer the PC Engine's bus as RAM at banks $80-$87.
//
// The console's bus is asynchronous to us. Every input is sampled through the
// SAME two-stage synchroniser on a fast clock (108 MHz from the Tang's 27 MHz
// in the top level), so address, data and strobes stay aligned with each other.
//
// READ:  RAM is read continuously at the current (synchronised) address, so the
//        data is waiting before /RD falls. The data pins are driven only while
//        /RD and /SEL are both low, decided combinationally from the raw pins
//        (no clock delay). The board's data translator turns round on /RD too
//        (docs/STAGE1.md decision 4), so the two agree on the direction.
// WRITE: committed on /WR's rising edge (synchronised), with the address and
//        data from the last sample taken while /WR was still low.
//
// sel_n comes from the board's 74HCT688 (A20..A16 = 1 0000). The bank bits
// A13-A15 inside $80-$87 are only used when ADDR_BITS = 16 (64 KB); the first
// image uses 13 (8 KB) until the BL616 lines carrying A13-A15 pass test T5.
`default_nettype none
module ram_responder #(
    parameter ADDR_BITS = 13           // 13 = 8 KB (bank $80 only), 16 = 64 KB ($80-$87)
) (
    input  wire                 clk,   // fast sampling clock
    input  wire [15:0]          a,     // bus A0-A15 through the input translators
    input  wire                 rd_n,
    input  wire                 wr_n,
    input  wire                 sel_n, // our bank decode, active low
    input  wire [7:0]           d_in,  // data pins, read side
    output wire [7:0]           d_out, // data pins, drive side
    output wire                 d_oe,  // drive the data pins
    // for a status LED / debug
    output reg                  write_strobe
);
    // ---------------------------------------------------------------- read side
    // Combinational: the moment the console asks for our data, drive it.
    // In 8 KB mode only bank $80 (A15-A13 = 0) answers. Reads of $81-$87 then
    // see an enabled translator with nothing behind it: undefined data, but no
    // contention, since nothing else lives at $80-$87.
    wire raw_in_window = (ADDR_BITS == 16) ? 1'b1 : (a[15:13] == 3'b000);
    assign d_oe = ~rd_n & ~sel_n & raw_in_window;

    // ---------------------------------------------------------------- one synchroniser for every input
    localparam W = 16 + 8 + 3;
    reg [W-1:0] s1, s2;
    always @(posedge clk) begin
        s1 <= {a, d_in, rd_n, wr_n, sel_n};
        s2 <= s1;
    end
    wire [15:0] a_s    = s2[W-1 -: 16];
    wire [7:0]  d_s    = s2[10:3];
    wire        wr_n_s = s2[1];
    wire        sel_n_s = s2[0];

    // ---------------------------------------------------------------- memory
    reg [7:0] mem [0:(1 << ADDR_BITS) - 1];
    // Simulation only: Gowin block RAM already powers up as zero, and its
    // synthesiser caps loops at 2000 iterations.
    // synthesis translate_off
    integer i;
    initial for (i = 0; i < (1 << ADDR_BITS); i = i + 1) mem[i] = 8'h00;
    // synthesis translate_on

    // In 8 KB mode only bank $80 answers: A13-A15 must be 0.
    wire in_window = (ADDR_BITS == 16) ? 1'b1 : (a_s[15:13] == 3'b000);

    // Continuous read, registered. The read address takes ONE sampling stage
    // (s1), not two: the RAM is re-read every clock, so a sample taken while the
    // address was changing is simply replaced by the next one. That saves a
    // clock (~9 ns) of read latency. Writes keep the full two-stage path.
    reg [7:0] rdata;
    always @(posedge clk) rdata <= mem[s1[W-1 -: 16] & ((1 << ADDR_BITS) - 1)];
    assign d_out = rdata;

    // Writes: remember the last sample taken while /WR was low and selected,
    // commit it when /WR goes high.
    reg [ADDR_BITS-1:0] wa;
    reg [7:0]           wd;
    reg                 pending;
    always @(posedge clk) begin
        write_strobe <= 1'b0;
        if (!wr_n_s && !sel_n_s && in_window) begin
            wa      <= a_s[ADDR_BITS-1:0];
            wd      <= d_s;
            pending <= 1'b1;
        end else if (wr_n_s && pending) begin
            mem[wa]      <= wd;
            pending      <= 1'b0;
            write_strobe <= 1'b1;
        end else if (!wr_n_s && (sel_n_s || !in_window)) begin
            pending <= 1'b0;           // a write elsewhere: not ours
        end
    end
    initial pending = 1'b0;
endmodule
`default_nettype wire
