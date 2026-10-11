# Now in Android reference

[Now in Android](https://github.com/android/nowinandroid) (NiA) is the reference
for architecture, data flow, Compose, testing and modularization. Read the relevant
source, not only its README. If a local clone exists, prefer it; otherwise browse
GitHub. Resolve documentation/source discrepancies through current source.

## Read before implementation

- [Architecture learning journey](https://github.com/android/nowinandroid/blob/main/docs/ArchitectureLearningJourney.md)
- [Modularization learning journey](https://github.com/android/nowinandroid/blob/main/docs/ModularizationLearningJourney.md)
- A feature `impl` module: its ViewModel, state-driven screen, entry provider and ViewModel tests.

## Patterns to follow

- UDF: repository data flows up into immutable UI state; user events flow down
  through ViewModel actions. Expose read-only `StateFlow`; collect with
  `collectAsStateWithLifecycle`. Choose `stateIn` sharing per feature instead of
  copying a timeout.
- Separate the route that obtains the ViewModel and handles platform work from
  Compose content that renders state and emits callbacks. Give every created or
  modified screen a `@Preview` with deterministic state and no-op callbacks.
- Repository contracts expose app models and reactive reads; suspend writes update
  the authoritative store. Hide DTOs and storage/network details.
- Constructor injection, injected dispatchers, structured concurrency and
  cancellation. Keep Context/Activity out of ViewModels and business logic.
- Shared theme and generic primitives belong in the design system; feature screens,
  copy and feature icons stay in the feature. Import SVG as VectorDrawable.
- Prefer realistic fakes for state and behavior tests. Existing project test
  libraries remain valid; no blanket migration is required.
- Use the project's convention plugins, version catalog and actual build variants,
  not NiA's demo/prod flavors or dependency versions.

NiA does not mandate reducers; the explicit [MVI contract](mvi.md) is an optional
convention layered on NiA's UDF. Do not add a generic MVI framework or base Store.
