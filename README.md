Telemetry Power Governor RTL — README
=====================================

**What is this project?**

This repository provides a compact, practical RTL reference implementation of a telemetry-driven power governor for SoC subsystems. The goal is to show how simple digital building blocks — cycle counters, a small finite-state machine (FSM), and a register interface — can be combined to measure workload, predict near-term activity, and make safe, temperature-aware power-state decisions in hardware.

Key points:

- Purpose: a small, synthesizable-friendly demo that demonstrates hardware power management techniques for hackathon demos, teaching, and quick SoC prototyping.
- Inputs: per-cycle telemetry (`activity_in`, `stall_in`) and a simulated temperature (`temp_in`).
- Decision cadence: the design evaluates measured telemetry once per observation window (`window_done`), avoiding per-cycle churn.
- Policy: a 4-state governor (`SLEEP`, `LOW_POWER`, `ACTIVE`, `TURBO`) with thermal override, hysteresis (dwell), and a lightweight EWMA predictor to pre-scale on ramps.
- Observability: testbenches produce `dump.vcd` waveforms and a small graphing tool is included to visualize power states, EWMA, and the arbiter grants.

Who this is for:

- Hardware engineers prototyping a PMU policy.
- Students learning about clock-gating, telemetry-driven governors, and simple predictors.
- Hackathon teams wanting a verifiable, testbench-driven demo to present.

Continue with the Quick start below to compile and run the included testbenches and generate waveforms.

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
