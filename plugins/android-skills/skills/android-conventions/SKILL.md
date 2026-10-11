---
name: android-conventions
description: Kotlin and Android coding standards - naming, module and package layout, Jetpack Compose screens and previews, MVI/UDF state, use cases, Hilt DI, dispatcher injection, Coroutines/Flow, error handling, design-system tokens, resources and localization, persistence, logging, and generated code. Load before writing, reviewing or refactoring Kotlin in an Android app.
---

# Android conventions

These are the default standards. **The target repository wins**: read its `CLAUDE.md` /
`AGENTS.md`, `README`, `ARCHITECTURE.md`, ADRs, `.claude/rules/*.md` whose `paths:` match the
files you touch, `.editorconfig`, detekt/ktlint/spotless config, and the nearest existing code.
When the repository has a different established pattern, follow it and do not migrate it as a
side effect. Resolve documentation drift from current source and say so.

Related: [module structure](../../references/module-structure.md) ·
[MVI contract](../../references/mvi.md) · [Now in Android](../../references/now-in-android.md) ·
`implement-mvi-feature` · `writing-tests`.

## Before the first edit

1. Read `settings.gradle.kts` to learn the real module graph and `gradle/libs.versions.toml`
   for the libraries that already exist.
2. Find the closest existing feature that does something similar and copy its shape — package
   names, file split, DI module, test layout. Consistency with neighbors beats a better idea.
3. Check the design-system module for a component before writing a composable.
4. Note the build variants (`./gradlew :app:tasks --group build`) so you build and test the
   right one.

## Naming

- Files, classes, interfaces: `PascalCase`; the file name matches its primary type.
- Functions, properties, parameters: `camelCase`. Constants: follow the repository
  (`const val MAX_RETRIES` at top level, or `camelCase` in a `companion object`).
- Implementations: follow the repository's suffix/prefix — `DefaultUserRepository` or
  `UserRepositoryImpl`. Never mix both in one module.
- Screen-scoped types share the screen's name: `ProfileScreen`, `ProfileRoute`,
  `ProfileViewModel`, `ProfileUiState`, `ProfileAction`, `ProfileResult`, `ProfileReducer`.
- Test classes mirror the subject: `ProfileReducerTest`, `ProfileViewModelTest`.
- Booleans read as predicates: `isLoading`, `hasError`, `canSubmit`.

One top-level public type per file. A ViewModel never lives in its screen's file.

## Modules and layers

Follow [module structure](../../references/module-structure.md):

- `app → feature → core / design system`; features never depend on each other; core never
  depends on a feature or the app.
- Inside a feature: `presentation → domain ← data`. Presentation never imports `data`.
  `domain` imports no Android, Compose, Retrofit, Room or DataStore types.
- Mark types `internal` unless another module needs them. Public surface of a feature is its
  navigation entry point and whatever the app's DI must see.
- New code uses the feature layout even when older code in the repository is layer-based
  (`viewmodels/`, `repository/`). Do not extend the legacy layout; do not move it either.

## Compose

- New screens are Jetpack Compose. When touching a legacy View/XML or MVP screen, change only
  what the task needs; extract business logic into a use case; never create a new Presenter or
  Contract.
- Split every screen into a **route** and **content**:

```kotlin
@Composable
internal fun ProfileRoute(
    onBack: () -> Unit,
    viewModel: ProfileViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    ProfileScreen(state = state, onAction = viewModel::onAction, onBack = onBack)
}

@Composable
internal fun ProfileScreen(
    state: ProfileUiState,
    onAction: (ProfileAction) -> Unit,
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
) { /* stateless rendering only */ }
```

- Content composables are stateless: they take state and callbacks, take a `modifier`
  parameter first among optional parameters, and apply it to the root.
- Collect flows with `collectAsStateWithLifecycle()`, never plain `collectAsState()` in app code.
- Hoist state; keep only UI-local state (focus, scroll, animation, text field draft when the
  repository does so) in `remember`/`rememberSaveable`.
- Use stable keys in lazy lists: `items(items, key = { it.id })`.
- Never perform IO, start coroutines for business work, or read singletons from a composable.
  Side effects go through `LaunchedEffect` keyed on the value that should restart them.
- Tag interactive elements for UI tests (`Modifier.testTag("login-submit")`, and
  `testTagsAsResourceId = true` at the root when Maestro/UiAutomator need resource ids).
- Accessibility: every icon-only control has a `contentDescription` from resources; decorative
  images use `null`; touch targets are at least 48dp; text scales with `sp`.

### Previews are part of the screen

Every created or modified screen gets a runnable `@Preview` **in the same file**, using
deterministic synthetic state and no-op callbacks. Preview the content composable, never the
route (no ViewModel, DI graph or navigation controller in previews). Cover the meaningful states
— loading, empty, content, error, and disabled/locked where they exist — plus a large font scale
and a long-text or second locale when layout is sensitive. Use the app's theme wrapper.

```kotlin
@Preview(name = "Content")
@Preview(name = "Large font", fontScale = 1.5f)
@Composable
private fun ProfileScreenContentPreview() {
    AppTheme { ProfileScreen(state = ProfileUiState(name = "Alex Doe"), onAction = {}, onBack = {}) }
}
```

Compiling the preview proves it compiles; only rendering it (IDE or screenshot tool) proves it
renders. Report which one you did.

## State management

Use the repository's pattern. When it is MVI (or unspecified for new work), follow the
[MVI contract](../../references/mvi.md) and `implement-mvi-feature`:

- `UiState` is an immutable `data class` with defaults; collections are `List`/`Map`, not
  mutable types; derived values are computed properties or computed in the reducer.
- `Action` and `Result` are `sealed interface`s.
- The ViewModel exposes `val uiState: StateFlow<UiState>` and `fun onAction(action)`.
  Nothing else is public.
- Durable outcomes (navigation after success, permission or credential prompts, approvals) are
  pending requests in state with an ID, acknowledged by an action — not zero-replay
  `SharedFlow` events that are lost when no collector is active.

When the repository uses MVVM with `StateFlow` + side-effect `SharedFlow`/`Channel`, keep it:
update state with `_uiState.update { it.copy(...) }`, never `_uiState.value = _uiState.value.copy`.

## Domain layer

Use cases are single-purpose and invoked as functions:

```kotlin
class GetProfileUseCase @Inject constructor(
    private val repository: ProfileRepository,
) {
    suspend operator fun invoke(userId: UserId): Profile = repository.profile(userId)
}
```

- Repository interfaces (ports) live in `domain`; implementations live in `data`.
- Data and domain APIs are `suspend fun` for one-shot work and `Flow<T>` for observed data —
  never callbacks, never RxJava types in new code, never `LiveData` below the UI layer.
- Domain models are plain Kotlin. Map DTO/entity ↔ domain in `data/mapper`; never pass a DTO
  or Room entity to presentation.
- Wrap primitive identifiers in value classes where the repository does
  (`@JvmInline value class UserId(val value: String)`).

## Dependency injection (Hilt)

```kotlin
@HiltViewModel
internal class ProfileViewModel @Inject constructor(
    private val getProfile: GetProfileUseCase,
    private val savedStateHandle: SavedStateHandle,
) : ViewModel()

@Module
@InstallIn(SingletonComponent::class)
internal abstract class ProfileDataModule {
    @Binds abstract fun bindProfileRepository(impl: DefaultProfileRepository): ProfileRepository
}
```

- Constructor injection always. No service locator, no `EntryPointAccessors` in business code.
- Resolve ViewModels in composables with `hiltViewModel()`.
- Scope deliberately: `@Singleton` only for real shared state (repositories with caches,
  clients); unscoped by default.
- Each feature owns the DI module for its own bindings; the app owns configuration
  (base URLs, BuildConfig values, SDK keys).

## Coroutines and Flow

- Inject dispatchers through qualifiers (`@IoDispatcher`, `@DefaultDispatcher` or the
  repository's equivalent). Never reference `Dispatchers.IO`/`Main` directly in classes you
  test.
- Launch from `viewModelScope` or an injected application scope. Never `GlobalScope`, never
  `runBlocking` outside tests and `main`.
- Switch threads with `withContext(ioDispatcher)` inside the suspending function that needs it;
  main-safety belongs to the data layer.
- Never swallow `CancellationException`. A broad `catch (e: Exception)` or `runCatching` must
  rethrow it:

```kotlin
suspend fun <T> runSuspendCatching(block: suspend () -> T): Result<T> = try {
    Result.success(block())
} catch (e: CancellationException) {
    throw e
} catch (e: Exception) {
    Result.failure(e)
}
```

- Use `stateIn(scope, SharingStarted.WhileSubscribed(5_000), initial)` (or the repository's
  policy) for derived screen state; choose the policy deliberately.
- Cold flows from repositories; hot flows only where state is genuinely shared.
- Never mix RxJava and coroutines in one call chain; bridge at a boundary if legacy code forces it.

## Error handling

- Map known failures to typed domain errors in `data` (network unavailable, unauthorized,
  not found, validation) and to UI error models in presentation. Never show `exception.message`.
- Keep current content when a refresh fails if the product expects it; show the error beside it.
- Log unexpected failures once, at the boundary that handles them, with the repository's logger
  (Timber or equivalent). Never `println` or `android.util.Log` in committed code.
- Never swallow an exception silently; an intentional ignore gets a one-line comment saying why.

## Design system, resources and localization

- Use the design-system module's components and theme tokens (colors, typography, spacing,
  shapes). No hard-coded colors, font sizes or dp values in feature UI except one-off layout
  measurements the design specifies.
- Feature-specific strings, icons and illustrations stay in the feature module, even when
  rendered through a shared component.
- Every user-visible string comes from resources, with every bundled locale updated in the same
  change. Plurals use `pluralStringResource`. Format arguments, never concatenation.
- Import design SVGs as VectorDrawable in the owning module. Use WebP only for true bitmaps
  (photos, 3D renders). Do not redraw or rasterize vectors.

## Persistence and network

- Room: DAOs return `suspend` for one-shot and `Flow` for observed queries. Every schema change
  has a migration and a migration test; exported schema JSON is committed and never hand-edited.
- DataStore over SharedPreferences for new key-value storage.
- Retrofit/Ktor services and DTOs stay in `data/remote`; serialization annotations never reach
  domain models.
- Secrets (tokens, keys, seeds) live in encrypted or Keystore-backed storage, never in UI state,
  `SavedStateHandle`, navigation arguments, logs, analytics or test fixtures.

## Kotlin style

- Explicit imports with short names in code; no fully qualified names in declarations or
  expressions; no wildcard imports; alias imports on conflicts.
- Prefer `val`, immutable collections, expression bodies for one-liners, `when` over `if` chains
  on sealed types (exhaustive, no `else` on sealed hierarchies).
- No `!!` on values that can be null at runtime; handle the null case.
- Comments explain *why*, not what. No ticket IDs in comments — they belong in commits and MRs.
- Run the repository's formatter/linter (`./gradlew spotlessApply`, `ktlintFormat`, `detekt`)
  before committing; never commit with new warnings.

## Build and dependencies

- Use existing convention plugins and the version catalog. Do not add a dependency for a few
  lines, upgrade pinned versions, add a framework, or split modules without a task requirement.
- Generated code (Room schemas, protobuf/gRPC, Apollo, `R`, BuildConfig, KSP output): change the
  source and regenerate; never edit the output.

## Verification

Build the affected variant, run the affected modules' unit tests, and run the repository's
static checks. Assembling the app verifies the DI graph and resource merging across modules; a
module's own tests do not. Report commands and actual results; never claim an unrun check passed.
For tests, load `writing-tests`.
