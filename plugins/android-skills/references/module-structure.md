# Android module structure

Default layout for multi-module Android apps, adapted from
[Now in Android](https://github.com/android/nowinandroid). The target project's
`settings.gradle.kts`, `ARCHITECTURE.md`/ADRs and agent instructions win. If the
project is a single module or uses another layout, keep its layout unless the task
is the migration.

## Module graph and rules

```text
:app                 → :feature:*, :core:*, :core:designsystem
:feature:<name>      → :core:* it actually uses, design system
:core:<name>         → other :core:* only
:core:designsystem   → no project modules
```

1. `:app` is the composition root. Nothing depends on `:app`.
2. A feature depends only on the design system and the core modules it uses.
   Features never depend on each other.
3. Core modules never depend on a feature or `:app`.
4. Use `implementation`, not `api`, unless a public signature exposes the other module's type.

Features do not navigate to each other directly. A feature exposes a route
composable with outcome callbacks; the app maps outcomes to its own root
destinations. Introduce NiA's `feature/<name>/api` + `impl` split only when a
ticket needs one feature to open another's screen, and record it in an ADR first.

## Module types

| Module | Owns | Never contains |
| --- | --- | --- |
| `:app` | `Application`, `MainActivity`, root navigation, per-feature entry installers, DI configuration, launch theme, BuildConfig | Screens, ViewModels, repositories, business rules |
| `:feature:<name>` | One user journey: domain, data, presentation, route entry points, its DI bindings, strings/drawables, previews and tests | Root navigation keys, another feature's types, app-shell assets |
| `:core:<name>` | Infrastructure or contracts with a semantic owner and two or more real consumers | Feature UI, product strings, feature business rules |
| design system | Primitives, theme, tokens, fonts, generic icons and their previews/tests | Feature screens, product copy, feature icons/illustrations |

## Package layout inside a feature module

```text
feature/<name>/src/main/kotlin/<namespace>/feature/<name>/
├── navigation/        Public route composables / flow entry contracts for the host
├── presentation/
│   ├── ui/            Stateless screens + their @Preview and preview fixtures
│   ├── component/     UI used only by this feature
│   ├── state/         Action/UiState/Result + pure Reducer, UI errors
│   └── viewmodel/     <Screen>ViewModel
├── domain/
│   ├── entity/        Pure Kotlin models
│   ├── repository/    Repository interfaces (ports)
│   └── usecase/       One business action each
└── data/
    ├── repository/    Repository implementations
    ├── local/ remote/ Data sources, DB/DTO models
    ├── mapper/        DTO/DB ↔ entity mapping
    └── di/            DI bindings for this feature
```

- `domain` imports no Android, Compose, Retrofit, DataStore or `data`/`presentation` packages.
- `presentation` never imports `data`. ViewModels call use cases or domain contracts.
- `navigation` may import `presentation` but nothing in `data`.
- Mark types `internal` unless another module needs them.
- Create a package only when it has content; no `.gitkeep` scaffolds.

## Where does it go?

| Adding… | Location |
| --- | --- |
| Screen, ViewModel, reducer for journey X | `:feature:x` presentation packages |
| A new user journey | New `:feature:<name>` module |
| Repository/use case used only by X | `:feature:x` domain/data |
| Contract needed by two features | Owning `:core:*` module |
| Generic button/field/icon/token | Design system module |
| Feature icon, illustration, copy, a11y label | That feature's `res/` |
| New root destination or startup routing | App navigation |
| Base URL, BuildConfig, SDK initialization | App DI / `Application` |

Move code to `:core:*` only when it has a semantic owner and two real consumers.
Never create `utils`, `helpers`, `common` or `shared` dumping-ground modules.

## Adding a feature module

Only when the ticket scopes a new journey or the user asks for it:

1. Include it in `settings.gradle.kts`; apply the project's convention plugins and namespace.
2. Depend only on the design system and needed core modules; versions from the catalog.
3. Expose a route in `navigation/` and wire it from the app.
4. Add strings for every bundled locale and drawables as VectorDrawable.
5. Add tests in the module and a `@Preview` in each screen file.
6. Add a module README and an ADR when the module graph or an ownership rule changes.

## Verification

Discover tasks from the build (`./gradlew tasks`). Typically: assemble the app
debug variant (it verifies DI graph and resource merging across modules), the
affected modules' unit tests, and the project's lint/format/static-analysis tasks.
A module's own tests do not verify app-level wiring.
