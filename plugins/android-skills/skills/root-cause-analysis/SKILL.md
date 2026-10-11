---
name: root-cause-analysis
description: Diagnose a reported Android defect (crash, wrong state, race, lifecycle bug) using reproduction, state transitions and evidence before proposing a scoped fix.
---

# Diagnose an Android defect

Establish expected versus observed behavior, build/environment and reproduction
steps. Use `project-integrations` if the task references a ticket, design or log
source. Read the target repository's instructions.

Trace the flow through screen action, ViewModel, use case, repository and platform
adapter. For timing defects inspect request identity, cancellation, collector
lifecycle, navigation ownership and restoration. Separate observed facts from
hypotheses; gather the smallest missing evidence that distinguishes them.

Reproduce at the lowest practical layer using `writing-tests` when feasible and
confirm the test fails for the expected reason. Fix the demonstrated cause once,
in the shared code, within the authorized scope; check sibling callers. Do not
rewrite the architecture because a defect exists. Preserve user changes.

Report cause, evidence, changed behavior, verification and remaining uncertainty.
Never include credentials or sensitive auth payloads in diagnostic output.
