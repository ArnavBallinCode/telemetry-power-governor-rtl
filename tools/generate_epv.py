#!/usr/bin/env python3
"""
Simple VCD parser and plotter for EPV (power-state / activity / arbiter) graphs.
Generates PNGs in docs/graphs from dump.vcd produced by the testbenches.
"""
import os
import re
from collections import defaultdict
import math

import matplotlib.pyplot as plt

VCD_PATH = 'dump.vcd'
OUT_DIR = 'docs/graphs'

if not os.path.exists(VCD_PATH):
    raise SystemExit(f"VCD file not found: {VCD_PATH}")

os.makedirs(OUT_DIR, exist_ok=True)

# Parse header to map id -> full name
id_to_name = {}
scope_stack = []
with open(VCD_PATH, 'r') as f:
    in_defs = True
    for line in f:
        line = line.strip()
        if line.startswith('$scope'):
            parts = line.split()
            # $scope module NAME $end
            if len(parts) >= 3:
                scope_stack.append(parts[2])
        elif line.startswith('$upscope'):
            if scope_stack:
                scope_stack.pop()
        elif line.startswith('$var'):
            parts = line.split()
            # $var <type> <size> <id> <name...> $end
            if '$end' in parts:
                idx = parts.index('$end')
                id = parts[3]
                name_tokens = parts[4:idx]
                # join and strip array suffix
                name_str = ' '.join(name_tokens)
                base_name = re.sub(r"\s*\[.*\]$", '', name_str)
                full_name = '.'.join(['tb_power_arbiter_direct'] + scope_stack + [base_name])
                id_to_name[id] = full_name
        elif line.startswith('$enddefinitions'):
            break

# Now parse value changes
signals = defaultdict(list)  # full_name -> list of (time_ns, value)
curr_time_ps = 0
with open(VCD_PATH, 'r') as f:
    in_values = False
    for line in f:
        line = line.strip()
        if line.startswith('$enddefinitions'):
            in_values = True
            continue
        if not in_values:
            continue
        if not line:
            continue
        if line.startswith('#'):
            try:
                curr_time_ps = int(line[1:])
            except Exception:
                curr_time_ps = curr_time_ps
            continue
        # match vector: b101010 id
        m = re.match(r'^b([01xz]+)\s+(.+)$', line)
        if m:
            bits = m.group(1)
            vid = m.group(2).strip()
            if vid in id_to_name:
                name = id_to_name[vid]
                if 'x' in bits or 'z' in bits:
                    val = None
                else:
                    val = int(bits, 2)
                signals[name].append((curr_time_ps/1000.0, val))
            continue
        # single-bit: 0id or 1id or xid
        m2 = re.match(r'^([01xz])(.+)$', line)
        if m2:
            bit = m2.group(1)
            vid = m2.group(2).strip()
            if vid in id_to_name:
                name = id_to_name[vid]
                if bit in '01':
                    val = int(bit)
                else:
                    val = None
                signals[name].append((curr_time_ps/1000.0, val))
            continue
        # ignore others

# Helper to find a signal by substring
def find_signal(sub):
    for k in id_to_name.values():
        if sub in k and k in signals:
            return k
    return None

# Determine global end_time (ns)
end_time = 0.0
for vals in signals.values():
    if vals:
        end_time = max(end_time, max(t for t, v in vals))
if end_time == 0.0:
    end_time = 1.0

# Utility to build step series
def build_series(entries):
    if not entries:
        return [], []
    entries = sorted(entries, key=lambda x: x[0])
    if entries[0][0] > 0.0:
        entries.insert(0, (0.0, entries[0][1]))
    times = [t for (t, v) in entries]
    vals = [v for (t, v) in entries]
    # append end_time to keep value until end
    times.append(end_time)
    vals.append(vals[-1])
    return times, vals

# Select signals of interest
s_power_A = find_signal('FSM_A.power_state_out')
s_power_B = find_signal('FSM_B.power_state_out')
s_ewma_A = find_signal('FSM_A.ewma_out')
s_ewma_B = find_signal('FSM_B.ewma_out')
s_act_a = find_signal('activity_count_a')
s_act_b = find_signal('activity_count_b')
s_grant_a = find_signal('ARB.grant_a') or find_signal('.grant_a')
s_grant_b = find_signal('ARB.grant_b') or find_signal('.grant_b')

# Plot 1: Power states
plt.figure(figsize=(10,3))
plotted = False
if s_power_A and s_power_A in signals:
    tA, vA = build_series(signals[s_power_A])
    plt.step(tA, vA, where='post', label='FSM_A state')
    plotted = True
if s_power_B and s_power_B in signals:
    tB, vB = build_series(signals[s_power_B])
    plt.step(tB, vB, where='post', label='FSM_B state')
    plotted = True
if plotted:
    plt.yticks([0,1,2,3], ['SLEEP','LOW_POWER','ACTIVE','TURBO'])
    plt.xlabel('Time (ns)')
    plt.title('Power State Transitions')
    plt.legend()
    plt.grid(True)
    out1 = os.path.join(OUT_DIR, 'power_states.png')
    plt.tight_layout()
    plt.savefig(out1)
    print('Wrote', out1)
    plt.close()

# Plot 2: Activity counts and EWMA (A and B)
plt.figure(figsize=(10,6))
rows = 2
if s_act_a and s_ewma_A and s_act_a in signals and s_ewma_A in signals:
    t_act, v_act = build_series(signals[s_act_a])
    t_ewma, v_ewma = build_series(signals[s_ewma_A])
    ax1 = plt.subplot(2,1,1)
    plt.step(t_act, v_act, where='post', label='activity_count_a')
    plt.step(t_ewma, v_ewma, where='post', label='ewma_a')
    plt.title('Subsystem A: activity & EWMA')
    plt.ylabel('Counts')
    plt.legend()
    plt.grid(True)
else:
    ax1 = None

if s_act_b and s_ewma_B and s_act_b in signals and s_ewma_B in signals:
    t_actb, v_actb = build_series(signals[s_act_b])
    t_ewmab, v_ewmab = build_series(signals[s_ewma_B])
    ax2 = plt.subplot(2,1,2)
    plt.step(t_actb, v_actb, where='post', label='activity_count_b')
    plt.step(t_ewmab, v_ewmab, where='post', label='ewma_b')
    plt.title('Subsystem B: activity & EWMA')
    plt.xlabel('Time (ns)')
    plt.ylabel('Counts')
    plt.legend()
    plt.grid(True)
else:
    ax2 = None

if ax1 or ax2:
    out2 = os.path.join(OUT_DIR, 'activity_ewma.png')
    plt.tight_layout()
    plt.savefig(out2)
    print('Wrote', out2)
    plt.close()

# Plot 3: Arbiter grants
plt.figure(figsize=(10,3))
plotted = False
if s_grant_a and s_grant_a in signals:
    tg_a, vg_a = build_series(signals[s_grant_a])
    plt.step(tg_a, vg_a, where='post', label='grant_a')
    plotted = True
if s_grant_b and s_grant_b in signals:
    tg_b, vg_b = build_series(signals[s_grant_b])
    plt.step(tg_b, vg_b, where='post', label='grant_b')
    plotted = True
if plotted:
    plt.yticks([0,1,2,3], ['SLEEP','LOW_POWER','ACTIVE','TURBO'])
    plt.xlabel('Time (ns)')
    plt.title('Arbiter Grants')
    plt.legend()
    plt.grid(True)
    out3 = os.path.join(OUT_DIR, 'arbiter_grants.png')
    plt.tight_layout()
    plt.savefig(out3)
    print('Wrote', out3)
    plt.close()

print('Done generating graphs.')
