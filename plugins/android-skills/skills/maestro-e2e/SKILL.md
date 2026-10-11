---
name: maestro-e2e
description: Write, run and validate Maestro end-to-end flows for an Android app - harness layout, stable selectors via test tags, a debug-only login bypass, screenshots compared with the design, baselining failures against the target branch, and green flows as the definition of done. Use when adding, updating or running Maestro flows, or validating a change end-to-end.
---

# End-to-end testing with Maestro

Use this when the repository has a [Maestro](https://maestro.dev) harness, or the user asks to
add one. Without a harness and without that request, report `needs device/E2E: <scenario>`
rather than building infrastructure.

## Harness layout

```
.maestro/
├── config.yaml          # flow order, tags, shared env
├── flows/               # one journey per file: smoke + feature flows
├── subflows/            # reusable steps: login, onboarding skip, reset state
├── .env.example         # test-account template (copy to .env, never commit .env)
└── screenshots/         # gitignored output
```

## Run

```sh
./gradlew :app:install<Variant>Debug            # the variant flows target
maestro test .maestro/flows/profile_edit.yaml   # one flow while iterating
maestro test --include-tags smoke .maestro/flows
maestro test .maestro/flows                     # everything touched before calling it done
maestro studio                                  # inspect the hierarchy and try selectors
```

Use the repository's runner script when it has one. Report the device or emulator, API level and
app variant you ran against.

## For every change

1. **Run the related flows.** Every flow whose screens or logic the change touches must pass,
   after the build and unit tests succeed. If one fails, fix the implementation and rerun.
2. **Add or update flows.**
   - New feature → a flow that exercises it end to end.
   - Bug fix → a flow that fails before the fix (red) and passes after (green).
   - Refactor or migration → a flow asserting behavioral parity with the old screen.
3. **Start authenticated and select stably** (below).

## Baseline a failure before fixing it

Flows often run against shared test data that drifts. Before looping on a failure, run the same
flow on the target branch:

- **Fails only on your branch** → your regression; fix and rerun until green.
- **Fails identically on the target** → pre-existing. Do not edit the flow to go green and do not
  loop on it. Report parity and note `needs flow-data refresh: <flow — what drifted>` in the MR.

Never claim Maestro is green when it is not. If the changed path has no flow and needs server
state no flow sets up, say `needs E2E: <scenario>` instead of implying coverage.

## Selectors

- Expose Compose test tags as resource ids once at the root:

```kotlin
Modifier.semantics { testTagsAsResourceId = true }
```

- Tag interactive elements and key containers: `Modifier.testTag("profile-save")`.
- In flows select by `id:` first, then exact `text:` from the default locale; never `.*` or
  positional selectors that break on layout changes.

```yaml
appId: ${APP_ID}
---
- runFlow: ../subflows/login.yaml
- tapOn:
    id: "home-profile"
- assertVisible:
    id: "profile-screen"
- tapOn:
    id: "profile-name"
- inputText: "Alex Doe"
- tapOn:
    id: "profile-save"
- assertVisible: "Profile saved"
- takeScreenshot: screenshots/profile_saved
```

## Debug-only login bypass

To keep flows fast and free of MFA, the app may accept launch arguments that sign in a test
account without UI — **only in debug builds**:

- Read `MAESTRO_*` intent extras in a debug source set or behind `BuildConfig.DEBUG`, so the
  code cannot ship in release.
- Pass them from `subflows/login.yaml` with `launchApp: { arguments: { ... } }`, values from
  `${MAESTRO_USER}` environment variables.
- Keep the same argument names across platforms when an iOS harness exists, so flows stay portable.

## UI fidelity

For new screens and UI migrations, flows validate the UI itself, not only that the journey
completes:

- Assert every element the design specifies — labels, fields, buttons — and the empty, loading
  and error states.
- `takeScreenshot` at each key state and compare with the design (spacing, alignment,
  typography, color). For a migration, compare with the legacy screen too.
- Mismatches with the design are defects to fix before calling the work done.

## Guardrails

- Never commit `.maestro/.env`, test credentials or screenshots.
- Never point flows at production accounts or data.
- Flows must be independent: each starts from a known state (`clearState: true` or a reset
  subflow) and does not rely on another flow's leftovers.
- Report flows run, results, and any parity/drift notes; carry them into the MR description.
