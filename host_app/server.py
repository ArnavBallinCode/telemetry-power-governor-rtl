import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import serial
from serial.tools import list_ports
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


UART_BAUD = int(os.getenv("PWRGOV_BAUD", "115200"))
UART_PORT = os.getenv("PWRGOV_PORT", "").strip()
FRAME_LEN = 16
FRAME_HEADER = bytes([0xAA, 0x55])


@dataclass
class TelemetryState:
    ts: float = 0.0
    connected: bool = False
    serial_port: str = ""
    frame_counter: int = 0
    host_mode: int = 0
    alarm_a: int = 0
    alarm_b: int = 0
    clk_en_a: int = 0
    clk_en_b: int = 0
    grant_a: int = 0
    grant_b: int = 0
    current_budget: int = 0
    budget_headroom: int = 0
    efficiency: int = 0
    temp_a: int = 0
    temp_b: int = 0
    act_a: int = 0
    stall_a: int = 0
    act_b: int = 0
    stall_b: int = 0
    req_a: int = 0
    req_b: int = 0
    phase: int = 0


class ControlPayload(BaseModel):
    mode: Optional[str] = Field(default=None, description="internal|host")
    host_use_ext_budget: Optional[bool] = None
    budget: Optional[int] = Field(default=None, ge=0, le=7)
    req_a: Optional[int] = Field(default=None, ge=0, le=3)
    req_b: Optional[int] = Field(default=None, ge=0, le=3)
    act_a: Optional[bool] = None
    stall_a: Optional[bool] = None
    act_b: Optional[bool] = None
    stall_b: Optional[bool] = None
    temp_a: Optional[int] = Field(default=None, ge=0, le=127)
    temp_b: Optional[int] = Field(default=None, ge=0, le=127)


class ScenarioRunPayload(BaseModel):
    name: str
    sample_ms: int = Field(default=200, ge=80, le=1000)


class SerialBridge:
    def __init__(self, port: str, baud: int):
        self.port = port
        self.baud = baud
        self._manual_port = bool(port and port.lower() != "auto")
        self._ser: Optional[serial.Serial] = None
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.state = TelemetryState()
        self._running = False

    @staticmethod
    def _frame_is_valid(frame: bytes) -> bool:
        if len(frame) != FRAME_LEN:
            return False
        if frame[0:2] != FRAME_HEADER or frame[15] != 0x0D:
            return False
        checksum = 0
        for b in frame[2:14]:
            checksum ^= b
        return checksum == frame[14]

    @classmethod
    def _contains_valid_frame(cls, data: bytes) -> bool:
        if len(data) < FRAME_LEN:
            return False
        idx = 0
        max_idx = len(data) - FRAME_LEN
        while idx <= max_idx:
            hdr = data.find(FRAME_HEADER, idx)
            if hdr < 0 or hdr > max_idx:
                return False
            frame = data[hdr:hdr + FRAME_LEN]
            if cls._frame_is_valid(frame):
                return True
            idx = hdr + 1
        return False

    def _detect_ports(self) -> List[str]:
        if self._manual_port:
            return [self.port]
        return [p.device for p in list_ports.comports()]

    def _open_candidate(self, port_name: str, require_frame: bool) -> Optional[serial.Serial]:
        ser = serial.Serial(port_name, self.baud, timeout=0.10)
        if not require_frame:
            return ser

        probe = bytearray()
        deadline = time.time() + 1.2
        while time.time() < deadline:
            chunk = ser.read(64)
            if chunk:
                probe.extend(chunk)
                if self._contains_valid_frame(probe):
                    self._buf.extend(probe)
                    return ser
        ser.close()
        return None

    def start(self) -> None:
        self._running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self) -> None:
        self._running = False
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()

    def _open(self) -> None:
        with self._lock:
            if self._ser and self._ser.is_open:
                return

            candidates = self._detect_ports()
            if not candidates:
                raise RuntimeError("No serial ports available")

            require_frame = not self._manual_port
            for candidate in candidates:
                try:
                    ser = self._open_candidate(candidate, require_frame=require_frame)
                    if ser is None:
                        continue
                    self._ser = ser
                    self.port = candidate
                    self.state.serial_port = candidate
                    break
                except Exception:
                    continue

            if not self._ser or not self._ser.is_open:
                if self._manual_port:
                    raise RuntimeError(f"Unable to open configured serial port: {self.port}")
                raise RuntimeError("No telemetry stream found on available serial ports")

            self.state.connected = True

    def _run(self) -> None:
        while self._running:
            try:
                self._open()
                data = self._ser.read(256) if self._ser else b""
                if data:
                    self._buf.extend(data)
                    self._consume_frames()
            except Exception:
                with self._lock:
                    if self._ser and self._ser.is_open:
                        self._ser.close()
                    self._ser = None
                self.state.connected = False
                time.sleep(1.0)

    def _consume_frames(self) -> None:
        while True:
            idx = self._buf.find(FRAME_HEADER)
            if idx < 0:
                if len(self._buf) > 512:
                    self._buf.clear()
                return
            if idx > 0:
                del self._buf[:idx]
            if len(self._buf) < FRAME_LEN:
                return
            frame = bytes(self._buf[:FRAME_LEN])
            if frame[15] != 0x0D:
                del self._buf[0]
                continue
            if not self._frame_is_valid(frame):
                del self._buf[0]
                continue
            self._decode(frame)
            del self._buf[:FRAME_LEN]

    def _decode(self, frame: bytes) -> None:
        flags = frame[4]
        grants = frame[5]
        budget = frame[6]
        eff = frame[7] | ((frame[8] & 0x03) << 8)
        io_flags = frame[11]
        req_pack = frame[12]

        self.state = TelemetryState(
            ts=time.time(),
            connected=True,
            serial_port=self.port,
            frame_counter=(frame[3] << 8) | frame[2],
            host_mode=(flags >> 0) & 0x01,
            alarm_a=(flags >> 1) & 0x01,
            alarm_b=(flags >> 2) & 0x01,
            clk_en_a=(flags >> 3) & 0x01,
            clk_en_b=(flags >> 4) & 0x01,
            grant_a=(grants >> 0) & 0x03,
            grant_b=(grants >> 2) & 0x03,
            current_budget=(budget >> 0) & 0x07,
            budget_headroom=(budget >> 3) & 0x07,
            efficiency=eff,
            temp_a=frame[9],
            temp_b=frame[10],
            stall_a=(io_flags >> 0) & 0x01,
            act_a=(io_flags >> 1) & 0x01,
            stall_b=(io_flags >> 2) & 0x01,
            act_b=(io_flags >> 3) & 0x01,
            req_a=(req_pack >> 0) & 0x03,
            req_b=(req_pack >> 2) & 0x03,
            phase=frame[13] & 0x07,
        )

    def write_commands(self, commands: List[int]) -> None:
        with self._lock:
            if not self._ser or not self._ser.is_open:
                raise RuntimeError("Serial not connected")
            self._ser.write(bytes(commands))


def payload_to_commands(p: ControlPayload) -> List[int]:
    cmds: List[int] = []

    if p.mode is not None:
        if p.mode not in {"internal", "host"}:
            raise HTTPException(status_code=400, detail="mode must be 'internal' or 'host'")
        cmds.append(0xA1 if p.mode == "host" else 0xA0)

    if p.host_use_ext_budget is not None:
        cmds.append(0xF1 if p.host_use_ext_budget else 0xF0)

    if p.budget is not None:
        cmds.append(0xB0 | (p.budget & 0x07))

    if p.req_a is not None:
        cmds.append(0xC0 | (p.req_a & 0x03))

    if p.req_b is not None:
        cmds.append(0xC4 | (p.req_b & 0x03))

    if p.act_a is not None:
        cmds.append(0xD1 if p.act_a else 0xD0)

    if p.stall_a is not None:
        cmds.append(0xD3 if p.stall_a else 0xD2)

    if p.act_b is not None:
        cmds.append(0xD5 if p.act_b else 0xD4)

    if p.stall_b is not None:
        cmds.append(0xD7 if p.stall_b else 0xD6)

    if p.temp_a is not None:
        cmds.extend([0xE0, p.temp_a & 0x7F])

    if p.temp_b is not None:
        cmds.extend([0xE1, p.temp_b & 0x7F])

    return cmds


def payload_mismatches(payload: ControlPayload, state: TelemetryState) -> Dict[str, Dict[str, Any]]:
    mismatches: Dict[str, Dict[str, Any]] = {}

    if payload.mode is not None:
        expected = 1 if payload.mode == "host" else 0
        if state.host_mode != expected:
            mismatches["mode"] = {"expected": payload.mode, "actual": "host" if state.host_mode else "internal"}

    compare_map = {
        "budget": "current_budget",
        "req_a": "req_a",
        "req_b": "req_b",
        "temp_a": "temp_a",
        "temp_b": "temp_b",
        "act_a": "act_a",
        "stall_a": "stall_a",
        "act_b": "act_b",
        "stall_b": "stall_b",
    }

    for payload_key, state_key in compare_map.items():
        expected = getattr(payload, payload_key)
        if expected is None:
            continue

        actual = getattr(state, state_key)
        if isinstance(expected, bool):
            expected_int = 1 if expected else 0
            if int(actual) != expected_int:
                mismatches[payload_key] = {"expected": expected_int, "actual": int(actual)}
            continue

        if int(actual) != int(expected):
            mismatches[payload_key] = {"expected": int(expected), "actual": int(actual)}

    # host_use_ext_budget is commandable but not currently exposed in telemetry frame, so it is not verifiable here.
    return mismatches


def wait_for_payload_reflection(
    payload: ControlPayload,
    timeout_s: float = 1.5,
    poll_s: float = 0.05,
) -> Dict[str, Any]:
    deadline = time.time() + timeout_s
    latest = bridge.state
    latest_mismatch = payload_mismatches(payload, latest)

    while time.time() < deadline:
        latest = bridge.state
        latest_mismatch = payload_mismatches(payload, latest)
        if not latest_mismatch:
            return {
                "applied": True,
                "state": asdict(latest),
                "mismatch": {},
            }
        time.sleep(poll_s)

    return {
        "applied": False,
        "state": asdict(latest),
        "mismatch": latest_mismatch,
    }


SCENARIOS: Dict[str, Dict[str, Any]] = {
    "tb_power_fsm_workload_sweep": {
        "source_testbench": "tb_power_fsm.v",
        "description": "FSM-style sweep: high activity -> low activity -> stall.",
        "steps": [
            {
                "label": "high_activity",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 6,
                    "req_a": 3,
                    "req_b": 3,
                    "act_a": True,
                    "stall_a": False,
                    "act_b": True,
                    "stall_b": False,
                    "temp_a": 45,
                    "temp_b": 47,
                },
            },
            {
                "label": "low_activity",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 3,
                    "req_a": 1,
                    "req_b": 1,
                    "act_a": False,
                    "stall_a": False,
                    "act_b": False,
                    "stall_b": False,
                    "temp_a": 35,
                    "temp_b": 34,
                },
            },
            {
                "label": "stall_stress",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 2,
                    "req_a": 3,
                    "req_b": 3,
                    "act_a": False,
                    "stall_a": True,
                    "act_b": False,
                    "stall_b": True,
                    "temp_a": 52,
                    "temp_b": 50,
                },
            },
            {
                "label": "return_internal",
                "duration_s": 1.0,
                "payload": {
                    "mode": "internal",
                },
            },
        ],
    },
    "tb_power_arbiter_contention": {
        "source_testbench": "tb_power_arbiter.v",
        "description": "Arbiter-focused contention and budget pressure between A/B.",
        "steps": [
            {
                "label": "balanced_load",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 4,
                    "req_a": 2,
                    "req_b": 2,
                    "act_a": True,
                    "stall_a": False,
                    "act_b": True,
                    "stall_b": False,
                    "temp_a": 48,
                    "temp_b": 48,
                },
            },
            {
                "label": "a_priority",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 3,
                    "req_a": 3,
                    "req_b": 1,
                    "act_a": True,
                    "stall_a": False,
                    "act_b": True,
                    "stall_b": True,
                    "temp_a": 56,
                    "temp_b": 44,
                },
            },
            {
                "label": "b_priority",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 3,
                    "req_a": 1,
                    "req_b": 3,
                    "act_a": True,
                    "stall_a": True,
                    "act_b": True,
                    "stall_b": False,
                    "temp_a": 44,
                    "temp_b": 57,
                },
            },
            {
                "label": "return_internal",
                "duration_s": 1.0,
                "payload": {
                    "mode": "internal",
                },
            },
        ],
    },
    "tb_reg_interface_thermal_alarm": {
        "source_testbench": "tb_reg_interface.v",
        "description": "Thermal sweep to observe alarm behavior and throttling effects.",
        "steps": [
            {
                "label": "cool",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 5,
                    "req_a": 2,
                    "req_b": 2,
                    "act_a": True,
                    "stall_a": False,
                    "act_b": True,
                    "stall_b": False,
                    "temp_a": 35,
                    "temp_b": 36,
                },
            },
            {
                "label": "hot",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 5,
                    "req_a": 2,
                    "req_b": 2,
                    "act_a": True,
                    "stall_a": False,
                    "act_b": True,
                    "stall_b": False,
                    "temp_a": 95,
                    "temp_b": 92,
                },
            },
            {
                "label": "recover",
                "duration_s": 2.0,
                "payload": {
                    "mode": "host",
                    "host_use_ext_budget": True,
                    "budget": 4,
                    "req_a": 1,
                    "req_b": 1,
                    "act_a": False,
                    "stall_a": False,
                    "act_b": False,
                    "stall_b": False,
                    "temp_a": 42,
                    "temp_b": 40,
                },
            },
            {
                "label": "return_internal",
                "duration_s": 1.0,
                "payload": {
                    "mode": "internal",
                },
            },
        ],
    },
}

TESTBENCH_NOTES: List[Dict[str, str]] = [
    {
        "name": "tb_counters.v",
        "focus": "Counter windowing",
        "summary": "Checks active/stall counters and window_done behavior over fixed intervals.",
    },
    {
        "name": "tb_power_fsm.v",
        "focus": "FSM state policy",
        "summary": "Exercises state transitions for changing workload and thermal conditions.",
    },
    {
        "name": "tb_testbench_power_fsm.v",
        "focus": "Extended FSM sweep",
        "summary": "Longer scripted FSM stress sequence used for broader transition coverage.",
    },
    {
        "name": "tb_power_arbiter.v",
        "focus": "Arbiter fairness",
        "summary": "Validates A/B request contention handling under shared budget pressure.",
    },
    {
        "name": "tb_power_arbiter_direct.v",
        "focus": "Direct arbiter controls",
        "summary": "Direct stimulus for grant edge cases and deterministic arbitration checks.",
    },
    {
        "name": "tb_reg_interface.v",
        "focus": "Register and command mapping",
        "summary": "Verifies command/register path updates internal controls correctly.",
    },
    {
        "name": "tb_level2.v",
        "focus": "Integrated level-2 flow",
        "summary": "Top-level multi-module simulation with workload and feedback interaction.",
    },
]

scenario_stop_event = threading.Event()
scenario_run_lock = threading.Lock()


def apply_control_payload(payload: ControlPayload, settle_s: float = 0.08) -> Dict[str, Any]:
    commands = payload_to_commands(payload)
    if not commands:
        return {
            "ok": True,
            "sent": 0,
            "commands": [],
            "applied": True,
            "attempts": 0,
            "mismatch": {},
            "state": asdict(bridge.state),
        }

    max_attempts = 2
    latest_result: Dict[str, Any] = {
        "applied": False,
        "state": asdict(bridge.state),
        "mismatch": {},
    }

    for attempt in range(1, max_attempts + 1):
        bridge.write_commands(commands)
        if settle_s > 0:
            time.sleep(settle_s)
        latest_result = wait_for_payload_reflection(payload)
        if latest_result["applied"]:
            return {
                "ok": True,
                "sent": len(commands),
                "commands": [hex(c) for c in commands],
                "applied": True,
                "attempts": attempt,
                "mismatch": {},
                "state": latest_result["state"],
            }
        if attempt < max_attempts:
            time.sleep(0.04)

    return {
        "ok": True,
        "sent": len(commands),
        "commands": [hex(c) for c in commands],
        "applied": False,
        "attempts": max_attempts,
        "mismatch": latest_result.get("mismatch", {}),
        "state": latest_result.get("state", asdict(bridge.state)),
    }


def run_scenario(name: str, sample_ms: int) -> Dict[str, Any]:
    scenario = SCENARIOS.get(name)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {name}")

    if not scenario_run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another scenario is already running")

    timeline: List[Dict[str, Any]] = []
    sample_s = sample_ms / 1000.0
    start_t = time.time()

    scenario_stop_event.clear()
    stop_reason = "completed"
    try:
        for step in scenario["steps"]:
            if scenario_stop_event.is_set():
                stop_reason = "stopped"
                break

            payload = ControlPayload(**step["payload"])
            apply_control_payload(payload, settle_s=0.10)

            step_end = time.time() + float(step["duration_s"])
            while time.time() < step_end:
                if scenario_stop_event.is_set():
                    stop_reason = "stopped"
                    break
                snap = asdict(bridge.state)
                snap["t_ms"] = int((time.time() - start_t) * 1000)
                snap["step"] = step["label"]
                timeline.append(snap)
                time.sleep(sample_s)

        # Always hand control back to internal workload_sim when scenario ends/stops.
        try:
            apply_control_payload(ControlPayload(mode="internal"), settle_s=0.06)
        except RuntimeError:
            pass

        return {
            "ok": True,
            "name": name,
            "description": scenario["description"],
            "status": stop_reason,
            "sample_ms": sample_ms,
            "points": len(timeline),
            "timeline": timeline,
            "final_state": asdict(bridge.state),
        }
    finally:
        scenario_stop_event.clear()
        scenario_run_lock.release()


def stop_scenario() -> Dict[str, Any]:
    scenario_stop_event.set()
    try:
        apply_control_payload(ControlPayload(mode="internal"), settle_s=0.04)
    except RuntimeError:
        pass
    return {
        "ok": True,
        "message": "Stop requested. Returning control to internal workload_sim.",
        "state": asdict(bridge.state),
    }


app = FastAPI(title="PwrGov Laptop Bridge", version="0.1.0")
bridge = SerialBridge(UART_PORT, UART_BAUD)
websockets: List[WebSocket] = []


@app.on_event("startup")
async def startup() -> None:
    bridge.start()
    asyncio.create_task(broadcast_loop())


@app.on_event("shutdown")
def shutdown() -> None:
    bridge.stop()


@app.get("/api/state")
def get_state() -> Dict:
    return asdict(bridge.state)


@app.post("/api/control")
def post_control(payload: ControlPayload) -> Dict:
    try:
        return apply_control_payload(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/scenarios")
def get_scenarios() -> Dict[str, Any]:
    return {
        "scenarios": [
            {
                "name": name,
                "description": cfg["description"],
                "source_testbench": cfg.get("source_testbench", ""),
                "steps": len(cfg["steps"]),
            }
            for name, cfg in SCENARIOS.items()
        ]
    }


@app.get("/api/testbenches")
def get_testbenches() -> Dict[str, Any]:
    return {
        "testbenches": TESTBENCH_NOTES,
    }


@app.post("/api/scenarios/run")
def post_run_scenario(payload: ScenarioRunPayload) -> Dict[str, Any]:
    if not bridge.state.connected:
        raise HTTPException(status_code=503, detail="Serial not connected")
    try:
        return run_scenario(payload.name, payload.sample_ms)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/api/scenarios/stop")
def post_stop_scenario() -> Dict[str, Any]:
    return stop_scenario()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    websockets.append(ws)
    try:
        while True:
            await asyncio.sleep(60)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if ws in websockets:
            websockets.remove(ws)


async def broadcast_loop() -> None:
    while True:
        if websockets:
            msg = json.dumps(asdict(bridge.state))
            dead = []
            for ws in websockets:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                if ws in websockets:
                    websockets.remove(ws)
        await asyncio.sleep(0.2)


static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(static_dir / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=False)
