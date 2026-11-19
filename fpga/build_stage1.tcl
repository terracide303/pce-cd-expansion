# Stage 1 RAM responder for the Tang Nano 20K. Run from the repo root:
#   C:/Gowin/Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe fpga/build_stage1.tcl
# Read the timing report (impl/pnr/*.tr) before flashing: the 108 MHz clock must close.
set_device GW2AR-LV18QN88C8/I7 -device_version C
add_file rtl/stage1_top.v
add_file rtl/ram_responder.v
add_file fpga/stage1.cst
add_file fpga/stage1.sdc
set_option -verilog_std sysv2017
set_option -synthesis_tool gowinsynthesis
set_option -output_base_name pce_exp_stage1
set_option -top_module stage1_top
set_option -use_mspi_as_gpio 1
set_option -use_sspi_as_gpio 1
set_option -use_ready_as_gpio 1
set_option -use_done_as_gpio 1
set_option -rw_check_on_ram 1
set_option -timing_driven 1
run all
