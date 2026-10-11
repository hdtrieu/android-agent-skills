---
name: local-review
description: Review a local Android diff (staged, unstaged and untracked) for behavioral defects, module/layer boundaries and state/lifecycle regressions with source-grounded findings, before opening an MR.
---

# Review a local diff

Read the target repository's instructions and `android-conventions`. Get the full
change: `git status --short`, then `git diff HEAD` (staged and unstaged), then read
each untracked file in full. If all are empty, diff against the branch base
(`GIT_BASE_BRANCH` or the repository's documented base). Never review a diff you
could not read. Do not assume every change belongs to the agent.

Review only what the diff changes. A pre-existing problem is a finding only when
the diff makes it materially worse; label it `pre-existing`.

Follow changed call sites far enough to establish observable consequences. Check
domain/data boundaries, cancellation and stale responses, state ownership,
navigation/prompt lifecycle, secret handling, missing previews and changed
acceptance behavior. Apply the [MVI](../../references/mvi.md) contract when the
project uses it: typed actions/results, immutable state, pure reducer and
generation guards. Load `writing-tests` when logic changed, to judge coverage.

Report each finding with severity, file:line, trigger, consequence and suggested
correction. Separate demonstrated defects from questions. Do not claim module
boundaries are compiler-enforced. Every finding needs a concrete failing behavior
or a documented project rule, not a style preference alone.

A review request produces findings; modify code only if fixes were requested.
