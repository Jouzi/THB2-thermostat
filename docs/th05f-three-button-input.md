# TH05F Three-Button Input Design

This document describes a practical way to add three extra buttons to the `TH05F` board while keeping the existing door/window contact function on `RX2`.

The design target is:

- Keep `RX2` as the Home Assistant `Opening` / door-window contact input.
- Reuse `TX2` as a button input, so the trigger output function is dropped.
- Reuse `P25` as a second button input.
- Encode 3 logical buttons on 2 GPIOs.
- Debounce the inputs in firmware with a sampled integrator algorithm rather than edge-only logic.

## Relevant TH05F pads

From the board tracing and current firmware pin map:

- `RX2` -> `GPIO_P18`
- `TX2` -> `GPIO_P20`
- `P25` test pad -> `GPIO_P25`

For TH05F, the current firmware maps:

- `GPIO_INP` -> `GPIO_P18` in [`bthome_phy6222/source/config.h`](../bthome_phy6222/source/config.h)
- `GPIO_TRG` -> `GPIO_P20` in [`bthome_phy6222/source/config.h`](../bthome_phy6222/source/config.h)

That means the clean expansion path is:

- keep `P18 / RX2` for the reed/contact input
- repurpose `P20 / TX2` as button input A
- use `P25` as button input B

## Electrical encoding

Use active-low inputs with pull-ups enabled on both button lines.

- Button 1 pulls `P20` low
- Button 2 pulls `P25` low
- Button 3 pulls both `P20` and `P25` low

Logical decoding:

- `11` -> no button
- `01` -> button 1
- `10` -> button 2
- `00` -> button 3

Here `1` means released and `0` means pressed.

### Wiring notes

Recommended:

- Configure both GPIOs as inputs with pull-ups
- Each button shorts its assigned line to GND
- For button 3, use either:
  - a DPST membrane/contact arrangement, one pole per GPIO
  - or one button plus two small signal diodes so the two GPIOs are not directly tied together

Using diodes for button 3 is preferred over hard-joining the GPIOs because it keeps the lines isolated if firmware configuration changes later.

## Why not use `TM`

`TM` is a test-mode pin used by the PHY6222 programming / boot flow. It is not a normal spare GPIO and should not be used as a button input.

## Why use software debounce

The current application handles the built-in button with GPIO edge callbacks and task-level event processing. It does not currently implement explicit debounce qualification in app code.

The PHY6222 datasheet states that PortA GPIOs support wake-up and debounce, but the current SDK GPIO driver used by this project does not configure the generic GPIO debounce register. The datasheet documents debounce timing clearly for `KSCAN`, but not in comparable detail for generic GPIO interrupt use.

For this reason, a software debounce implementation is the more predictable choice for a board-level button expansion feature.

## Debounce algorithm

The recommended approach is the classic sampled integrator algorithm, applied independently to each physical button line.

The original short reference for this style of debounce is Kenneth A. Kuhn's `debounce.c` note:

- <https://www.kennethkuhn.com/electronics/debounce.c>

For each line:

- Keep an `integrator` counter in the range `0..MAXIMUM`
- Keep a debounced `output` value
- Sample the raw GPIO periodically
- Move the integrator toward `0` when the raw input is low
- Move the integrator toward `MAXIMUM` when the raw input is high
- Change the debounced output only when the integrator reaches `0` or `MAXIMUM`

This gives time hysteresis:

- short glitches and bounce are ignored
- the signal does not need one perfectly stable window
- noisy contacts are filtered more gracefully than with a one-shot delay

This document uses the same core idea as Kuhn's algorithm, but applies it independently to two GPIO lines and then decodes the debounced pair into one logical button state.

### Per-line debounce state

Example structure:

```c
typedef struct {
    uint8_t integrator;
    uint8_t output;
} debounce_t;
```

### Per-line update

Example update function for active-low buttons:

```c
#define BTN_DEBOUNCE_MAX 5

static void debounce_update(debounce_t *d, uint8_t raw_level)
{
    if (raw_level == 0) {
        if (d->integrator > 0) {
            d->integrator--;
        }
    } else {
        if (d->integrator < BTN_DEBOUNCE_MAX) {
            d->integrator++;
        }
    }

    if (d->integrator == 0) {
        d->output = 0;
    } else if (d->integrator >= BTN_DEBOUNCE_MAX) {
        d->output = 1;
        d->integrator = BTN_DEBOUNCE_MAX;
    }
}
```

### Decoding the two debounced lines

After both GPIOs are debounced, decode them into one logical button state:

```c
typedef enum {
    BTN_NONE = 0,
    BTN_1,
    BTN_2,
    BTN_3,
} th05f_btn_state_t;

static th05f_btn_state_t decode_buttons(uint8_t p20, uint8_t p25)
{
    if (p20 && p25) {
        return BTN_NONE;
    } else if (!p20 && p25) {
        return BTN_1;
    } else if (p20 && !p25) {
        return BTN_2;
    } else {
        return BTN_3;
    }
}
```

## Recommended timing

Suggested starting point:

- sample period: `5 ms`
- integrator maximum: `4` or `5`

That gives about `20..25 ms` of effective debounce time.

This is a reasonable starting value for membrane buttons and short board wires.

If testing shows the button response is too sluggish, reduce:

- sample period to `2 ms`, or
- `MAXIMUM` by one step

If testing shows contact chatter still slips through, increase:

- `MAXIMUM`, or
- the sample period slightly

## OSAL integration strategy

The project already uses GPIO edge callbacks to wake the task and post events. A good fit for this codebase is:

1. Register GPIO edge callbacks on `P20` and `P25`
2. On any edge, start a short periodic button-scan timer if not already running
3. On each scan tick:
   - sample both GPIOs
   - update both integrators
   - decode the debounced pair
   - compare the decoded state with the previous stable decoded state
4. Generate press/release actions only on stable state changes
5. Stop the scan timer once:
   - decoded state is `BTN_NONE`, and
   - both integrators are fully settled at the released rail

This keeps idle power low because the scan loop only runs during and shortly after button activity.

## Suggested event model

Treat the decoded button state as a stable logical state machine:

- `BTN_NONE -> BTN_1` = button 1 press
- `BTN_NONE -> BTN_2` = button 2 press
- `BTN_NONE -> BTN_3` = button 3 press
- `BTN_1 -> BTN_NONE` = button 1 release
- `BTN_2 -> BTN_NONE` = button 2 release
- `BTN_3 -> BTN_NONE` = button 3 release

If a transition occurs directly between two non-idle states, the safest interpretation is:

- release old logical button
- press new logical button

That keeps behavior deterministic even if a user rolls from one membrane button to another.

## Middle button versus simultaneous `+` and `-`

In the intended electrical design, the middle button is not the same thing as a user pressing the `+` and `-` buttons at nearly the same time.

The intended middle button behavior is:

- one physical button
- one shared press action
- both GPIO lines pulled low by the same contact action

That means the two lines should have very similar timing and bounce behavior because they originate from the same button press.

By contrast, a human pressing `+` and `-` "simultaneously" is still two separate button actions:

- press start times differ slightly
- release times differ slightly
- bounce patterns differ
- one line may settle before the other

So the raw GPIO waveform signature is usually different from the dedicated middle button, even if the final settled state is also `00`.

In theory, software could try to distinguish those cases by analyzing timing asymmetry between the two lines. For example:

- whether both lines started changing within a very small window
- whether their bounce patterns track each other closely
- whether they are released together or separately

However, that kind of classification is heuristic and not guaranteed to be reliable across switch tolerances, wiring differences, and user behavior.

For the current design, the recommended rule remains:

- treat any stable `00` state as logical button 3

This is simple, deterministic, and matches the stated requirement that simultaneous `+` and `-` presses do not currently need a separate meaning.

## Current firmware touch points

The current single-button and contact handling is concentrated in:

- [`bthome_phy6222/source/thb2_main.c`](../bthome_phy6222/source/thb2_main.c)
- [`bthome_phy6222/source/config.h`](../bthome_phy6222/source/config.h)
- [`bthome_phy6222/source/main.c`](../bthome_phy6222/source/main.c)

The relevant existing mechanisms are:

- GPIO registration with `hal_gpioin_register(...)`
- task events such as `KEY_CHANGE_EVT` and `PIN_INPUT_EVT`
- `GPIO_INP` on `P18` for the door/window contact
- `GPIO_TRG` on `P20`, which would need to be disabled or repurposed

## Implementation outline

At a high level, the firmware change would look like this:

1. Keep `GPIO_INP` on `P18` unchanged
2. Stop using `GPIO_TRG` on `P20` for trigger output on the TH05F button-enabled build
3. Add a second button input definition for `P25`
4. Add a new periodic button scan event
5. Maintain:
   - one debounce integrator for `P20`
   - one debounce integrator for `P25`
   - one stable decoded logical button state
6. Translate decoded button events into the desired actions

## Constraints

- This encoding cannot distinguish `button 1 + button 2 pressed together` from `button 3`, because both produce `00`
- If that distinction is required, use 3 separate GPIOs or an ADC ladder design instead
- The trigger output feature on `TX2 / P20` is incompatible with using `P20` as a button input at the same time

## Related files

- [`README.md`](../README.md)
- [`docs/thermostat-setpoint.md`](./thermostat-setpoint.md)
- [`bthome_phy6222/source/config.h`](../bthome_phy6222/source/config.h)
- [`bthome_phy6222/source/thb2_main.c`](../bthome_phy6222/source/thb2_main.c)
