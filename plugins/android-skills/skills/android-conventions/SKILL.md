---
name: android-conventions
description: Apply Kotlin, Jetpack Compose, Hilt, Coroutines and Clean Architecture layer conventions when writing or reviewing Android app code.
---

# Android conventions

Read the target repository's agent instructions, README/ARCHITECTURE and
[module structure](../../references/module-structure.md) first; the repository wins
over this skill. Resolve documentation drift using current source. For presentation
work read [MVI](../../references/mvi.md) and `implement-mvi-feature` when the
project uses MVI; otherwise follow its existing pattern.

- Preserve module direction (app → feature → core/design system; never feature → feature)
  and layer direction inside a module (presentation → domain ← data). Presentation
  calls use cases/domain contracts; repositories hide DTO, persistence and SDK details.
- Keep domain logic independent of Android/UI/Retrofit. Match the existing DI
  conventions rather than introducing another abstraction.
- Use constructor injection; no service locator, Activity/Context in ViewModel,
  or framework navigator in business logic.
- Compose screens render state and emit typed actions. Keep platform work in hosts.
  Every created or modified screen gets a `@Preview` with deterministic state.
- Use injected dispatchers and Coroutines/Flow; preserve cancellation.
- Use explicit imports and short names; no fully qualified names in code and no
  wildcard imports. Use an alias import when names conflict.
- Reuse the project's design-system components, theme tokens and localization APIs
  instead of hard-coded colors, fonts, spacing or strings.
- Keep secrets out of UI state, saved state, routes and logs.
- Use the existing convention plugins and version catalog. Do not split modules,
  upgrade dependencies or add a framework without a concrete task requirement.
- Import design SVGs as VectorDrawable in the owning module; use raster only for real bitmaps.

For tests load `writing-tests`; for Jira/GitLab/Figma load `project-integrations`.
