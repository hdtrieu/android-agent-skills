# Presentation MVI contract

Use this contract when the target project has adopted MVI, or when the user asks for
it. If the project uses another presentation pattern, follow the project and do not
relabel MVVM as MVI. AndroidX ViewModel stays the lifecycle owner of screen state;
MVI only specifies actions, results and reduction.

## Contract and responsibilities

- `<Screen>Action`: typed UI inputs delivered through `onAction`. No Android `Intent` type is needed.
- `<Screen>UiState`: immutable renderable state with a single owner.
- `<Screen>Result`: internal outcomes of actions and asynchronous work.
- `<Screen>Reducer`: pure `(previousState, result) -> nextState`, with no IO,
  coroutine launch, clock, random value, navigation or mutable shared state.
- `<Screen>ViewModel`: receives actions, calls domain use cases, produces results
  and serializes their reduction. Exposes read-only `StateFlow<UiState>`.
- Route/host: lifecycle-aware collection, framework navigation and system dialogs.
- Screen: stateless rendering and callbacks. Local focus/animation state may stay local.

Business decisions belong in domain, not in the reducer. Map domain entities/errors
to UI models before reducing them. No shared DTO/DB/domain/UI model or new base
Store/ViewModel hierarchy is needed. In a feature module, put the contract/reducer
in `presentation/state/`, the ViewModel in `presentation/viewmodel/`, rendering in
`presentation/ui/` and the host route in the feature's `navigation/` package (see
[module structure](module-structure.md)), unless the project has another layout.

## Concurrency and errors

Choose and document an operation policy: cancel previous search, ignore duplicate
submission, or queue ordered work. Cancellation alone does not guarantee that an
old callback stops; compare a request/generation ID before applying its result.
Every result must reduce against the latest state. Never derive new state from a
snapshot captured before a suspend call.

Use `viewModelScope` and injected dispatchers where a dispatcher is needed.
Catch known failures and map them to typed UI errors. Rethrow
`CancellationException`; broad `runCatching` must not turn cancellation into failure.
Retain current content on refresh failure when the product calls for it. Track
operation state separately if multiple operations can run simultaneously.

## Events, navigation and prompts

Durable workflow outcomes, auth transitions and important platform prompts must
survive a temporary absence of a UI collector. Represent pending requests in state
with an ID and acknowledge or complete them with a typed action. The host owns
launching and navigation; ViewModel decides whether a result still matches the
active request. Do not promise exactly-once external side effects across crashes.

An optional transient notification stream is acceptable only when missing that
notification cannot change workflow correctness. Do not use a zero-replay flow for
required navigation, credential prompts or approvals.

Keep tokens, credentials and sensitive challenge payloads out of UiState,
SavedStateHandle, route arguments and logs. Model prompt state with non-secret
identifiers; resolve sensitive data through a scoped platform adapter.

## Verification

Test reducer transitions directly, then ViewModel action/result behavior with
controlled scheduling: duplicate actions, stale responses, retry and cancellation.
UI tests cover rendered states and emitted actions, not DI wiring by default.

The [load/retry example](../assets/mvi-example/LoadContract.kt) and its
[reducer tests](../assets/mvi-example/LoadReducerTest.kt) demonstrate transitions,
not a complete ViewModel.

## Sources

- [Android UI layer / UDF](https://developer.android.com/topic/architecture/ui-layer)
- [UI events](https://developer.android.com/topic/architecture/ui-layer/events)
- [Architecture recommendations](https://developer.android.com/topic/architecture/recommendations)

The sources support UDF and state ownership; the explicit Result/reducer layout is
a convention of this plugin, not an Android requirement.
