---
name: writing-tests
description: Select and implement meaningful Android regression, reducer, ViewModel, repository and Compose tests for changed behavior and assess missing coverage. Use before writing or modifying any test.
---

# Write Android tests

Read the target repository's instructions, then inspect its modules, nearest tests
and available harness. For presentation tests read [the MVI contract](../../references/mvi.md)
and the relevant [Now in Android examples](../../references/now-in-android.md). Use the
test stack the project already declares (commonly JUnit4/Truth, MockK or fakes, Turbine,
coroutines-test, Robolectric); do not introduce a runner or migrate existing tests as a
side effect. Feature tests stay in their own module; design-system tests cover shared
component behavior only.

## Inventory and regression workflow

1. List the changed observable behaviors from the acceptance criteria and current
   contract: success, specified variants/rejections and meaningful boundaries.
   Include new action handlers, guarded IDs/indices and dependent state resets.
   Flag undefined outcomes as `needs product decision: <scenario>` rather than
   pinning accidental behavior. Documentation-only changes need content checks.
2. Select applicable cases from [the regression recipes](references/regression-cases.md).
   These supplement the contract cases rather than replace them; do not apply all
   twelve recipes to every change.
3. Choose the lowest layer that can detect each defect using the table below.
   Reuse existing fixtures, test doubles and dispatcher rules. Name each added
   case after its scenario and explain what defect it catches when non-obvious.
4. For a bug, write and run the reproduction before fixing when feasible. Confirm
   it fails at the expected assertion, not an import/build error. If the fix already
   exists or red verification cannot run, state that limitation. Behavior-change
   regressions should fail if the change is reverted; characterization tests for
   a refactor intentionally pass on the old and new implementations.
5. Run targeted tests, inspect the resulting diff and report coverage gaps. Do not
   weaken assertions, update expectations to match a regression or permanently
   skip a failing test. Changed expectations need a justified contract change.

## Choose the owning layer

| Behavior | Test |
| --- | --- |
| Immutable state transition, loading/error/content retention | Pure reducer |
| Action execution, duplicate submit, stale response, cancellation | ViewModel with controlled fake use cases |
| Policy, validation, calculation and field mapping | Domain/use-case or mapper unit test |
| Cache convergence, persistence, API error contract | Repository test; real storage/serialization integration when that is the seam |
| Rendered states, retry input, emitted actions, accessibility | State-driven Compose content; route test when host wiring is relevant |
| System prompt, navigation restoration, Android Keystore | Host/lifecycle or device test where required |

A fake repository proves ViewModel behavior, not repository persistence. A mocked
serializer, DB or cipher cannot prove the real dependency's semantics. Exercise
that dependency through the appropriate integration harness. Robolectric is useful
for supported Android runtime behavior, but does not prove hardware-backed Keystore
behavior. Flag missing harnesses explicitly rather than silently downgrading to mocks
or building unrelated infrastructure. For end-to-end flows load `maestro-e2e`.

## Deterministic MVI and coroutine tests

Use `runTest` and `StandardTestDispatcher` with one shared test scheduler. Replace
Main only where required and restore it in teardown. Use controlled completions,
`runCurrent`, scheduler advancement and barriers rather than real sleeps or race
loops. Freeze/inject time for expiry windows, retry and debounce; use distinct
synthetic IDs and values to expose swaps and stale updates.

For `stateIn` with a subscription-driven policy, start the required collector in
`backgroundScope` (or use Turbine) before driving the source; cancel collectors at
completion. Assert stable state, not every scheduler-dependent intermediate emission.
Hold work pending explicitly when testing loading.

Test reducers without IO, clock or coroutine setup. Test ViewModels through typed
Action → use case → Result → UiState, including reduction against the latest state.
Force old requests to finish after new ones and verify generation guards; cancellation
must not become an error or overwrite new content. Duplicate-submit tests assert the
chosen ignore/cancel/queue policy. Loading/content/error and meaningful empty/retry
states belong at the owning layer; do not duplicate every case at every layer.

For durable prompts/navigation, test pending request IDs, acknowledgement, absence
and return of a collector, and rejection of stale responses. Activity recreation is
not process death. Use the appropriate restoration/persistence harness for that claim;
never put secrets, tokens or sensitive challenges in fixtures copied from users,
UiState, SavedStateHandle, route arguments or test output.

Assert rendered state, returned values and persisted outcomes. Interaction checks
are useful for a meaningful boundary contract, not private implementation details.
Keep distinct regression cases; parameterize input matrices where helpful. Do not
mock the function or the collaborator whose wiring is the defect under test.

## Verification and reporting

Discover the affected module/variant tasks in the selected checkout. Run the targeted
class (for example `./gradlew :feature:<name>:testDebugUnitTest --tests '<fully.qualified.TestClass>'`,
only if that task exists), then the relevant module suite and project checks when app
code changes warrant it.
For this skill's Markdown changes, validate frontmatter, references and the final diff;
an Android build does not verify instructions.

Report tests actually run, expected red/green evidence, failures and unrun device/system
cases. Use `needs integration harness: <scenario>` or `needs device/E2E: <scenario>` for
unverified seams in the task summary (and MR description only if preparing an MR).
Sample tests and declared libraries are not evidence of passing app tests or a migrated
checkout.
