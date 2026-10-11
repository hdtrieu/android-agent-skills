---
name: root-cause-analysis
description: Diagnose an Android defect (crash, ANR, wrong state, race, lifecycle or restoration bug, data corruption) from evidence - reproduce, trace the flow, separate facts from hypotheses, prove the cause with a failing test, fix it once at the root - and write the RCA with one primary root cause, the fix and version, and one matched prevention action. Use for bug investigation, "why does this happen", "root cause", "RCA", or an incident/escalation ticket.
---

# Root cause analysis

Two outputs, often both: a **diagnosis and fix** in code, and a **written RCA** for the ticket.
The fix is only as good as the evidence; the RCA is only worth writing if it comes from the code.

## Step 1 — Establish the facts

Fetch the ticket when there is one (`jira-ticket`, `jira issue <KEY> --comments 50`) and write
down:

- **Expected vs observed** behavior, in one line each.
- **Where**: app version and build variant, Android version, device/OEM, locale, account type,
  network state, first occurrence.
- **Frequency**: always, intermittent, after an upgrade, only after process death, only on
  rotation/foldable, only under load.
- **Evidence available**: stack trace, logcat, ANR trace, crash-reporting issue, screenshot or
  video, server logs, payload.

Treat the reporter's theory as a hypothesis. Investigations often carry a plausible but wrong
premise ("only these records") — check it.

## Step 2 — Gather evidence on Android

Use what the situation allows; do not install tools without asking.

```sh
adb logcat -v threadtime -b crash,main,system | tee logcat.txt   # reproduce while capturing
adb logcat -d -b crash                                           # last crashes
adb bugreport bugreport.zip                                      # ANR traces, tombstones, system state
adb shell dumpsys activity <package>                             # activities, back stack, process state
adb shell am kill <package>                                      # simulate process death in background
adb shell cmd uimode night yes|no ; adb shell wm size / wm density   # configuration changes
```

- **Crash**: read the full cause chain (`Caused by:`) and the first frame in app code.
- **ANR**: main-thread stack in `/data/anr` traces from the bug report — look for IO, locks,
  `runBlocking`, binder calls or heavy composition on main.
- **Wrong state / race**: log state transitions with request IDs temporarily, or reproduce in a
  ViewModel test with a controlled scheduler.
- **Restoration**: rotate, toggle dark mode, change font scale, and use *Don't keep activities*
  or `am kill` for process death — they are different seams.
- **Release-only**: suspect R8/ProGuard rules (`r8-analyzer`), missing `@Keep`/serialization
  rules, or debug-only code paths.
- **Upgrade-only**: suspect Room/DataStore migrations and persisted shapes written by older
  versions.

## Step 3 — Trace the flow

Follow the data through the layers and note where the observed value first goes wrong:

```
UI event → Action → ViewModel → use case → repository → data source / platform adapter
          ← Result ← reducer/state ← mapper ← DTO / entity ← network / storage
```

For timing defects check: request/generation IDs, cancellation (`CancellationException`
swallowed by `runCatching`?), collector lifecycle (`collectAsStateWithLifecycle`,
`repeatOnLifecycle`), state derived from a snapshot taken before a suspend call, navigation
ownership, and what survives configuration change vs process death.

Use `git log -S '<symbol>'`, `git log -L :<function>:<file>` and `git blame` to find the change
that introduced the behavior, and read *why* the old code was the way it was.

## Step 4 — Separate facts from hypotheses

Keep a short list: **observed facts** (with the evidence for each) and **hypotheses** (with what
would confirm or rule each out). Gather the smallest piece of evidence that distinguishes them.
Never present a hypothesis as the cause.

## Step 5 — Prove it with a failing test

Reproduce at the lowest layer that can show it (`writing-tests` §2): reducer, ViewModel with a
controlled scheduler, mapper with the real payload shape, repository with real storage, or an
instrumented test when the platform is the seam. Confirm it fails **for the expected reason**.
If no automated reproduction is feasible, record the manual reproduction steps and why.

## Step 6 — Fix once, at the root

- Fix the demonstrated cause in the shared code, not the symptom at one call site.
- Grep every caller and sibling copy of the code you change; a bug fixed in one of three
  copy-pasted paths is still shipping in two.
- Keep the change scoped. Do not rewrite the architecture because a defect exists; note larger
  issues as follow-ups.
- Preserve error handling and validation in code you touch.
- Watch the failing test pass; run the module suite.

## Step 7 — Write the RCA

Pick **one primary root cause**, top-down — the highest one that applies wins:

1. **New behavior / specification gap** — an undefined case surfaced; expected behavior was never
   decided.
2. **Architectural gap** — structural, ownership, cross-service or consistency issue.
3. **Implementation defect** — the design was sound; the code had wrong logic, an unsafe
   assumption or a known pitfall.
4. **Missing coverage** — everything above was fine, but a realistic case was not tested.

If the destination (a ticket field or template) offers its own vocabulary, map onto it and
pick exactly one. When it also asks *why it escaped* (test gap, review gap, staging gap,
monitoring gap), put the origin in the root cause and the testing gap in the escape — do not
spend the root-cause slot on "no test".

**Prevention** — one action, matched to the cause:

| Root cause | Prevention |
| --- | --- |
| Specification gap | Write/update the product spec or acceptance criteria |
| Architectural gap | An ADR/technical decision record if this fix did not fully resolve it |
| Implementation defect | Update a guideline, lint rule or review checklist |
| Missing coverage | The specific unit/integration/E2E test that now exists |

Link a real artifact; never invent a URL.

Format:

```
**Primary root cause:** <one category>

**Cause:** <why the system behaved this way — concrete, 1–3 sentences, citing the commit, line or payload>

**Fix:** <the change that shipped> — available in <version / build>, <platform>.

**Not covered by the fix:** <records or cases not verified, known remaining gaps — or "none known">

**Prevention:** <one durable action> — <link>
```

Post it only where and when the user asks (ticket field or comment via
`jira comment <KEY> --body-file rca.txt --write`). Never change the ticket's status or assignee.

## Report

Cause and evidence, the failing-then-passing test, files changed, checks run with results,
remaining uncertainty, and the RCA text. Never include credentials, tokens or sensitive payloads
in diagnostic output; redact identifiers from logs you quote.
