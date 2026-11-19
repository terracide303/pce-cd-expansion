#!/bin/sh
# Simulate the stage-1 RAM responder: the real design must PASS, three broken
# copies must FAIL (a bench that has never failed has not been tested).
#   sh sim/run_ram_responder.sh
set -e
cd "$(dirname "$0")/.."
IV=${IVERILOG:-iverilog}; VVP=${VVP:-vvp}
command -v "$IV" >/dev/null 2>&1 || { IV=/c/iverilog/bin/iverilog; VVP=/c/iverilog/bin/vvp; }
OUT=sim/out; mkdir -p "$OUT"
status=0

run() {   # label rtl_file addr_bits plusargs expect
    "$IV" -g2012 -o "$OUT/tb.vvp" -P tb.ADDR_BITS="$3" sim/tb_ram_responder.v "$2"
    res=$("$VVP" -n "$OUT/tb.vvp" $4 | tee "$OUT/$1.log" | grep RESULT | awk '{print $2}')
    if [ "$res" = "$5" ]; then mark=ok; else mark=WRONG; status=1; fi
    printf '  %-5s %-44s %s (expected %s)\n' "$mark" "$1" "$res" "$5"
    grep -E "errors|overlaps|margin|latency" "$OUT/$1.log" | sed 's/^/          /'
}

echo "the real design:"
run "8KB, nominal (strobe 60 ns)"        rtl/ram_responder.v 13 "+strobe=60" PASS
run "64KB, nominal"                      rtl/ram_responder.v 16 "+strobe=60" PASS

echo "broken copies (each must FAIL):"
sed 's/assign d_oe = .*/assign d_oe = ~sel_n;/' rtl/ram_responder.v > "$OUT/broken_drive.v"
run "drives during writes too"            "$OUT/broken_drive.v" 13 "+strobe=60 +ops=1500" FAIL
sed 's/mem\[wa\]      <= wd;/;/' rtl/ram_responder.v > "$OUT/broken_nowrite.v"
run "never commits a write"               "$OUT/broken_nowrite.v" 13 "+strobe=60 +ops=1500" FAIL
sed 's/if (!wr_n_s \&\& !sel_n_s \&\& in_window)/if (!wr_n_s)/' rtl/ram_responder.v > "$OUT/broken_decode.v"
run "writes on any address"               "$OUT/broken_decode.v" 13 "+strobe=60 +ops=1500" FAIL

echo "sweep: how early can the console sample? (address setup 10 ns; sample = setup + strobe - 10 ns)"
for s in 30 35 40 45 50 55; do
    "$IV" -g2012 -o "$OUT/tb.vvp" -P tb.ADDR_BITS=13 sim/tb_ram_responder.v rtl/ram_responder.v
    r=$("$VVP" -n "$OUT/tb.vvp" +strobe=$s +as=10 +ops=1500 | grep -E "RESULT|data errors" | tr '
' ' ')
    printf '    sample at %3d ns after the address: %s
' $((10 + s - 10)) "$r"
done

[ $status = 0 ] && echo "ALL AS EXPECTED" || echo "SOMETHING UNEXPECTED"
exit $status
