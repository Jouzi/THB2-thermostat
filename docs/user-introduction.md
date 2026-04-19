# THB2 Thermometer Configuration and BLE Basics

This document is a short introduction for users of the PHY62x2 BTHome firmware and OTA web page. It explains how the main timing settings work, how to reduce battery use, and what BLE can and cannot do when integrating with Home Assistant.

## What the device does

The thermometer primarily works in BLE advertising mode:

- It measures temperature and humidity.
- It broadcasts the latest values in BTHome format.
- Home Assistant can receive those BLE advertisements without keeping a permanent connection to the device.

This is the low-power operating mode. It is the reason the device can run for a long time on battery when configured sensibly.

## The three timing concepts

There are three related but different timing concepts in the OTA web page:

1. `Advertising interval`
2. `Measurement step`
3. `Battery survey interval`

These are not the same thing.

### Advertising interval

`Advertising interval` is how often the thermometer sends a BLE advertisement packet.

- Smaller value: more frequent BLE packets, faster updates, higher battery use
- Larger value: fewer BLE packets, slower updates, lower battery use

The UI uses milliseconds, but internally the firmware stores this as units of `62.5 ms`.

Examples:

- `62.5 ms` means very fast advertising
- `1000 ms` means 1 BLE packet per second
- `5000 ms` means 1 BLE packet every 5 seconds

## Measurement step

`Measurement step` is not a time in milliseconds by itself. It is a multiplier of the advertising interval.

The actual sensor sampling period is:

```text
Sampling period = Advertising interval × Measurement step
```

Examples:

- `62.5 ms × 2 = 125 ms`
- `1000 ms × 2 = 2000 ms = 2 s`
- `5000 ms × 2 = 10000 ms = 10 s`

This is the most important setting for slowing down temperature sampling.

## Battery survey interval

`Battery survey interval` controls how often battery voltage is checked.

- It does not directly control temperature sampling
- A very small value increases battery use

For battery operation, a value like `60 seconds` is usually much more reasonable than `2 seconds`.

## What your current settings mean

From the screenshot:

- `Advertising interval = 62.5 ms`
- `Measurement step = 2`
- `Battery survey interval = 2 s`
- `Conn. Latency = 30 ms`
- `Tx Power = +5 dBm`

That means:

```text
Sampling period = 62.5 ms × 2 = 125 ms
```

So the sensor is effectively sampled about 8 times per second. That is very aggressive for a battery thermometer.

It also advertises very often, checks the battery very often, and uses the highest radio power. All of that pushes consumption up.

## Recommended low-power settings

### Option A: about 1 sample every 2 seconds

Use:

- `Advertising interval = 1000`
- `Measurement step = 2`
- `Battery survey interval = 60`
- `Conn. Latency = 900`
- `Tx Power = 0 dBm` or `-5 dBm` if reception remains reliable

Result:

```text
1000 ms × 2 = 2000 ms = 2 s
```

### Option B: about 1 sample every 10 seconds

Use:

- `Advertising interval = 5000`
- `Measurement step = 2`
- `Battery survey interval = 60`
- `Conn. Latency = 900`
- `Tx Power = 0 dBm` or `-5 dBm`

Result:

```text
5000 ms × 2 = 10000 ms = 10 s
```

This is close to the firmware defaults and is much more suitable for battery operation.

## Alternative: keep fast advertising, slow only measurements

If for some reason you want frequent BLE advertisements but slower sensor sampling, you can change only `Measurement step`.

With `Advertising interval = 62.5 ms`:

- `Measurement step = 32` gives about `2.0 s`
- `Measurement step = 160` gives about `10.0 s`

This works, but it is not the best option for battery life because the radio still wakes up very often to advertise.

## Other settings worth knowing

### Conn. Latency

`Conn. Latency` matters while the device is actively connected over BLE, for example from the OTA web page.

- Smaller value: the connection exchanges data more often, less latency, more power use
- Larger value: slower interaction, lower power use during connection

For a battery device, `900 ms` is a sensible value unless you specifically need a very responsive interactive BLE session.

Important: this setting does not define the passive BTHome advertising cadence seen by Home Assistant.

### Number of event transmissions

This is used for event bursts, such as button or input events. It is not the main temperature sampling rate.

### History interval

`History interval` is based on the measurement period, not absolute seconds. A value of `0` disables history logging.

That is good for saving flash wear and some energy if you do not need onboard history.

### Notification

This applies to connected BLE notification mode, not passive BTHome advertising mode.

For normal Home Assistant BTHome use, the critical settings are still:

- advertising interval
- measurement step
- tx power
- battery survey interval

## BLE basics in plain language

BLE has two common communication styles:

### 1. Advertising

The device periodically broadcasts small packets.

- Very low power
- One-to-many
- Great for sensors
- No persistent connection required

This is how BTHome works and how Home Assistant usually receives values from this thermometer.

### 2. Connected GATT mode

A phone, browser, ESP32, or another BLE central device opens a connection and reads or writes characteristics.

- Higher power
- Two-way communication
- Good for configuration and control

The OTA web page uses this mode when you press `Connect`.

## Can Home Assistant send information back to the thermometer?

Yes in principle, but not through normal passive BTHome advertising alone.

BTHome advertisements are effectively one-way:

- thermometer -> Home Assistant

To send a target temperature from Home Assistant back to the thermometer, something must establish a BLE connection and write data to the device's GATT command interface.

## What the firmware already supports

The firmware already has a command interface in connected BLE mode. It supports writable commands for:

- device configuration
- trigger configuration
- time setting
- sensor configuration
- other maintenance and OTA functions

The trigger configuration already includes threshold and hysteresis fields, so the device can locally drive its trigger output based on temperature or humidity rules.

That means the device is not limited to one-way sensing at the firmware level. It already has a control path over BLE connection mode.

## What Home Assistant usually supports

Standard Home Assistant BTHome support is normally passive BLE reception:

- Home Assistant listens for advertisements
- It decodes them into sensor entities
- It does not usually maintain a BLE connection and write custom GATT commands back to the device

So if you want thermostat behavior such as:

- Home Assistant computes a target temperature
- Home Assistant sends that target to the thermometer
- The thermometer changes local output behavior

you generally need more than the default BTHome integration.

## Practical options for thermostat-style writeback

### Option 1: Keep control logic in Home Assistant

Home Assistant reads the thermometer and controls some separate relay, TRV, or switch entity.

This is the simplest architecture and usually the most robust.

### Option 2: Use a custom BLE client

A custom integration, ESPHome node, Bluetooth proxy with custom code, or another BLE-capable controller could:

- connect to the thermometer
- write the target or trigger settings
- disconnect

This is technically feasible, but it requires custom software because it is outside normal BTHome sensor reception.

### Option 3: Extend the firmware protocol

The current firmware already supports trigger and config writes, but if you want a dedicated "target temperature" concept with thermostat semantics, the firmware and client software could be extended to define a cleaner command for that workflow.

## Suggested first step

For now, the best immediate change for battery life is:

- set `Advertising interval` to `1000 ms` and `Measurement step` to `2` for a 2-second sample period

Later, if battery life matters more than update speed, move to:

- `Advertising interval = 5000 ms`
- `Measurement step = 2`

If you later want thermostat behavior, the next design question is not only firmware. It is deciding which BLE central device will connect and write settings back to the thermometer:

- Home Assistant with custom integration
- ESPHome or ESP32 proxy
- browser tool
- dedicated gateway

Without that connected control channel, BTHome alone remains a sensor broadcast protocol rather than a full thermostat control protocol.

## Encrypted advertising with BindKey

The firmware supports encrypted BTHome advertisements using a `BindKey`.

This protects the measurement payload from casual passive listeners nearby. Someone may still see that a BLE device exists, but without the correct key they should not be able to decode the temperature and humidity values.

### What encryption covers

This feature encrypts the BTHome advertisement payload.

It does not mean:

- that the device becomes invisible over BLE
- that every possible BLE interaction is blocked
- that the device becomes suitable for safety-critical authentication use

It is mainly a privacy feature for the advertised sensor data.

### Where the setting is in the OTA page

There are two relevant controls in the OTA web page:

- `Config` -> `Encrypted advertising`
- `Service` -> `BindKey`

The key format is:

- `16 bytes`
- written as `32 hexadecimal characters`
- no spaces
- example format: `00112233445566778899aabbccddeeff`

### Recommended setup procedure

1. Connect to the device in the OTA web page.
2. Open the `Service` tab.
3. Read the existing `BindKey`, or write your own random key.
4. Save that key somewhere safe.
5. Go back to the `Config` tab.
6. Enable `Encrypted advertising`.
7. Click `Write`.
8. In Home Assistant, configure the same bindkey for that device.

### Important note about the key

If no bindkey exists yet, the firmware can generate one automatically and store it internally.

That is convenient, but writing and recording your own random key is often safer operationally because you know exactly what key was used.

If you lose the bindkey, Home Assistant will not be able to decrypt the sensor data.

## Home Assistant setup for encrypted BTHome devices

Home Assistant can work with encrypted BTHome devices, but it must know the device's bindkey.

### New encrypted device

If the thermometer is discovered by Home Assistant as encrypted from the beginning, Home Assistant should normally prompt for the bindkey during setup or configuration.

### Existing device switched from unencrypted to encrypted

This case is more confusing and is exactly what often happens in practice.

Typical behavior:

1. The device was already known to Home Assistant in unencrypted mode.
2. Encryption is enabled later in the thermometer.
3. Home Assistant still shows the last known old value for a while.
4. After some time, the device may become `Unavailable`.
5. The `BTHome` integration shows that one device has a problem.
6. Using `Reconfigure` on that device or integration allows entering the bindkey.
7. After enough fresh packets are received, the device starts working again.

This delayed recovery is normal. It can take a few minutes.

### Practical Home Assistant recovery flow

If you enable encryption and the device stops updating:

1. Wait a little while for new advertisements to arrive.
2. Open `Settings` -> `Devices & Services`.
3. Open the `BTHome` integration.
4. Look for a warning about the device.
5. Use `Reconfigure`.
6. Enter the `32`-character bindkey.
7. Wait again for fresh encrypted packets to be received and decoded.

If necessary, Home Assistant may briefly show:

- stale old values
- `Unavailable`
- delayed rediscovery or recovery

That does not automatically mean something is broken.

## Transmission monitor and other BLE monitor tools

If you use additional Home Assistant BLE tools besides the official `BTHome` integration, remember that they may behave independently.

Examples include:

- transmission monitors
- passive BLE monitor integrations
- custom Bluetooth dashboards

Important:

- entering the bindkey in the official `BTHome` integration may not automatically configure that key in other BLE monitoring tools
- some tools may need their own separate encryption key entry
- some tools may simply need time to rediscover the device after the advertising format changes

In practice, after switching to encrypted advertising, some monitors may temporarily stop showing the device's MAC address or data and then recover several minutes later.

## Security expectations and limitations

Encrypted BTHome advertising is useful, but expectations should stay realistic.

It helps with:

- preventing casual nearby observers from reading the advertised temperature and humidity
- improving privacy of the sensor payload

It does not guarantee:

- strong anti-spoof protection for control logic
- full-device hardening
- protection against every BLE attack model

For ordinary home telemetry privacy, it is still a sensible feature and worth enabling.

## Thermostat setpoint

The firmware also supports a separate thermostat setpoint value that can be stored in the device and read back over BLE.

- Range: `4.0 .. 28.0 C`
- Step: `0.5 C`
- Default: `21.0 C`
- On LCD models, the small numeric field can alternate between humidity and this setpoint

If you need to read or write that value from a computer, use [`th05_setpoint.py`](../th05_setpoint.py). Full details and examples are in [thermostat-setpoint.md](./thermostat-setpoint.md).
