#!/usr/bin/env python3
"""
Toggle FLG_SHOW_SMILEY on TH05/THB2-family devices over BLE.

Usage:
    python3 th05_smiley.py <MAC> <on|off>
"""

import argparse
import asyncio
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.device import BLEDevice


CMD_CHAR_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
CMD_ID_CFG = 0x55
CMD_ID_CFG_DEF = 0x56
FLG_SHOW_SMILEY = 0x00000004


def _normalize_mac(mac: str) -> str:
    return mac.strip().upper().replace("-", ":")


async def _find_device(mac: str, scan_timeout: float) -> BLEDevice:
    device = await BleakScanner.find_device_by_address(mac, timeout=scan_timeout)
    if device is None:
        raise RuntimeError(
            f"Device {mac} not found after {scan_timeout:.1f}s scan. "
            "Make sure it is advertising and close apps that may hold the BLE connection."
        )
    return device


async def set_smiley(mac: str, state: str, scan_timeout: float) -> int:
    mac = _normalize_mac(mac)
    queue: asyncio.Queue[bytes] = asyncio.Queue()

    def on_notify(_sender: int, data: bytearray) -> None:
        queue.put_nowait(bytes(data))

    device = await _find_device(mac, scan_timeout)

    async with BleakClient(device, timeout=20.0) as client:
        await client.start_notify(CMD_CHAR_UUID, on_notify)

        # Read current config
        await client.write_gatt_char(CMD_CHAR_UUID, bytes([CMD_ID_CFG]), response=True)

        cfg: Optional[bytes] = None
        for _ in range(20):
            packet = await asyncio.wait_for(queue.get(), timeout=5.0)
            if len(packet) >= 13 and packet[0] in (CMD_ID_CFG, CMD_ID_CFG_DEF):
                cfg = packet
                break

        if cfg is None:
            raise RuntimeError("No config response (expected packet ID 0x55 or 0x56).")

        flags = int.from_bytes(cfg[1:5], "little")
        if state == "on":
            flags |= FLG_SHOW_SMILEY
        else:
            flags &= ~FLG_SHOW_SMILEY

        # Partial set is supported by firmware: [0x55][flags_le_u32]
        payload = bytes([CMD_ID_CFG]) + flags.to_bytes(4, "little")
        await client.write_gatt_char(CMD_CHAR_UUID, payload, response=True)

        await client.stop_notify(CMD_CHAR_UUID)
        return flags


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Turn TH05 smiley flag on/off via BLE command channel."
    )
    parser.add_argument("mac", help="BLE MAC address, e.g. C4:7C:8D:12:34:56")
    parser.add_argument("state", choices=("on", "off"), help="Target smiley state")
    parser.add_argument(
        "--scan-timeout",
        type=float,
        default=45.0,
        help="Seconds to scan for the device before connect (default: 45)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    final_flags = asyncio.run(set_smiley(args.mac, args.state, args.scan_timeout))
    print(f"{args.mac}: smiley -> {args.state}, flags=0x{final_flags:08x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
