// Stage 1 timing: the on-board 27 MHz; the rPLL's 108 MHz output is derived by Gowin.
// The console bus is asynchronous: it enters through the two-stage synchroniser in
// rtl/ram_responder.v, and its pins are not constrained against our clock.
create_clock -name clk_27m -period 37.037 [get_ports {clk_27m}]
