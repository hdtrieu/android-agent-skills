---
name: writing-tests
description: Decide what to test and at which layer for an Android change, then write deterministic Kotlin tests - pure reducers, ViewModels with coroutines-test and Turbine, use cases, mappers, repositories, Room/DataStore integration, Robolectric Compose tests - using twelve regression archetypes. Use before writing or modifying any test, when fixing a bug (red first), and when judging coverage in a review.
---

# Write Android tests

The goal is a test that **fails when the behavior regresses** — not coverage numbers. Read the
repository's instructions, then inspect its modules, nearest tests, fakes, test rules and the
test dependencies already declared. Use that stack; do not add a runner, assertion library or
mocking framework, and do not migrate existing tests as a side effect.

References: [regression recipes](references/regression-cases.md) ·
[Kotlin skeletons](references/kotlin-skeletons.md) · [MVI contract](../../references/mvi.md) ·
[Now in Android](../../references/now-in-android.md).

## §0 Workflow

1. **Inventory the behavior.** From the acceptance criteria, ticket test cases and the diff,
   list every observable behavior that changed: success, each specified variant and rejection,
   meaningful boundaries, new action handlers, guarded IDs/indices, dependent state resets.
   An outcome nobody specified is `needs product decision: <scenario>`, not something to pin.
2. **Pick the archetypes** that apply using the §1 trigger table. They add to the contract
   cases; they do not replace them, and you do not apply all twelve to every change.
3. **Pick the owning layer** for each case with §2 — the lowest layer that can detect the defect.
4. **Bug fix: red first.** Write the reproduction, run it, and confirm it fails at the expected
   assertion — not at a compile or import error. Then fix and watch it pass. If the fix already
   exists or red cannot be run, say so.
5. **Write the tests** with the §4 rules and the skeletons. Reuse fixtures, fakes, dispatcher
   rules and builders that exist.
6. **Run** the targeted class, then the module suite. Inspect the diff of the tests themselves.
7. **Report** with §6: what was added, red/green evidence, what is not covered and why.

## §1 Trigger table — what did you touch?

| You changed… | Archetypes |
| --- | --- |
| Parsing, DTO mapping, a guarded parameter, an enum reader | A1 (+A3 for projected fields) |
| A cache, local/remote sync, dependent state that must reset | A2 |
| Lookup by id/position, grouping, aggregation, selection | A3 (+A10 for limits) |
| Concurrent writes, duplicate submit, retry, refresh while loading | A4 |
| A state machine, completion gate, terminal state, reducer | A5 (+A9 when the contract changed) |
| Session, account switch, ownership, permission, visibility | A6 |
| A refactor, migration (XML→Compose, MVVM→MVI), screen rewrite | A7 |
| A multi-step operation spanning services or storage | A8 |
| A persisted shape, enum, schema/migration, or a revert | A9 |
| Pagination, import size, payload limits, large lists | A10 |
| Clone/duplicate/import of a record that owns files or rows | A11 |
| Debounce, delayed work, pending callbacks, lifecycle-bound work | A12 |

Each archetype is described in [regression recipes](references/regression-cases.md) and has a
Kotlin shape in [Kotlin skeletons](references/kotlin-skeletons.md).

## §2 Which layer owns the test?

| Behavior | Test | Notes |
| --- | --- | --- |
| Immutable state transition, loading/error/content retention, stale-result guard | Pure reducer | No coroutines, clock or fakes needed |
| Action → use case → result → state; duplicate submit; stale response; cancellation; retry | ViewModel with controlled fakes | `runTest` + `StandardTestDispatcher`, Turbine or `backgroundScope` collector |
| Business rule, validation, calculation | Use case / domain unit test | Plain JUnit |
| DTO/entity ↔ domain mapping, unknown values, missing fields | Mapper test through the real decoder | Use captured payloads (§3) |
| Cache convergence, persistence, error translation | Repository test with fake data sources | Real Room/DataStore in-memory when storage semantics are the seam |
| Schema migration | Room `MigrationTestHelper` (instrumented or Robolectric) | Seed old data, migrate, read with new code |
| Rendered states, emitted actions, accessibility semantics | Compose content test (Robolectric or instrumented) | Drive the stateless content composable with fixed state |
| Navigation wiring, route-level platform work | Route/host test | Only when the wiring is what changed |
| Keystore, biometrics, Binder limits, real device behavior | Instrumented/device test | Flag `needs device/E2E` if no harness |
| Whole user journey | Maestro flow (`maestro-e2e`) | Only where the repository has a harness |

Rules of thumb:

- A fake repository proves ViewModel behavior, not repository persistence.
- A mocked serializer, DAO or cipher cannot prove the real dependency's semantics; exercise it
  through the real implementation when that is the seam.
- Robolectric proves supported Android framework behavior, not hardware-backed Keystore or
  device-specific rendering.
- When the right harness is missing, say `needs integration harness: <scenario>` or
  `needs device/E2E: <scenario>` instead of silently downgrading to a mock or building
  unrelated infrastructure.

## §3 Captured-payload fixtures for every cross-boundary input

For anything decoded from outside the process (API responses, push payloads, deep links,
imports, QR content, files), test the real decoder/mapper with:

1. A **sanitized representative payload** in `src/test/resources/<feature>/…json`, with its
   source and date noted beside it. No user identifiers, tokens or secrets.
2. **Variants derived from it**: missing key, explicit `null`, empty collection, blank string,
   `0`/`false` as valid values, unknown enum, wrong type, extra unknown fields.
3. The expected behavior per variant from the contract: default, typed error, or rejection.

A captured fixture detects known shapes; it does not make the producer's CI detect drift. Say so
when the producer has no contract test.

## §4 Rules for every test

**Determinism**

- `runTest` with one shared `TestCoroutineScheduler`; inject `StandardTestDispatcher(scheduler)`
  through the repository's dispatcher qualifiers. Replace `Dispatchers.Main` with a rule or
  `Dispatchers.setMain` and reset it in teardown.
- Drive time with `advanceTimeBy`, `advanceUntilIdle`, `runCurrent`; never `Thread.sleep` or
  real delays. Inject a clock for expiry, debounce and retry windows.
- Hold work pending with `CompletableDeferred` or a gated fake to observe loading states and to
  force interleavings (old request finishing after the new one).
- For `stateIn(WhileSubscribed)`, start a collector in `backgroundScope` (or use Turbine) before
  driving the source; assert stable states, not every scheduler-dependent emission.

**Assertions**

- Assert observable outcomes: rendered state, returned values, persisted data, emitted actions.
  Verify interactions only at meaningful boundaries (e.g. "never called the API with a blank id").
- Use distinct synthetic values per field and per item so swapped fields, first/last/sum
  mistakes and stale updates are visible.
- Expected values are written independently — never computed with the production function.
- One behavior per test; name it after the scenario:
  `` `stale load result does not overwrite newer content` ``.

**Doubles**

- Prefer small hand-written fakes that implement the domain interface over mocks for
  repositories and data sources; use the repository's mocking library where it is established.
- Never mock the class under test or the collaborator whose wiring is the defect.
- Do not add generic test base classes or factories for one test. Reuse shared fixtures.

**Secrets and data**

- Never copy real user data, tokens, seeds or challenge payloads into fixtures, UiState under
  test, SavedStateHandle, route arguments or test output.

**Honesty**

- Do not weaken an assertion, update an expectation to match a regression, or `@Ignore` a
  failing test to get green. A changed expectation needs a justified contract change, stated in
  the report.
- Characterization tests for a refactor pass on both old and new code by design; regression
  tests for a behavior change fail when the change is reverted.

## §5 MVI specifics

- Reducer tests need no coroutine setup: construct state, apply result, compare whole state.
- ViewModel tests go through the public surface only: `onAction(...)` in, `uiState` out.
  Cover reduction against the latest state (two results racing), generation guards, duplicate
  submit policy, cancellation that must not become an error, and retry from error.
- Pending navigation/prompt requests: assert the ID appears, survives a missing collector, is
  cleared only by its own acknowledgement, and a stale acknowledgement is ignored.
- Configuration change is not process death. Test `SavedStateHandle` restoration explicitly when
  the feature restores state; never restore secrets.

## §6 Definition of done

Before you call tests done, state:

- [ ] Every changed behavior from §0 has a test at its owning layer, or a named gap.
- [ ] Bug fixes have red-then-green evidence (or the reason it could not be shown).
- [ ] Archetypes from §1 that apply are covered; the others were consciously skipped.
- [ ] No sleeps, real network, real clock or shared mutable state between tests.
- [ ] Targeted and module test commands run, with results quoted.
- [ ] Ticket test cases (if any) mapped one by one to a test, a flow, or a manual step.
- [ ] Gaps listed as `needs product decision:`, `needs integration harness:` or `needs device/E2E:`.

## Running tests

Discover task names from the build — library modules usually have `testDebugUnitTest`, apps
with flavors have `test<Flavor>DebugUnitTest`:

```sh
./gradlew :feature:profile:testDebugUnitTest --tests '*.ProfileViewModelTest'
./gradlew :feature:profile:testDebugUnitTest
./gradlew :app:connectedDebugAndroidTest   # only when an instrumented test is needed and a device is available
```

For Markdown-only changes to this skill, validate content and links; an Android build does not
verify instructions. Declared test libraries and sample tests are not evidence that the app's
tests pass.
