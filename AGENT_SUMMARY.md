# AI Agent Summary: THB2-Thermostat

## What this project is

Custom firmware and tooling for Tuya BLE thermometer/tag devices built on PHY622x2/ST17H6x families.  
Main outcomes in repo:
- Device firmware build sources.
- Ready-to-flash artifacts.
- UART flashing/maintenance scripts.
- Web BLE OTA/config UI.

## Top-level layout

- `bthome_phy6222/`: main firmware app source, SDK, Makefile, web UI.
- `ota_boot/`: OTA bootloader source + Makefile.
- `bin/`: release binaries (`BOOT_*.hex`, `*.bin`).
- `update_boot/`: bootloader OTA update binaries.
- `rdwr_phy62x2.py`: serial flasher utility.
- `auto_time_sync.py`: BLE-based time synchronization daemon.
- `fw.json`: manifest for shipped binaries.
- `README.md`: usage, pinouts, flashing and OTA flow.
- `PROJECT_OVERVIEW.md`: concise project map.

## Core firmware files (high signal)

From `bthome_phy6222/source/`:
- `thb2_main.c`, `thb2_peripheral.c`: app flow, BLE behavior.
- `bthome_beacon.c`: advertisement payload behavior.
- `sensors.c`, `dev_i2c.c`: sensor detection and I2C interactions.
- `battery.c`, `flash_eep.c`: battery and persisted settings/history areas.
- `ble_ota.c`: OTA handoff behavior.
- `config.c`, `cmd_parser.c`: runtime configuration and commands.
- `lcd_th*.c`, `lcd_thb1.c`, `lcd_th04.c`: model-specific display handling.

## Build and flash workflows

- App firmware build: run `make` in `bthome_phy6222/`.
- Bootloader build: run `make` in `ota_boot/`.
- Flash via UART utility: `python3 rdwr_phy62x2.py ...` (see `README.md`).
- OTA provisioning/config generally uses `bthome_phy6222/web/PHY62x2BTHome.html`.

## Practical assumptions

- Toolchain expected: `arm-none-eabi-*` + Python 3.
- This repo mixes first-party firmware code with vendor SDK code under `bthome_phy6222/SDK/`.
- Most feature work should touch `bthome_phy6222/source/` first, not SDK internals.
