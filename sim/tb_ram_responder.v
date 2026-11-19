// Testbench: the RAM responder on a model of the board and the console's bus.
//
//   sh sim/run_ram_responder.sh      (runs the good design AND two broken ones)
//
// WHAT IS MODELLED
//   console: HuC6280-style cycles at 7.16 MHz (139.7 ns), asynchronous to the
//            FPGA clock (random start phase). Address setup before /RD or /WR,
//            strobe width, data setup/hold are PARAMETERS: the real values come
//            from TEST_PLAN T3 on the scope. Defaults are deliberately tight.
//   board:   74HCT688 decode delay, 74LVC245A input delay, SN74LVC8T245 data
//            delay, its direction from /RD and enable from /SEL (as wired).
// WHAT IS CHECKED
//   1 every read of our window returns what was last written there
//   2 writes outside our window ($00-$7F HuCard space, $88-$FF, and in 8 KB
//     mode $81-$87) change nothing
//   3 the FPGA never drives its data pins while the translator drives them
//     (direction bus->FPGA), beyond a short turnaround window
//   4 the margin: how long before the console samples the data was already right
// WHAT IS NOT
//   the real HuC6280 pin timing (T3), metastability (behavioural sync), the
//   Gowin PLL (an ideal 108 MHz clock here), analog effects.
`timescale 1ns/1ps
`default_nettype none
module tb;
    parameter ADDR_BITS = 13;
    // console timing (ns); +overridable with plusargs
    real T_CYC = 139.7, T_AS = 20.0, T_STROBE = 60.0, T_SU = 10.0, T_DH = 5.0, T_WDV = 10.0;
    // board delays (ns), datasheet maxima at 5 V / 3.3 V, rounded up
    real T_688 = 35.0, T_245 = 7.0, T_8T245 = 8.0;
    real TURNAROUND = 15.0;          // allowed FPGA/translator overlap at a direction change

    // ---------------------------------------------------------------- console side
    reg  [20:0] A = 0;
    reg         RD_N = 1, WR_N = 1;
    reg  [7:0]  cpu_d = 0;
    reg         cpu_drive = 0;
    wire [7:0]  BUS_D;
    assign BUS_D = cpu_drive ? cpu_d : 8'hzz;

    // ---------------------------------------------------------------- board
    reg sel_n_raw = 1;
    always @(A) sel_n_raw <= #(T_688) !(A[20:16] == 5'b10000);
    // input translators (fixed bus -> FPGA)
    reg [15:0] f_a = 0; reg f_rd_n = 1, f_wr_n = 1, f_sel_n = 1;
    always @(A)         f_a     <= #(T_245) A[15:0];
    always @(RD_N)      f_rd_n  <= #(T_245) RD_N;
    always @(WR_N)      f_wr_n  <= #(T_245) WR_N;
    always @(sel_n_raw) f_sel_n <= #(T_245) sel_n_raw;
    // data translator: enabled when SEL_N low; DIR = /RD (high: bus -> FPGA)
    wire        dt_on    = !sel_n_raw;
    wire        dt_to_bus = dt_on && !RD_N;
    wire        dt_to_fpga = dt_on && RD_N;
    wire [7:0]  fpga_pins;
    reg  [7:0]  bus_from_board = 8'hzz, fpga_from_board = 8'hzz;
    always @(*) bus_from_board  <= #(T_8T245) (dt_to_bus  ? fpga_pins : 8'hzz);
    always @(*) fpga_from_board <= #(T_8T245) (dt_to_fpga ? BUS_D    : 8'hzz);
    assign BUS_D = bus_from_board;

    // ---------------------------------------------------------------- FPGA
    reg clk = 0;
    real phase;
    initial begin phase = ($urandom % 9259) / 1000.0; #(phase); forever #4.6296 clk = ~clk; end   // 108 MHz
    wire [7:0] d_out; wire d_oe; wire wstb;
    assign fpga_pins = d_oe ? d_out : fpga_from_board;
    ram_responder #(.ADDR_BITS(ADDR_BITS)) dut (
        .clk(clk), .a(f_a), .rd_n(f_rd_n), .wr_n(f_wr_n), .sel_n(f_sel_n),
        .d_in(fpga_pins), .d_out(d_out), .d_oe(d_oe), .write_strobe(wstb));

    // ---------------------------------------------------------------- check 3: no fight at the FPGA pins
    real fight_start = -1, fight_max = 0;
    integer fights = 0;
    always @(d_oe or dt_to_fpga) begin
        if (d_oe && dt_to_fpga && fight_start < 0) fight_start = $realtime;
        if (!(d_oe && dt_to_fpga) && fight_start >= 0) begin
            if ($realtime - fight_start > fight_max) fight_max = $realtime - fight_start;
            if ($realtime - fight_start > TURNAROUND) fights = fights + 1;
            fight_start = -1;
        end
    end

    // ---------------------------------------------------------------- scoreboard
    reg [7:0] model [0:65535];
    integer errors = 0, reads = 0, writes = 0, outside_writes = 0, i;
    real margin_min = 1e9, last_change, t_addr, lat_max = 0;
    always @(BUS_D) last_change = $realtime;

    function in_window(input [20:0] addr);
        in_window = (addr[20:16] == 5'b10000) && (ADDR_BITS == 16 || addr[15:13] == 3'b000);
    endfunction

    task bus_write(input [20:0] addr, input [7:0] data);
        real t0;
        begin
            t0 = $realtime;
            A = addr;
            #(T_AS) WR_N = 0;
            #(T_WDV) begin cpu_d = data; cpu_drive = 1; end
            #(T_STROBE - T_WDV) WR_N = 1;
            #(T_DH) cpu_drive = 0;
            #(T_CYC - T_AS - T_STROBE - T_DH);
            writes = writes + 1;
            if (in_window(addr)) model[addr[15:0] & ((1 << ADDR_BITS) - 1)] = data;
            else outside_writes = outside_writes + 1;
        end
    endtask

    task bus_read(input [20:0] addr, output [7:0] got);
        begin
            A = addr;
            t_addr = $realtime;
            #(T_AS) RD_N = 0;
            #(T_STROBE - T_SU);
            got = BUS_D;
            if (in_window(addr)) begin
                reads = reads + 1;
                if (got !== model[addr[15:0] & ((1 << ADDR_BITS) - 1)]) begin
                    errors = errors + 1;
                    if (errors <= 5) $display("  MISMATCH read %06h: got %02h want %02h at %0t", addr, got,
                                              model[addr[15:0] & ((1 << ADDR_BITS) - 1)], $time);
                end else begin
                    if ($realtime - last_change < margin_min) margin_min = $realtime - last_change;
                    if (last_change - t_addr > lat_max) lat_max = last_change - t_addr;
                end
            end
            #(T_SU) RD_N = 1;
            #(T_CYC - T_AS - T_STROBE);
        end
    endtask

    function [20:0] rand_window_addr(input integer dummy);
        rand_window_addr = {5'b10000, 16'((ADDR_BITS == 16) ? $urandom % 65536 : $urandom % 8192)};
    endfunction

    reg [7:0] got;
    integer n, kind, OPS;
    reg [20:0] ad;
    initial begin
        if ($value$plusargs("strobe=%f", T_STROBE)) ;
        if ($value$plusargs("as=%f", T_AS)) ;
        if (!$value$plusargs("ops=%d", OPS)) OPS = 6000;
        for (i = 0; i < 65536; i = i + 1) model[i] = 8'h00;
        #200;
        // fill the window with "address in data", read it all back
        for (n = 0; n < (1 << ADDR_BITS); n = n + 1) bus_write({5'b10000, n[15:0]}, n[7:0] ^ n[15:8] ^ 8'h5a);
        for (n = 0; n < (1 << ADDR_BITS); n = n + 1) bus_read({5'b10000, n[15:0]}, got);
        // random mix: in-window reads/writes, writes outside (HuCard area, other banks)
        for (n = 0; n < OPS; n = n + 1) begin
            kind = $urandom % 10;
            if (kind < 4) bus_read(rand_window_addr(0), got);
            else if (kind < 7) bus_write(rand_window_addr(0), $urandom);
            else if (kind < 8) bus_write({1'b0, 20'($urandom)}, $urandom);                     // HuCard space
            else if (kind < 9) bus_write({5'(5'b10001 + $urandom % 15), 16'($urandom)}, $urandom); // $88-$FF
            else bus_write({5'b10000, 3'(3'd1 + $urandom % 7), 13'($urandom)}, $urandom);       // $81-$87 (outside in 8 KB mode)
        end
        // final sweep: everything in the window still matches the model
        for (n = 0; n < (1 << ADDR_BITS); n = n + 1) bus_read({5'b10000, n[15:0]}, got);

        $display("ADDR_BITS=%0d strobe=%0.1f ns as=%0.1f ns: %0d writes (%0d outside), %0d reads checked",
                 ADDR_BITS, T_STROBE, T_AS, writes, outside_writes, reads);
        $display("  data errors: %0d", errors);
        $display("  FPGA/translator overlaps longer than %0.0f ns: %0d (longest %0.1f ns)", TURNAROUND, fights, fight_max);
        $display("  read margin: data was right %0.1f ns before the console sampled it (worst case)", margin_min);
        $display("  read latency: our data settled on the bus %0.1f ns after the address changed (worst case)", lat_max);
        if (errors == 0 && fights == 0 && reads > 0) $display("RESULT: PASS");
        else $display("RESULT: FAIL");
        $finish;
    end
endmodule
`default_nettype wire
