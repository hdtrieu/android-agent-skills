---
name: maestro-e2e
description: Write, run and validate Maestro end-to-end flows for an Android app - stable selectors, debug-only login bypass, screenshots against the design, and treating green flows as the definition of done. Use when adding, updating or running Maestro flows or validating a change end-to-end.
---

# End-to-end testing with Maestro

Use this when the repository has a [Maestro](https://maestro.dev) harness (usually
`.maestro/` at the repo root with `flows/`, `subflows/`, `config.yaml`) or the user
asks to add one. If there is no harness and none was requested, report
`needs device/E2E: <scenario>` instead of building one.

## Run

```sh
./gradlew :app:installDebug          # or the project's debug variant
maestro test .maestro/flows/<flow>.yaml
maestro test .maestro/flows          # all flows
maestro studio                       # inspect selectors interactively
```

Use the repository's own runner script when it has one. Report the device/emulator
and app variant used.

## For every change

1. **Run the related flows.** Every flow whose UI or logic the change touches must
   pass, after the build and unit tests succeed. If a flow fails, fix the
   implementation and rerun until green.
2. **Add or update flows.** New feature: a flow that exercises it end-to-end.
   Refactor or migration: a flow that asserts behavioral parity. Bug fix: a flow that
   fails before the fix (red) and passes after (green).
3. **Start authenticated, select stably.** Reuse a login subflow via `runFlow`.
   Assert stable anchors (resource IDs, test tags exposed as `testTagsAsResourceId`,
   or exact accessibility text), never `.*`.

## UI fidelity

For new screens and UI migrations, assert the concrete elements the design
specifies: labels, fields, buttons, and the empty/loading/error states. Call
`takeScreenshot` at each key state and compare with the design (spacing,
alignment, typography, colors). For a migration, compare against the legacy
screen too. Treat mismatches as defects to fix before calling the work done.

## Debug-only login bypass

To keep flows fast and free of MFA, the app may read `MAESTRO_*` launch arguments
(intent extras) and, **in debug builds only**, sign in to a test account without UI.
Keep the bypass behind `BuildConfig.DEBUG` (or a debug source set) so it cannot ship
in release. Pass the arguments from the login subflow via `launchApp: arguments:`.

## Guardrails

- Test accounts live in `.maestro/.env` (from `.env.example`); never commit it.
  Pass values with `maestro test -e NAME=value` or the env file.
- Screenshots go to a gitignored directory.
- Never point flows at production accounts or data.
