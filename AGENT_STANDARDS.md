# AI Agent Standards: THB2-Thermostat

## 1) Change strategy

- Prefer minimal, targeted edits over broad refactors.
- Preserve existing firmware behavior unless user asks for behavior changes.
- Avoid renaming/moving files unless there is a clear need.
- Keep patches focused by concern (firmware logic, tooling script, docs).

## 2) Safe edit boundaries

- Primary feature/fix surface is `bthome_phy6222/source/`.
- Treat `bthome_phy6222/SDK/` as vendor/low-level dependency:
  - Do not modify SDK files unless required and explicitly justified.
  - If SDK edits are unavoidable, document exact reason and risk.
- Do not modify release artifacts in `bin/`, `update_boot/`, `fullflash_jl.bin` unless task is explicitly artifact generation/update.

## 3) Build and verification expectations

- For firmware changes:
  - Try to run `make` in impacted firmware directory (`bthome_phy6222/` or `ota_boot/`).
  - Report whether build was run and whether it passed.
- For Python tooling changes:
  - Run at least syntax check (for example `python3 -m py_compile <file>`).
- If full verification cannot be run, state that clearly and why.

## 4) Code style and implementation norms

- Follow existing C conventions in nearby files (naming, macros, spacing).
- Avoid adding heavy abstractions in constrained embedded paths.
- Keep logging and debug changes minimal and intentional.
- Add comments only when needed to explain non-obvious logic or hardware constraints.

## 5) Firmware-specific caution points

- Respect flash map assumptions (`README.md` documents key regions).
- Be cautious with OTA, boot handoff, settings/history storage, and low-power logic.
- For model-specific behavior, check corresponding `lcd_*` / sensor / board-condition paths to avoid regressions on other devices.

## 6) Documentation standards for agent output

- When changing behavior, update relevant docs (`README.md` or focused docs) in the same task when practical.
- In status/final notes, include:
  - What changed.
  - What was verified.
  - Remaining risks or unverified areas.

## 7) Git and workspace hygiene

- Never revert unrelated local changes.
- Do not use destructive git commands unless explicitly requested.
- Keep commits/patches logically scoped and readable.
