EXPLAINER — "Like I'm 10 (Donkey Edition)"
=========================================

Quick TL;DR
------------
This project is a tiny hardware "power manager" brain for a chip. It watches how busy the chip is, feels if the chip is getting hot, and decides whether to run the chip fast (use more power) or slow (save power). The brain is written in Verilog (a hardware language), we simulate it with software, and we can put it onto an FPGA (a blank, reprogrammable chip) with tools like Vivado.

Big-picture analogy
-------------------
- Think of the chip as a car.
- `activity_in` = gas pedal (how much the car is being used).
- `stall_in` = traffic jam signal (you are stuck; more gas won't help).
- The power manager (FSM) = the driver who decides if the car should go slow, normal, or full speed.
- `temp_in` = the engine temperature gauge. If it gets too hot, the driver slows the car down.
- The FPGA & bitstream = the car's brain wires and maps. "Bitstream" = the map that tells the car how to wire itself.

Files & what they do (simple)
------------------------------
- `counters.v` — a counter that watches the pedal and traffic for a fixed window (100 cycles). It counts how many cycles the pedal was down (`activity_count`) and how many cycles there was a stall (`stall_count`). It bangs a bell (`window_done`) at the end of every window.

- `power_fsm.v` — the actual power manager brain (FSM). Every time the bell (`window_done`) rings it looks at the counts and temperature and decides: SLEEP (off), LOW_POWER, ACTIVE, or TURBO (full speed). It also includes:
  - Thermal override: if too hot, force low power.
  - Hysteresis (dwell): don't flip state on a single tiny blip (optional smoothing).
  - EWMA predictor: a smoothing filter that guesses if the next window will be busy so we can pre-scale up.
  - Workload classifier: says if the work is CPU-like or memory-bound.

- `reg_interface.v` — the front door. It latches inputs so outputs are stable, stores the thermal threshold (a register you can set), and produces `thermal_alarm`. It also sets `clk_en` (which is like turning the engine on/off) depending on the requested power state.

- `power_arbiter.v` — optional top-level boss when you have two subsystems (A and B). If both ask for max power but the whole chip has only so much budget, the arbiter decides who gets how much.

- `tb_*.v` files — these are testbenches (fake worlds) that drive the modules to verify they work. They run in a simulator, not on real hardware.

- `tools/generate_epv.py` — a helper Python script that reads the simulator waveform (`dump.vcd`) and generates pretty PNG graphs so you can see what happened.

How the pieces talk to each other (flow)
---------------------------------------
1. The testbench or the real world provides `activity_in`, `stall_in`, and `temp_in`.
2. `counters.v` watches these per cycle, builds `activity_count` and `stall_count` for a 100-cycle window, and pulses `window_done` once per window.
3. `power_fsm.v` waits for `window_done`. When it sees it, it reads the counts and `thermal_alarm` and updates `power_state_out`.
4. `reg_interface.v` latches `power_state_out` into a stable `power_state_out` that other parts of the chip see; it also produces `clk_en` to gate clocks and `thermal_alarm` so the FSM can observe heat.
5. If multiple subsystems are present, `power_arbiter.v` can take the FSM requests and map them to granted states respecting global budget.

Where the "power management logic" actually happens
--------------------------------------------------
- The decision logic lives in `power_fsm.v` — that file contains the rules like:
  - If temp alarm, go down to LOW_POWER.
  - If activity high and not stalled, step up one state.
  - If activity low, step down one state.
  - Optionally, require N consecutive windows (dwell) before changing state so you don't oscillate.
- `reg_interface.v` supports thermal threshold config and generates `thermal_alarm` — so thermal logic is split: reg_interface senses and flags alarm, FSM acts on it.

Simulation: how we test the design on a computer
------------------------------------------------
- We use a simulator (Icarus Verilog in this repo) to run the `tb_*.v` files.
- Steps (copy/paste into terminal):

```bash
# Run counters test
iverilog -g2012 -o tb_counters.vvp tb_counters.v counters.v
vvp tb_counters.vvp

# Run reg_interface test
iverilog -g2012 -o tb_reg_interface.vvp reg_interface.v counters.v tb_reg_interface.v
vvp tb_reg_interface.vvp

# Run FSM test
iverilog -g2012 -o tb_power_fsm.vvp power_fsm.v reg_interface.v counters.v tb_power_fsm.v
vvp tb_power_fsm.vvp
```

- Each test writes `dump.vcd`. Open it with GTKWave to see signals, or run the included Python script to make PNG graphs.

What is Vivado, FPGA, and bitstreams? (very simple)
---------------------------------------------------
- FPGA: a field-programmable gate array — a chip you can rewire again and again. It's like a LEGO board of tiny logic blocks.
- Vivado: Xilinx's tool that turns Verilog (our code) into a real wiring map for an FPGA. It "synthesizes" and "implements" the design and then makes a bitstream.
- Bitstream: a file that tells the FPGA exactly how to wire its little blocks. Loading a bitstream programs the FPGA.
- LEDs on boards: simple lights connected to FPGA pins. We can drive them from outputs to show states (like SLEEP/ACTIVE/TURBO). They are great for quick debugging.

How Verilog → FPGA works (simple steps)
---------------------------------------
1. Write Verilog (that's what we did: `*.v`).
2. Synthesize: translate Verilog into FPGA building blocks (LUTs, flip-flops, BRAM).
3. Implement: place & route — choose where on the FPGA each block lives and wire them.
4. Generate bitstream: pack the final wiring into a file (bitstream).
5. Program FPGA: load the bitstream onto the board (Vivado Hardware Manager or `vivado -mode batch`).

Important FPGA pieces (tiny definitions)
----------------------------------------
- LUTs (Lookup Tables): tiny decision boxes that can implement boolean logic.
- Flip-flops / registers: hold a 0 or 1 for one clock cycle.
- BRAM: bigger on-chip memory blocks.
- I/O pins: the pins that connect to LEDs, switches, connectors.
- PLL/clocking: special blocks that make/adjust clocks.

How to test on an actual FPGA board (end-to-end)
------------------------------------------------
1. Create a top-level Verilog wrapper that maps the signals you want to real pins (LEDs, switches, buttons) — this uses a constraints file (.xdc) that maps logical names to physical FPGA pins.
2. Use Vivado to synthesize, implement, and generate a bitstream. Example (simplified):

```tcl
# run inside Vivado TCL or a text script
create_project pmu_proj ./pmu -part <your-part-name>
add_files {power_fsm.v reg_interface.v counters.v top_wrapper.v}
read_xdc top_constraints.xdc
synth_design -top top_wrapper
opt_design
place_design
route_design
write_bitstream -force pmu.bit
```

3. Program the board with `pmu.bit` (Vivado Hardware Manager or `vivado -mode batch -source program.tcl`).
4. Use switches/buttons on the board (or external wiring) to provide `activity_in` / `stall_in` or wire these to test signals.
5. Watch LEDs for `power_state_out` or other debug signals. If you have a serial/UART, you can print debug messages or use an oscilloscope/logic analyzer on pins.

Notes about board-specific details
---------------------------------
- Every FPGA board is different. The exact pin numbers for LEDs, switches, and clocks are in the board's documentation. You must edit `top_constraints.xdc` to match your board.
- If you don't have physical switches for `activity_in`, you can either drive them from another board or use a small test circuit (or inside the FPGA use a simple pattern generator block in `top_wrapper.v`).

What are bitsreams and why do they matter?
------------------------------------------
- Bitstream = the final "wiring kit" that tells the FPGA exactly how to behave.
- Without the bitstream, the FPGA is just blank hardware. With the bitstream, it becomes your design.
- You can reprogram the FPGA many times with different bitstreams.

LEDs: the practical visible outputs
----------------------------------
- Map `power_state_out[1:0]` to two LEDs: 00=SLEEP (both off), 01=LOW_POWER, 10=ACTIVE, 11=TURBO. That gives an easy visual.
- Add extra LEDs for `thermal_alarm`, `clk_en`, or `workload_class` if you want more debug view.

How do we know it works? (end-to-end verification)
-------------------------------------------------
- Software side: run the testbenches (`tb_*.v`) and check console output; open `dump.vcd` in GTKWave or inspect PNG graphs produced by `tools/generate_epv.py`.
- Hardware side (FPGA): program the board, toggle inputs (switches or external signals), and watch LEDs change state as expected.
- Bring-up checklist:
  - Ensure clock constraints and I/O pin mappings are correct in `.xdc`.
  - Start with slow test patterns so you can observe changes by eye.
  - Verify `thermal_thresh_in` register is set to a reasonable value so you can test thermal override.

Where to look in code for the "brain"
-------------------------------------
- Decision making and policy rules: `power_fsm.v`.
- Telemetry gathering (counts + window): `counters.v`.
- Register interface, thermal alarm, `clk_en`: `reg_interface.v`.
- Multi-module policy (budget): `power_arbiter.v`.

Helpful commands (recap)
------------------------
Simulation (Icarus):

```bash
iverilog -g2012 -o tb_power_fsm.vvp power_fsm.v reg_interface.v counters.v tb_power_fsm.v
vvp tb_power_fsm.vvp
gtkwave dump.vcd   # view waveforms
python3 tools/generate_epv.py  # create PNG graphs
```

Vivado (very short summary, board-specific):

```bash
# interactive: open Vivado GUI and import project
# batch (example script):
vivado -mode batch -source build_and_program.tcl
```

Final simple summary
--------------------
- This repo is a small, testbench-driven demo of a hardware power manager.
- The counting -> decide -> apply loop is the core: `counters.v` → `power_fsm.v` → `reg_interface.v`.
- Test first in simulator (easy), then synthesize and program FPGA (requires a board and Vivado). LEDs are your friends for fast, physical feedback.

If you want, I can:
- Add a `top_wrapper.v` and a sample `.xdc` for a specific FPGA board (you tell me the board model).
- Make the `EXPLAINER.md` even simpler or convert it into a slide-style README.
- Add a demo bitstream or Vivado TCL script template for a particular board.


---
File: EXPLAINER.md created in repo root.
