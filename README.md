Telemetry Power Governor RTL — README
=====================================

**Project**: Small power governor RTL demonstrating counters, a 4-state FSM governor, thermal interface, EWMA predictor, and workload classification.

**Quick start (local)**

Prerequisites:
- macOS or Linux
- Homebrew (mac) or system package manager
- Icarus Verilog (iverilog) and `vvp` for simulation
- GTKWave for waveform viewing (optional)

Install (macOS):

```bash
brew install icarus-verilog gtkwave
```

Run tests:

```bash
# counters
iverilog -g2012 -o tb_counters.vvp tb_counters.v counters.v
vvp tb_counters.vvp

# reg_interface (make sure reg_interface.v is compiled first)
iverilog -g2012 -o tb_reg_interface.vvp reg_interface.v counters.v tb_reg_interface.v
vvp tb_reg_interface.vvp

# power_fsm
iverilog -g2012 -o tb_power_fsm.vvp power_fsm.v reg_interface.v counters.v tb_power_fsm.v
vvp tb_power_fsm.vvp

# Arbiter integration (direct windows)
iverilog -g2012 -o tb_power_arbiter_direct.vvp tb_power_arbiter_direct.v power_arbiter.v power_fsm.v reg_interface.v counters.v
vvp tb_power_arbiter_direct.vvp
```

After a run, open the generated waveform `dump.vcd` with GTKWave:

```bash
gtkwave dump.vcd
```

**Files**

- `counters.v` — 100-cycle window counters and `window_done` pulse.
- `reg_interface.v` — register interface, `thermal_thresh_in`, `thermal_alarm`, `clk_en` policy.
- `power_fsm.v` — FSM governor: thermal override, dwell/hysteresis, EWMA predictor, workload classification.
- `tb_counters.v`, `tb_reg_interface.v`, `tb_power_fsm.v` — testbenches.
- `REPORT.md` — detailed report (this repo).

**EDA Playground**

- Copy-paste the files into EDA Playground (https://www.edaplayground.com/).
- Select Icarus Verilog and add compiler flag `-g2012`.
- Choose the top module (`tb_power_fsm` or other testbench) and run.
- Use the Waveform tab to view signals interactively.

**Design notes**

- The FSM reacts only on the `window_done` pulse to avoid per-cycle churn.
- The EWMA predictor uses alpha=1/8 implemented as shifts for synthesis friendliness.
- `DWELL` parameter controls hysteresis — higher values reduce oscillation, increase reaction latency.

**Next steps**

- Implement `power_arbiter` to coordinate multiple subsystems (Level 2).
- Add configurable `window_len` register.
- Add logging registers for state transitions and timestamps.

**License**

- Use as you wish for hackathon/demo purposes. No warranty.

**Author**
- Work performed by repository owner (local modifications and tests) — 28 March 2026.
