#!/usr/bin/env python3
"""
Get/set thermostat setpoint over TH05/THB2 BLE command channel.

Protocol:
  Command 0x57
  - GET: [0x57]
  - SET: [0x57, setpoint_c_x2]

Response:
  [0x57, setpoint_c_x2, version_lo, version_hi, min_c_x2, max_c_x2, unit_flag]
"""

import argparse
import asyncio
from typing import Optional

from bleak import BleakClient, BleakScanner


CMD_CHAR_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
CMD_ID_SETPOINT = 0x57


def _normalize_mac(mac: str) -> str:
    return mac.strip().upper().replace("-", ":")


def _parse_setpoint_response(packet: bytes) -> dict:
    if len(packet) < 7 or packet[0] != CMD_ID_SETPOINT:
        raise RuntimeError(f"Unexpected response: {packet.hex()}")

    c_x2 = packet[1]
    version = packet[2] | (packet[3] << 8)
    min_x2 = packet[4]
    max_x2 = packet[5]
    unit_flag = packet[6]
    celsius = c_x2 / 2.0
    fahrenheit = celsius * 9.0 / 5.0 + 32.0
    return {
        "c_x2": c_x2,
        "celsius": celsius,
        "fahrenheit": fahrenheit,
        "version": version,
        "min_c": min_x2 / 2.0,
        "max_c": max_x2 / 2.0,
        "display_unit": "F" if unit_flag else "C",
    }


async def _read_setpoint(client: BleakClient, queue: asyncio.Queue[bytes]) -> dict:
    await client.write_gatt_char(CMD_CHAR_UUID, bytes([CMD_ID_SETPOINT]), response=True)
    for _ in range(20):
        packet = await asyncio.wait_for(queue.get(), timeout=5.0)
        if packet and packet[0] == CMD_ID_SETPOINT:
            return _parse_setpoint_response(packet)
    raise RuntimeError("No setpoint response received.")


def _to_c_x2(value_c: float) -> int:
    # quantize to 0.5 C steps
    return int(round(value_c * 2.0))


async def _run_once(mac: str, action: str, value_c: Optional[float], settle_ms: int) -> dict:
    mac = _normalize_mac(mac)
    queue: asyncio.Queue[bytes] = asyncio.Queue()
    state: Optional[dict] = None

    def on_notify(_sender: int, data: bytearray) -> None:
        queue.put_nowait(bytes(data))

    # On Windows, direct connect by address is usually more stable than long pre-scan.
    client = BleakClient(mac, timeout=20.0)
    try:
        await asyncio.wait_for(client.connect(), timeout=25.0)
        await client.start_notify(CMD_CHAR_UUID, on_notify)

        if action == "get":
            state = await _read_setpoint(client, queue)
        else:
            assert value_c is not None
            c_x2 = _to_c_x2(value_c)
            payload = bytes([CMD_ID_SETPOINT, c_x2 & 0xFF])
            await client.write_gatt_char(CMD_CHAR_UUID, payload, response=True)
            state = await _read_setpoint(client, queue)
    finally:
        try:
            await client.stop_notify(CMD_CHAR_UUID)
        except Exception:
            pass
        if client.is_connected:
            try:
                await asyncio.wait_for(client.disconnect(), timeout=10.0)
            except Exception:
                pass
        # Give host stack a moment to propagate disconnect.
        await asyncio.sleep(settle_ms / 1000.0)

    if state is None:
        raise RuntimeError("No setpoint state received.")
    return state


async def run(
    mac: str,
    scan_timeout: float,
    action: str,
    value_c: Optional[float],
    retries: int,
    settle_ms: int,
) -> None:
    mac = _normalize_mac(mac)
    last_error: Optional[Exception] = None

    # Prime the Windows BLE cache before the first connect attempt.
    try:
        await BleakScanner.discover(timeout=scan_timeout)
    except Exception:
        pass

    for attempt in range(1, retries + 1):
        try:
            state = await _run_once(mac, action, value_c, settle_ms)
            print(
                f"{mac}: setpoint={state['celsius']:.1f}C ({state['fahrenheit']:.1f}F), "
                f"version={state['version']}, range={state['min_c']:.1f}..{state['max_c']:.1f}C, "
                f"display_unit={state['display_unit']}"
            )
            return
        except Exception as exc:
            last_error = exc
            # Warm up device cache for next attempt.
            try:
                await BleakScanner.discover(timeout=scan_timeout)
            except Exception:
                pass
            if attempt < retries:
                await asyncio.sleep(1.0)

    msg = f"Failed after {retries} attempts: {last_error}"
    if last_error is not None and "not found" in str(last_error).lower():
        msg += (
            "\nThe device is not advertising. On Windows this often means the previous BLE session "
            "is still stuck open.\nRecovery: turn Bluetooth off/on on the laptop, or power-cycle the "
            "device, then retry once the BLE icon disappears."
        )
    raise RuntimeError(msg)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get/set TH05 thermostat setpoint via BLE.")
    parser.add_argument("mac", help="BLE MAC address, e.g. 40:B7:FC:19:2F:78")
    parser.add_argument("action", choices=("get", "set"))
    parser.add_argument("value", nargs="?", type=float, help="Setpoint in Celsius, step 0.5")
    parser.add_argument("--scan-timeout", type=float, default=8.0, help="Fallback scan timeout (seconds)")
    parser.add_argument("--retries", type=int, default=3, help="Connection retries (default: 3)")
    parser.add_argument("--settle-ms", type=int, default=1200, help="Post-disconnect settle time in ms")
    args = parser.parse_args()
    if args.action == "set" and args.value is None:
        parser.error("value is required for action 'set'")
    if args.retries < 1:
        parser.error("--retries must be >= 1")
    if args.settle_ms < 0:
        parser.error("--settle-ms must be >= 0")
    return args


def main() -> int:
    args = parse_args()
    asyncio.run(
        run(
            args.mac,
            args.scan_timeout,
            args.action,
            args.value,
            args.retries,
            args.settle_ms,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
