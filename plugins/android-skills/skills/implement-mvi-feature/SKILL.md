---
name: implement-mvi-feature
description: Plan and implement an Android screen or flow with Clean Architecture + MVI - typed Action, immutable UiState, internal Result, pure Reducer, AndroidX ViewModel, stateless Compose content, route wiring, previews and tests. Use for new features and for changes to an existing state flow in a project that uses (or adopts) MVI.
---

# Implement an MVI feature

Read the [MVI contract](../../references/mvi.md), [module structure](../../references/module-structure.md)
and `android-conventions`, then the repository's own instructions. If the project uses another
presentation pattern, confirm with the user before introducing MVI; never rename MVVM to MVI
without real reducers.

## Step 1 — Scope the behavior

Write down, before any code:

- **Owner**: which feature module owns the screen (or which new module, per the checklist in
  module structure).
- **Inputs**: every user action and every external input (deep link argument, saved state,
  repository stream, system result).
- **States**: loading, empty, content, error, partial/refreshing, disabled/locked — only the ones
  the acceptance criteria require.
- **Transitions**: a table of `state × result → next state`, including failure, retry and
  cancellation.
- **Concurrency policy** per operation: *cancel previous* (search, refresh), *ignore duplicate*
  (submit), or *queue* (ordered writes).
- **Durable outcomes**: navigation after success, prompts, approvals — modelled as pending
  requests with IDs.
- **Restoration**: what survives configuration change (ViewModel) and process death
  (`SavedStateHandle`, non-secret IDs only).

Present this as the plan when the task asks for a plan or the change is non-trivial.

## Step 2 — Domain and data first

- Reuse existing repositories and use cases. Add a use case only for a real business action.
- Repository interface in `domain/repository`, implementation in `data/repository`, mappers in
  `data/mapper`, DI binding in `data/di`.
- Domain errors are typed (`sealed interface ProfileError`) or mapped exceptions — the
  presentation layer must be able to tell them apart without string matching.

## Step 3 — The contract

`presentation/state/ProfileContract.kt` (or split files when large):

```kotlin
internal data class ProfileUiState(
    val profile: ProfileUi? = null,
    val isLoading: Boolean = false,
    val isSaving: Boolean = false,
    val error: ProfileErrorUi? = null,
    val loadRequestId: Long? = null,
    val pendingNavigation: ProfileNavigation? = null,
)

internal sealed interface ProfileAction {
    data object Load : ProfileAction
    data object Retry : ProfileAction
    data class NameChanged(val value: String) : ProfileAction
    data object Save : ProfileAction
    data class NavigationHandled(val id: Long) : ProfileAction
}

internal sealed interface ProfileResult {
    data class LoadStarted(val requestId: Long) : ProfileResult
    data class Loaded(val requestId: Long, val profile: ProfileUi) : ProfileResult
    data class LoadFailed(val requestId: Long, val error: ProfileErrorUi) : ProfileResult
    data class NameEdited(val value: String) : ProfileResult
    data object SaveStarted : ProfileResult
    data class Saved(val navigationId: Long) : ProfileResult
    data class SaveFailed(val error: ProfileErrorUi) : ProfileResult
    data class NavigationAcknowledged(val id: Long) : ProfileResult
}

internal data class ProfileNavigation(val id: Long, val destination: Destination) {
    enum class Destination { Back }
}
```

## Step 4 — The pure reducer

```kotlin
internal object ProfileReducer {
    fun reduce(state: ProfileUiState, result: ProfileResult): ProfileUiState = when (result) {
        is ProfileResult.LoadStarted -> state.copy(isLoading = true, error = null, loadRequestId = result.requestId)
        is ProfileResult.Loaded ->
            if (result.requestId != state.loadRequestId) state
            else state.copy(profile = result.profile, isLoading = false, loadRequestId = null)
        is ProfileResult.LoadFailed ->
            if (result.requestId != state.loadRequestId) state
            else state.copy(isLoading = false, error = result.error, loadRequestId = null)
        is ProfileResult.NameEdited -> state.copy(profile = state.profile?.copy(name = result.value))
        ProfileResult.SaveStarted -> state.copy(isSaving = true, error = null)
        is ProfileResult.Saved -> state.copy(
            isSaving = false,
            pendingNavigation = ProfileNavigation(result.navigationId, ProfileNavigation.Destination.Back),
        )
        is ProfileResult.SaveFailed -> state.copy(isSaving = false, error = result.error)
        is ProfileResult.NavigationAcknowledged ->
            if (state.pendingNavigation?.id == result.id) state.copy(pendingNavigation = null) else state
    }
}
```

No IO, coroutines, clock, random, logging or navigation in the reducer. Generate IDs in the
ViewModel (an injected counter or clock) and pass them in through results.

## Step 5 — The ViewModel

```kotlin
@HiltViewModel
internal class ProfileViewModel @Inject constructor(
    private val getProfile: GetProfileUseCase,
    private val saveProfile: SaveProfileUseCase,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ProfileUiState())
    val uiState: StateFlow<ProfileUiState> = _uiState.asStateFlow()

    private var nextId = 0L
    private var loadJob: Job? = null

    fun onAction(action: ProfileAction) {
        when (action) {
            ProfileAction.Load, ProfileAction.Retry -> load()
            is ProfileAction.NameChanged -> reduce(ProfileResult.NameEdited(action.value))
            ProfileAction.Save -> save()
            is ProfileAction.NavigationHandled -> reduce(ProfileResult.NavigationAcknowledged(action.id))
        }
    }

    private fun load() {
        loadJob?.cancel() // policy: a new load cancels the previous one
        val requestId = ++nextId
        reduce(ProfileResult.LoadStarted(requestId))
        loadJob = viewModelScope.launch {
            val result = try {
                ProfileResult.Loaded(requestId, getProfile().toUi())
            } catch (e: CancellationException) {
                throw e
            } catch (e: ProfileException) {
                ProfileResult.LoadFailed(requestId, e.toUi())
            }
            reduce(result)
        }
    }

    private fun save() {
        val current = _uiState.value
        if (current.isSaving) return // policy: ignore duplicate submit
        val profile = current.profile ?: return
        reduce(ProfileResult.SaveStarted)
        viewModelScope.launch {
            val result = try {
                saveProfile(profile.toDomain())
                ProfileResult.Saved(navigationId = ++nextId)
            } catch (e: CancellationException) {
                throw e
            } catch (e: ProfileException) {
                ProfileResult.SaveFailed(e.toUi())
            }
            reduce(result)
        }
    }

    // Always reduce against the latest state, never a snapshot taken before a suspend call.
    private fun reduce(result: ProfileResult) = _uiState.update { ProfileReducer.reduce(it, result) }
}
```

Trigger the initial load from the route (`LaunchedEffect(Unit) { onAction(Load) }`) or from
`init`, following the repository's convention — not both.

## Step 6 — Route, screen and navigation

- The route collects state with `collectAsStateWithLifecycle()`, hosts platform work
  (permission launchers, system dialogs, sharing) and performs navigation:

```kotlin
val navigation = state.pendingNavigation
LaunchedEffect(navigation?.id) {
    if (navigation != null) {
        onBack()
        viewModel.onAction(ProfileAction.NavigationHandled(navigation.id))
    }
}
```

- The screen is stateless and emits `ProfileAction`s.
- Expose the route from the feature's `navigation/` package and wire it into the app's navigation
  the same way existing features are wired (Navigation 3 entry provider, Navigation Compose
  destination, or the repository's installer pattern). Features do not navigate to each other
  directly; they expose outcome callbacks the app maps.

## Step 7 — Resources and previews

- Strings in every bundled locale; icons as VectorDrawable in the feature's `res/`.
- `@Preview`s in the screen file for each meaningful state, with synthetic fixtures and no-op
  callbacks (see `android-conventions`).

## Step 8 — Tests

Load `writing-tests`. Minimum for a new MVI screen:

| Layer | Cases |
| --- | --- |
| Reducer (pure) | each transition in the Step 1 table; stale request ignored; acknowledgement clears only the matching ID |
| ViewModel | load success/failure; retry; new load cancels old and old result cannot overwrite; duplicate save ignored; cancellation does not become an error |
| Compose content | each state renders the specified elements; actions are emitted from the right controls |
| Use case / repository | mapping and error translation when logic lives there |

## Step 9 — Verify and report

Build the app variant, run the module tests and static checks, compile previews. Report the
transition table you implemented, the concurrency policies, tests added, commands run with
results, and anything not verified (rendered previews, device behavior, process death).

Adapt [the load example](../../assets/mvi-example/LoadContract.kt) only when its semantics fit.
Never introduce a generic Store base class, global event bus or MVI library to satisfy naming.
