# TH05 and Home Assistant Control Design Proposal

This document proposes a practical v1 control design for a `TH05` room unit with three local input buttons (`-`, `middle`, `+`) integrated with Home Assistant.

It is intentionally a proposal, not a frozen specification. The goal is to define a control model that fits the current firmware architecture in this repository and can be implemented incrementally without discarding the existing thermostat setpoint work.

## Goals

The design target is:

- Keep `TH05` as a room terminal, not the final heating controller.
- Keep Home Assistant as the authoritative owner of room-control state.
- Support local user input through three buttons:
  - `-`
  - `middle`
  - `+`
- Support normal setpoint changes and timed override requests.
- Minimize BLE traffic by sending only committed user actions.
- Reuse the current BLE command approach instead of introducing a completely different transport model.

## Existing repository baseline

The current repository already contains the main building blocks for a thermostat-style integration:

- A dedicated persisted thermostat setpoint in:
  - [`bthome_phy6222/source/setpoint.h`](../bthome_phy6222/source/setpoint.h)
  - [`bthome_phy6222/source/setpoint.c`](../bthome_phy6222/source/setpoint.c)
- A BLE command interface on characteristic `0xFFF4` with command `CMD_ID_SETPOINT = 0x57` in:
  - [`bthome_phy6222/source/cmd_parser.h`](../bthome_phy6222/source/cmd_parser.h)
  - [`bthome_phy6222/source/cmd_parser.c`](../bthome_phy6222/source/cmd_parser.c)
- LCD rendering support for showing the setpoint on screen models, including `TH05`, in:
  - [`bthome_phy6222/source/lcd_th05.c`](../bthome_phy6222/source/lcd_th05.c)
- A prior hardware/input design note for three-button expansion:
  - [`docs/th05f-three-button-input.md`](./th05f-three-button-input.md)

The current setpoint behavior is already documented in:

- [`docs/thermostat-setpoint.md`](./thermostat-setpoint.md)

That baseline matters because the proposed v1 should extend the current design, not replace it with a conceptually different protocol that is harder to implement in this firmware.

## Proposed system model

### Functional split

The proposed control split is:

- `TH05` acts as:
  - room sensor
  - room display
  - local user input terminal
- Home Assistant acts as:
  - authoritative owner of target state
  - scheduler
  - timed override owner
  - heating logic owner

This means:

- `TH05` sends user intent.
- Home Assistant computes final state.
- `TH05` displays authoritative state after synchronization.

### Why this split is the right one

This repository already works well as a BLE sensing platform with optional stored configuration. Pushing schedule logic, absolute time handling, and override expiry into the device would add complexity in a constrained firmware path and would make synchronization harder.

For this use case, Home Assistant is the better place to own:

- schedules
- override lifetime
- cancellation rules
- final effective target temperature

## Proposed v1 principles

The recommended v1 principles are:

- Home Assistant is the master for room-control state.
- `TH05` edits locally and commits once.
- Intermediate button presses do not generate BLE writes.
- A normal setpoint change cancels a timed override.
- Timed override from the device is duration-based, not absolute-time based.
- Sensor telemetry continues independently through BTHome advertisements.
- Active control uses the existing BLE command channel, not BTHome advertisements.

## Important adjustment to the earlier draft

The earlier draft expressed commands as JSON messages such as:

- `set_setpoint`
- `start_override`
- `state_sync`

That is useful as a logical model, but it should not be mistaken for the firmware-level wire contract in this repository.

The current firmware uses a compact binary command protocol over the `0xFFF4` GATT characteristic. For this project, the correct design direction is:

- keep the JSON examples as logical semantics if desired
- define the actual transport in compact binary command frames
- extend the existing command table in [`cmd_parser.h`](../bthome_phy6222/source/cmd_parser.h)

This is lower-risk and much more compatible with the current codebase.

## Authoritative state model in Home Assistant

Home Assistant should maintain at least these values for each room:

- `current_temperature`
- `current_humidity`
- `battery`
- `base_setpoint_c`
- `override_active`
- `override_setpoint_c`
- `override_end_time`
- `effective_setpoint_c`
- `state_version`

Definitions:

- `base_setpoint_c`
  - Normal target temperature outside temporary override.
- `override_setpoint_c`
  - Temporary target temperature while override is active.
- `override_end_time`
  - Timestamp computed by Home Assistant when override starts.
- `effective_setpoint_c`
  - The target temperature currently in force.
- `state_version`
  - Monotonic Home Assistant state revision used for synchronization.

## Recommended priority rules in Home Assistant

Recommended priority order:

1. safety and hard limits
2. direct manual setpoint change
3. timed override
4. schedule
5. fallback default

Recommended rule:

- a normal manual setpoint change cancels any active timed override

That should apply regardless of whether the manual change came from:

- `TH05` local buttons
- Home Assistant UI
- another user-facing control path

## Local responsibility on TH05

`TH05` should provide:

- measured room temperature
- measured room humidity
- battery level
- local display
- local button input
- local draft editing for setpoint and override setup

`TH05` should not own:

- room schedule
- override expiry time
- long-lived authoritative thermostat state
- final heating decisions

## Proposed device-side UI model

The earlier draft assumed the bottom two-digit cluster could carry the setpoint display. That is not a good fit for the real `TH05` LCD because the target temperature needs three digits including one decimal place, for example `21.5`.

For that reason, the recommended v1 UI model is scene-based:

- `SENSOR_SCENE`
- `CONTROL_SCENE`
- `EDIT_SETPOINT`
- `SETPOINT_COMMITTED`
- `OVERRIDE_HOURS`
- `OVERRIDE_SETPOINT`
- `OVERRIDE_COMMITTED`
- `STATUS_SCENE`

These are device-local states and do not need to be transmitted directly to Home Assistant in v1.

### Scene concept

In idle operation, the display should alternate between two scenes:

- a sensor scene
- a room-control or room-status scene

This is a better use of the display than trying to keep measurements in the large digits and all control information in the small digits at the same time.

Recommended idle behavior:

- `SENSOR_SCENE` shows measured values
- `CONTROL_SCENE` shows the room target
- if a stronger room status is active, the control scene may be replaced by a status-oriented scene

Suggested starting timing:

- sensor scene visible for `5 s`
- control or status scene visible for `3 .. 5 s`

The exact timing can remain implementation-defined, but automatic alternation should be part of the design.

### Button behavior

Recommended behavior:

- short press `middle` in idle operation
  - toggle immediately between the current idle scenes
  - restart the scene timer so the chosen scene remains visible for a full interval
- long press `middle` in idle operation
  - enter timed override flow
- `+` from `SENSOR_SCENE`
  - switch to `CONTROL_SCENE`
  - enter `EDIT_SETPOINT`
  - seed draft from authoritative base setpoint
  - increment by `0.5 C`
- `-` from `SENSOR_SCENE`
  - switch to `CONTROL_SCENE`
  - enter `EDIT_SETPOINT`
  - seed draft from authoritative base setpoint
  - decrement by `0.5 C`
- `+` from `CONTROL_SCENE`
  - enter `EDIT_SETPOINT`
  - increment by `0.5 C`
- `-` from `CONTROL_SCENE`
  - enter `EDIT_SETPOINT`
  - decrement by `0.5 C`

Inside `EDIT_SETPOINT`:

- `+`
  - increase draft by `0.5 C`
- `-`
  - decrease draft by `0.5 C`
- `middle`
  - commit immediately
- inactivity timeout
  - commit after `5 s`

Inside timed override flow:

- `OVERRIDE_HOURS`
  - `+` or `-` adjusts duration
  - `middle` confirms duration
- `OVERRIDE_SETPOINT`
  - `+` or `-` adjusts override setpoint
  - `middle` commits override

This preserves a simple mental model:

- `+` and `-` mean adjust value
- short `middle` means inspect, toggle, or confirm
- long `middle` means enter the special timed override flow

### Why setpoint edit should target base setpoint

During an active override, the effective setpoint can differ from the normal target. If the device seeds normal editing from `effective_setpoint_c`, the user may accidentally edit the override value instead of the persistent base target.

For that reason, normal `+/-` editing should target:

- `base_setpoint_c`

not:

- `effective_setpoint_c`

## Display proposal

The display proposal should respect real `TH05` LCD constraints instead of assuming a richer UI than the hardware offers.

The current `TH05` LCD implementation in [`bthome_phy6222/source/lcd_th05.c`](../bthome_phy6222/source/lcd_th05.c) already supports:

- a large top numeric area
- a small lower numeric area
- compact symbolic indicators

The key display constraint is:

- the setpoint temperature requires the large three-digit cluster because it needs one decimal place

That means the bottom two-digit cluster should not be treated as the primary setpoint display area.

### Recommended v1 scene semantics

`SENSOR_SCENE`

- top: measured room temperature
- bottom: humidity

`CONTROL_SCENE`

- top: displayed room target temperature
- bottom: `SP` or another compact setpoint marker

`EDIT_SETPOINT`

- top: draft setpoint, blinking if feasible
- bottom: `SP`

`SETPOINT_COMMITTED`

- top: committed setpoint
- bottom: `SP`
- show for `5 s`, then return to idle scene rotation

`OVERRIDE_HOURS`

- top: selected duration
- bottom: `Hr`

`OVERRIDE_SETPOINT`

- top: draft override setpoint, blinking if feasible
- bottom: `SP`

`OVERRIDE_COMMITTED`

- top: committed override setpoint
- bottom: override marker or `SP`
- show for `5 s`, then return to idle scene rotation

`STATUS_SCENE`

- top: status-oriented value or temperature, depending on the condition
- bottom: compact status marker

### Normal idle rotation

Recommended idle behavior:

- alternate automatically between `SENSOR_SCENE` and one room-control or room-status scene

This means:

- scene 1 explains what the room measures
- scene 2 explains what the room control state currently is

In the simplest normal case, scene 2 is `CONTROL_SCENE`.

If a stronger status is active, scene 2 may be replaced by a status-oriented scene.

### Override indication in normal mode

An active timed override should be visible in the idle control scene.

Without that, the user sees a target value but cannot tell whether it is:

- the normal base setpoint
- or a temporary override

For v1, the indication can be minimal:

- icon
- compact marker
- periodic alternate symbol

It does not need to show the exact end time on-device.

### Window-open display

When the window contact is open, the user-facing display should explain the room status, not the actuator fallback target.

That means:

- do not display `4.0 C` just because the TRV may be driven to its minimum target internally
- instead, show a window-open status scene or window-open marker

Recommended behavior:

- keep `SENSOR_SCENE` unchanged
- replace the ordinary `CONTROL_SCENE` with a window-oriented `STATUS_SCENE`

This lets the panel communicate:

- the room measurement
- the fact that heating is suspended because the window is open

without exposing the low-level actuator workaround.

### Override and window-open priority

Recommended idle-scene priority:

1. `SENSOR_SCENE`
2. if window is open, show a window-oriented `STATUS_SCENE`
3. else if override is active, show `CONTROL_SCENE` with override marker
4. else show ordinary `CONTROL_SCENE`

This makes the currently relevant room condition dominate the control/status scene.

## Numeric conventions

### Temperature resolution

Recommended:

- unit: Celsius
- resolution: `0.5 C`

This matches the current implementation already present in the firmware.

### Setpoint range

The current implementation already uses:

- minimum: `4.0 C`
- maximum: `28.0 C`
- default: `21.0 C`

Those values are defined in [`bthome_phy6222/source/setpoint.h`](../bthome_phy6222/source/setpoint.h).

For v1, the design proposal recommends keeping those existing limits unless there is a deliberate cross-stack decision to change them in:

- firmware
- tools
- Home Assistant integration
- documentation

Using a new nominal range such as `5.0 .. 30.0 C` only in the design would create avoidable mismatch.

### Override duration

Recommended:

- unit: hours
- step: integer hours
- minimum: `1`
- maximum: implementation-defined, for example `24`

This is sufficient for v1 and avoids device clock dependence.

## Transport model

### Telemetry path

Sensor telemetry should continue to use BTHome advertisements independently:

- temperature
- humidity
- battery

This preserves compatibility with existing passive BLE reception in Home Assistant.

### Control path

Control commands should use the active BLE command channel, not advertisements.

For this repository, that means:

- GATT connection
- write to the existing command characteristic
- binary command frames parsed by [`cmd_parser.c`](../bthome_phy6222/source/cmd_parser.c)

## Proposed v1 command surface

The recommended v1 logical control surface is still:

`TH05 -> HA`

- set base setpoint
- start timed override

`HA -> TH05`

- authoritative state sync

However, the firmware-level implementation should be binary and should extend the current command set rather than replacing it.

### Keep the existing setpoint command

The repository already has `CMD_ID_SETPOINT = 0x57` for get/set of the persisted thermostat setpoint.

That command should remain.

Reasons:

- it already exists
- it already has client support documented
- it already includes a version counter
- it is useful even outside a full HA thermostat flow

### Proposed additional commands

Recommended additions for a future implementation:

- `CMD_ID_OVERRIDE_REQ`
  - device-to-HA request for timed override
- `CMD_ID_STATE_SYNC`
  - HA-to-device authoritative state write

The exact numeric IDs can be chosen later. This proposal is only defining their role.

## Proposed binary semantics

The exact byte layout is intentionally deferred, but the semantics should be:

### TH05 to Home Assistant

#### Set base setpoint

Fields:

- command id
- setpoint in `C * 2`
- request id

Meaning:

- user committed a new normal target temperature

Recommended Home Assistant behavior:

- cancel active override if present
- update `base_setpoint_c`
- recompute `effective_setpoint_c`
- send authoritative state sync back to the device

#### Start timed override

Fields:

- command id
- duration in hours
- setpoint in `C * 2`
- request id

Meaning:

- user committed a temporary override request

Recommended Home Assistant behavior:

- set `override_active = true`
- set `override_setpoint_c`
- compute `override_end_time = now + duration`
- recompute `effective_setpoint_c`
- send authoritative state sync back to the device

### Home Assistant to TH05

#### State sync

Fields should include at least:

- command id
- `base_setpoint_c_x2`
- `display_setpoint_c_x2`
- `override_active`
- `window_open`
- `state_version`
- optional result code

Optional future fields:

- `override_setpoint_c_x2`
- `override_remaining_min`
- compact status code for scene selection

Meaning:

- Home Assistant informs the device about the authoritative state relevant to display and local editing

The meaning of `display_setpoint_c_x2` should be explicit:

- it is the room-facing target temperature the panel should display in `CONTROL_SCENE`
- it is not necessarily the raw actuator target currently sent to the TRV

This distinction is important when a window-open condition causes Home Assistant or Better Thermostat to drive the TRV to its minimum target internally.

## Why request and state versions matter

The earlier abstract draft did not define idempotency or synchronization counters. For a BLE-connected device, that omission is risky.

Without versioning or request identifiers:

- a retry can be ambiguous
- a disconnect after write can leave the device unsure whether HA accepted the change
- stale state can overwrite fresh state after reconnect

For that reason, the v1 design should include:

- `request_id` on device-originated commits
- `state_version` on Home Assistant authoritative sync

The existing setpoint path already uses a device-side version counter. Extending that approach is more robust than relying on timing alone.

## Startup and resynchronization behavior

### TH05 restart

After restart, `TH05` may show its locally stored setpoint as a provisional value for usability, but that value must not be treated as authoritative after Home Assistant resynchronizes.

Recommended rule:

- local cached state is provisional
- Home Assistant state wins after sync

### Home Assistant restart

After Home Assistant restart, the integration should resend authoritative state when it next establishes contact with the device.

### State arrival during local editing

This case should be defined explicitly:

- if `TH05` is in an edit state and Home Assistant sends a new sync, the device should store the incoming authoritative state but avoid immediately disrupting the local draft
- after commit, cancel, or timeout, the device should reconcile with the newest authoritative state

This keeps the UI stable while still preserving Home Assistant authority.

## Validation rules

Validation should exist on both sides.

### On TH05

The device should locally clamp:

- setpoint range
- override duration range

This improves local UX and avoids needless invalid requests.

### On Home Assistant

Home Assistant should independently validate all received requests.

For base setpoint:

- reject or clamp malformed values
- reject or clamp out-of-range values

For override requests:

- reject or clamp malformed duration
- reject or clamp out-of-range duration
- reject or clamp out-of-range setpoint

If Home Assistant corrects a value, the corrected authoritative state should be returned in `state_sync`.

## Failure handling

### Device commit but HA not reached

If `TH05` cannot deliver a control command:

- it should not permanently assume success
- local committed display may be shown briefly as feedback
- the next authoritative sync from Home Assistant remains final

An explicit local error indicator can be added later, but it is not required for v1.

### Lost connection after write

If `TH05` writes a request and disconnects before confirmation:

- Home Assistant should still return authoritative state on next successful contact
- `request_id` and `state_version` reduce ambiguity

## Out of scope for v1

The following should remain out of scope:

- full device-side scheduling
- local heating-actuator control decisions on `TH05`
- absolute time synchronization solely for override expiry handling
- complex menu trees
- multiple override classes
- cryptographic framing details for active control
- advanced retry and transaction semantics beyond simple request and state versioning

## Implementation direction for this repository

If this proposal is accepted, the implementation should likely proceed in this order:

1. extend the input subsystem for three logical buttons
2. add device-local UI state handling for setpoint edit and override flow
3. preserve `CMD_ID_SETPOINT = 0x57` as the basic persisted setpoint command
4. add new BLE command ids for override request and authoritative state sync
5. update the LCD logic to show edit and override states
6. add a Home Assistant-side bridge or integration that can actively connect over BLE and exchange command messages

This sequence keeps risk low and allows staged testing.

## Open design questions

The following questions still need a concrete decision before implementation:

- Should Home Assistant write `base_setpoint` to the existing `0x57` setpoint storage directly, or should `0x57` remain a local cached value while a richer HA sync command carries full authority?
- Should `TH05` support an explicit `cancel override` action later, for example by a longer press sequence from `CONTROL_SCENE`?
- Should the exact idle-scene timing be `5/5`, `5/3`, or another ratio?
- What exact BLE central component will mediate writes:
  - custom Home Assistant integration
  - ESPHome proxy
  - external daemon
- Should `state_sync` include `override_remaining_min` in v1 for display/debugging, or is `override_active` enough?

## Recommended v1 summary

The recommended v1 design is:

- keep Home Assistant authoritative
- keep `TH05` as a local room terminal
- keep telemetry in BTHome advertisements
- keep control on the active BLE command channel
- keep the existing setpoint command
- add binary commands for timed override request and authoritative state sync
- use `request_id` and `state_version`
- treat a normal setpoint change as cancellation of timed override

That is enough to implement:

- local room target adjustment
- timed override requests from the device
- clean Home Assistant ownership of schedules and logic
- a firmware design that stays compatible with the current repository structure
