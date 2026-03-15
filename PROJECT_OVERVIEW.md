# THB2-thermostat Repository Overview

## Purpose
Custom BLE firmware suite for Tuya thermometers/keyfobs on PHY622x2/ST17H6x chips. Broadcasts BTHome v2 telemetry and optional Apple Find My–style beacons. Supports models: THB1/2/3, BTH01, TH04/05 variants, TH05F, KEY2, HDP16, TN6ATAG3 with CHT83xx, SHT30/CHT832x, AHT20-30 sensors.

## Release Artifacts
- `bin/`: ready-to-flash boot (`BOOT_*.hex`) and app (`*.bin`) images v2.1; mapping in `bin/README.md`.
- `update_boot/`: OTA bootloader upgrade BINs v2.1.
- `fw.json`: lists current custom and update-boot binaries for tooling.

## Tooling & Scripts
- `rdwr_phy62x2.py` (+ `wr_*.cmd`): pyserial flasher for USB-UART; parses Intel HEX, erases/writes flash, supports PHY62x2/ST17H66B/TG7100B.
- `auto_time_sync.py`: Bleak daemon; scans for BTHome UUID 0xFCD2, connects, reads time (0x33), sets time (0x23) when drift >3s; retries/cooldowns.
- `bthome_phy6222/web/PHY62x2BTHome.html`: browser UI for BLE provisioning/OTA, graphs; works offline.

## Firmware Source Layout
- `bthome_phy6222/source/`: main APP
  - `thb2_main.c`: BLE peripheral app glue.
  - `bthome_beacon.*`: BTHome advertising payloads.
  - `ble_ota.*`: OTA handoff to bootloader.
  - `sensors.c` + `dev_i2c.*`: sensor drivers.
  - `battery.c`, `flash_eep.*`: battery measurement and settings storage.
  - LCD drivers per model: `lcd_thb1.c`, `lcd_th05*.c`, `lcd_th04.c`.
  - `trigger.*`: TX/TX2 hysteresis control; `buzzer.*`: audible alerts.
  - `findmy_beacon.*`: experimental Find My beaconing.
  - `cmd_parser.*`, `config.*`, `logger.*`, `history` via `flash_eep` area.
- `bthome_phy6222/Makefile`, `mk_all.py`: GCC build orchestration; `SDK/` contains BLE stack, mesh libs, drivers, CMSIS startup, linker scripts.
- `ota_boot/`: minimal bootloader source + Makefile (ARM GCC, cortex-m0, `ota_upboot.ld`).

## Behavior & Features (default settings)
- Adverts BTHome every 5s; sensor read every 10s; battery every 60s; history every 30 min.
- Button shortens advert interval for 60s for easier connection.
- Hysteresis-controlled TX/TX2 output; open/close counter on RX/RX2 with debounce strategy; optional encrypted ads (BindKey); Fahrenheit display toggle; LCD sleep; deep sleep on low battery.

## Flash Layout (512 KB)
- 0x00000 ROM used (8 KB)
- 0x02000 Boot info (4 KB)
- 0x03000 Boot w/ OTA (52 KB)
- 0x10000 APP (128 KB)
- 0x30000 History (304 KB)
- 0x7C000 Settings/EEP (16 KB)

## Usage Quick Steps
1) Flash boot via USB-UART: `python rdwr_phy62x2.py -p COMx -e -r wh BOOT_*.hex`.
2) OTA app with `PHY62x2BTHome.html` (Connect → OTA tab → select `*.bin` → Start). APP can also be written directly at 0x10000.
3) Optional: run `python auto_time_sync.py` to keep device clocks aligned.

## Build Notes
- Uses GNU Arm Embedded Toolchain. Build APP in `bthome_phy6222/`; build bootloader in `ota_boot/`. See respective Makefiles for flags and linker scripts.

## External Links
- Device pages & datasheets referenced throughout README for pinouts and photos (e.g., THB1/2/3, TH05 variants, TH04, BTH01, KEY2, HDP16, TN-6ATAG3).
