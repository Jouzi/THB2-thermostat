# Thermostat Setpoint and BLE Control

This document describes the thermostat setpoint functionality added in commit `5ce53f4ab778a87452556e66867fc88d1bf16ee7`, including the firmware behavior and the `th05_setpoint.py` helper script.

## What changed

The firmware now has a dedicated thermostat setpoint value for devices built with `SERVICE_THS`.

- The setpoint is stored separately from the existing trigger configuration.
- It is persisted in flash and restored on boot.
- It can be read or changed through the BLE command channel.
- On LCD models, the small numeric field can show the setpoint instead of humidity on alternating refresh cycles.

The implementation lives in:

- [`bthome_phy6222/source/setpoint.c`](../bthome_phy6222/source/setpoint.c)
- [`bthome_phy6222/source/setpoint.h`](../bthome_phy6222/source/setpoint.h)
- [`bthome_phy6222/source/cmd_parser.c`](../bthome_phy6222/source/cmd_parser.c)

## Setpoint behavior

The stored setpoint uses Celsius internally.

- Range: `4.0 .. 28.0 C`
- Step size: `0.5 C`
- Default: `21.0 C`
- Storage format: `degrees C * 2`

Examples:

- `21.0 C` is stored as `42`
- `22.5 C` is stored as `45`
- `28.0 C` is stored as `56`

If a client writes a value outside the supported range, the firmware clamps it to the nearest valid limit.

Each committed change increments a `version` counter. That counter is returned in the BLE response so a client can detect whether the stored value changed.

## LCD behavior

For screen models, `FLG_SHOW_SETPOINT` is now enabled in the default configuration.

When that flag is enabled:

- The small numeric field alternates between humidity and the thermostat setpoint.
- The alternation period is 4 seconds.
- If the display is configured to show Fahrenheit, the setpoint is converted before rendering.
- The LCD shows an integer value only, because that display area has no decimal point.

Affected LCD implementations in this repository:

- [`bthome_phy6222/source/lcd_th04.c`](../bthome_phy6222/source/lcd_th04.c)
- [`bthome_phy6222/source/lcd_th05.c`](../bthome_phy6222/source/lcd_th05.c)
- [`bthome_phy6222/source/lcd_th05d.c`](../bthome_phy6222/source/lcd_th05d.c)
- [`bthome_phy6222/source/lcd_th05f.c`](../bthome_phy6222/source/lcd_th05f.c)
- [`bthome_phy6222/source/lcd_thb1.c`](../bthome_phy6222/source/lcd_thb1.c)

## BLE command

The setpoint is exposed on the command characteristic `0000fff4-0000-1000-8000-00805f9b34fb`.

Command ID:

- `0x57`

Request formats:

- Get: `[0x57]`
- Set: `[0x57, setpoint_c_x2]`

Response format:

```text
[0x57, setpoint_c_x2, version_lo, version_hi, min_c_x2, max_c_x2, unit_flag]
```

Field meanings:

- `setpoint_c_x2`: current setpoint in `C * 2`
- `version_lo`, `version_hi`: 16-bit change counter
- `min_c_x2`: minimum supported setpoint, currently `8`
- `max_c_x2`: maximum supported setpoint, currently `56`
- `unit_flag`: `0` for Celsius display mode, `1` for Fahrenheit display mode

The BLE protocol definition is declared in [`bthome_phy6222/source/cmd_parser.h`](../bthome_phy6222/source/cmd_parser.h).

## Relationship to trigger output

This feature does not replace the existing trigger configuration described in the main README.

The trigger output on `TX` or `TX2` is still controlled by the trigger configuration in the web UI. The new setpoint feature adds a dedicated value that external software can store and retrieve over BLE. That makes it useful as a thermostat target shared between:

- the device display
- a BLE automation client
- external control logic that wants a simple target temperature value

If you want the device output behavior to follow that target directly, you still need matching trigger settings or host-side logic that keeps trigger thresholds aligned with the setpoint.

## Python helper script

The repository includes [`th05_setpoint.py`](../th05_setpoint.py) for direct BLE access from a computer.

It uses:

- `bleak` for BLE scanning and connection
- characteristic `0xFFF4`
- command `0x57`

Install dependencies:

```bash
pip3 install -r requirements.txt
```

Read the current setpoint:

```bash
python3 th05_setpoint.py 40:B7:FC:19:2F:78 get
```

Set the setpoint to `22.5 C`:

```bash
python3 th05_setpoint.py 40:B7:FC:19:2F:78 set 22.5
```

Optional connection tuning:

```bash
python3 th05_setpoint.py 40:B7:FC:19:2F:78 set 21.0 --retries 5 --scan-timeout 10 --settle-ms 1500
```

Expected output looks like:

```text
40:B7:FC:19:2F:78: setpoint=22.5C (72.5F), version=3, range=4.0..28.0C, display_unit=C
```

## Script behavior

`th05_setpoint.py` is intentionally narrow in scope.

- `get` reads the current setpoint and prints it in both Celsius and Fahrenheit.
- `set` writes a Celsius value, quantized to `0.5 C` steps.
- The script disconnects cleanly and waits briefly so the host BLE stack can settle before the next operation.
- On startup and retry, it performs a scan to warm up the BLE cache, which is particularly useful on Windows.

## Notes and constraints

- The CLI accepts Celsius input only. The script still reports the Fahrenheit equivalent for convenience.
- The firmware response includes the active display unit, but the stored value remains Celsius-based.
- Values outside the valid range are clamped by the firmware.
- If the device is not advertising or a previous BLE session is stuck, the script may need another retry or a Bluetooth reset on the host.

## Troubleshooting

If a command fails:

- Make sure the device is powered and advertising.
- Press the device button if you need to refresh its connectable state.
- Retry with a larger `--scan-timeout` or more `--retries`.
- On Windows, toggle Bluetooth off and on if the previous connection appears stuck.
- If another tool or browser tab is connected to the device, disconnect it first.

## Related files

- [`README.md`](../README.md)
- [`requirements.txt`](../requirements.txt)
- [`docs/user-introduction.md`](./user-introduction.md)
