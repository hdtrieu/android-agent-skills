# Regression recipes

Twelve defect archetypes for Kotlin/Android, aligned with the MVI contract and
common security boundaries. Read only the recipes matching the change.

| Changed behavior | Recipe |
| --- | --- |
| Parsing, mapping, guarded action parameters | A1; A3 for projected fields |
| Local/remote or dependent state propagation | A2 |
| Lookup, grouping, selection or aggregation | A3; A10 for size limits |
| Concurrent write, duplicate action, retry | A4 |
| State transition, completion gate or terminal state | A5; A9 for changed contracts |
| Session, ownership, authorization or visibility | A6 |
| Refactor, migration to MVI, screen rewrite | A7 |
| Multi-step external operation | A8 |
| Enum, persisted shape, source of truth or revert | A9 |
| Pagination, large import, payload size | A10 |
| Clone/import duplicate, owned file/resource | A11 |
| Debounce, delayed work, pending callback | A12 |

## A1 — Inputs and boundary shapes

Parameterize applicable null, absent JSON field, empty collection, blank/whitespace,
zero/false valid values, unknown enum and malformed shape cases. Missing JSON and
explicit null are different producer inputs: exercise the real parser if this matters.
Do not manufacture impossible nulls in non-nullable Kotlin domain types. Test guarded
indices/IDs at action call sites and assert the contract's no-op, rejection or reset.
Unknown values need the specified typed error/fallback, not an invented default.

For API/import seams, prefer sanitized representative producer payloads plus malformed
variants through the real decoder/mapper. Document provenance and format locally,
without user identifiers, credentials or secrets. If no safe sample is available,
use clearly labeled synthetic fixtures and report the unverified producer assumption.
A captured fixture detects known shapes; it does not make producer CI detect drift.

## A2 — State convergence

Write → read back → observe again; assert the authoritative store and UI converge.
Detect/handle a change twice and assert it does not trigger repeatedly. Test dependent
state resets when switching account/session/tab. Fake-store tests do not prove disk
persistence or correct DI scope; add that harness only when it owns the defect.

## A3 — Identity and projection

Place the target after a differently valued decoy. Use distinct per-account/item values
so first/last/sum and swapped-field errors are visible. Assert selection by identity and
exact grouping/count semantics, including duplicate keys or partial selections when
relevant. Real DB joins require a storage integration test.

## A4 — Concurrency and atomicity

Force the interleave with controlled suspensions/barriers: duplicate submit, old response
after new action, logout/account swap while work is pending. Assert the operation policy
and unchanged unrelated state. For multi-step writes, fail the later step and assert the
specified rollback/incomplete outcome. Test replay/idempotency where the contract requires
it; do not promise exactly-once external effects across crashes. Sequential calls cannot
prove a race fix; mocks cannot prove DB constraints or transactions.

## A5 — Transitions and gates

Enumerate contract-defined legal/rejected transitions with independent expected states;
reading production transition outputs as test expectations hides the same bug. Assert
unrelated content retention, completion/error/retry exits and terminal-state protection.
Inspect every relevant writer/Result branch when adding a state, including refresh and
pending callbacks. Exercise freshness of derived gates after their inputs change.

## A6 — Session and security boundaries

Use synthetic users/accounts A and B. Test allowed and denied operations, read and write
isolation, and unchanged A data after a denied B operation. Force logout/session replacement
before an old result completes; reject stale prompts/challenges. Do not mock the policy
being verified. UI hiding proves presentation only, not server authorization. Platform
biometric/Keystore and deployed authorization require their respective harnesses.

## A7 — Refactor preservation

Characterize the existing observable behavior before rewriting: derived state, error/retry,
static disabled controls, pending prompts and emitted actions. Keep it green through the
refactor. Inspect sibling callers/copies affected by a shared fix; preserve unrelated code
and report out-of-scope defects. Preserve regression coverage or replace it with an
equivalent proof; explain expectation changes rather than accepting new output blindly.

## A8 — External linkage

Test the local consumer contract and the failure half of a multi-step operation. Assert
its specified rollback, retry or incomplete-state policy. Local tests do not prove remote
services converge, deployments agree or reconciliation runs. Report those gaps without
adding cross-service infrastructure or contacting unrelated services.

## A9 — Existing data and reverts

Seed old persisted shapes against new readers/migrations, including data written during
a reverted implementation. Check enum readers/writers and validation changes. Define
compatibility or migration for actual existing data within task scope; do not silently
wipe accounts or weaken encryption. If reconciliation is outside scope, report the
blocking compatibility gap. New-code-created fixtures alone miss these failures.

## A10 — Limits and realistic size

Exercise the relevant bound and bound+1 (pagination, import/file size, duplicates, state
payload). Assert counts and explicit rejection/pagination/truncation per contract. Large
fixtures alone do not measure device performance or Binder limits; use a device/profiling
check when required. Avoid arbitrary giant fixtures unrelated to a real boundary.

## A11 — Resource independence

For duplication/import, assert fresh identity and independent owned resources only where
the contract requires them. Mutate/delete one copy and verify siblings remain intact;
fail resource creation and assert no half-created record. Distinguish intentionally
shared resources from accidental aliasing. Never copy real account secrets into fixtures.

## A12 — Deferred work and lifecycle

Schedule work, change entity/session/callback ownership before its deadline, then advance
the shared test scheduler. Assert the specified latest-value or cancellation behavior,
burst coalescing and no stale write. Test clear/unmount policy explicitly: do not assume
user content must flush on logout, which could cross a session boundary. Recomposition,
Activity recreation and process death are different seams; choose the matching harness.
