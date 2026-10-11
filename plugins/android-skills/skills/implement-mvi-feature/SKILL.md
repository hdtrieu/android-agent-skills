---
name: implement-mvi-feature
description: Plan or implement an Android presentation feature with Clean Architecture and MVI (Action/UiState/Result, pure Reducer, AndroidX ViewModel, Compose).
---

# Implement an MVI feature

Read the [MVI contract](../../references/mvi.md) and
[module structure](../../references/module-structure.md), then the target
repository's instructions. Determine whether the task asks for a design or for
actual code. If the project does not use MVI, confirm before introducing it;
never relabel MVVM as MVI without real reducers.

Identify the feature owner, domain contract, acceptance behavior and existing
navigation/platform bridges. Reuse current infrastructure. Specify the state
transitions, concurrency policy and lifecycle handling before implementing them.

Implement Action/UiState/Result, a pure reducer, and a ViewModel that invokes use
cases and reduces results against the current state. Follow the project's package
layout. Use typed prompt/result IDs for platform work; keep secrets in scoped
adapters. Expose the route from the feature's navigation package and wire it from
the app the way existing features are wired. Add screen previews for the
meaningful states (loading, empty, content, error).

Adapt [the load example](../../assets/mvi-example/LoadContract.kt) only when its
request semantics fit. Do not add a generic store, global event bus or MVI library
to satisfy naming alone.

Verify acceptance transitions, cancellation/stale responses, errors and restoration
using `writing-tests`. Run the affected build and test tasks; report actual results
and remaining gaps.
