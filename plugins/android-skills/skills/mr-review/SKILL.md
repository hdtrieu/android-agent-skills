---
name: mr-review
description: Resolve review comments on an open GitLab merge request in a loop - fetch every unresolved thread with file:line, triage and plan all of them first, apply fixes, build and test, reply in each thread with what changed (or why not), resolve only what is fixed, push, and repeat until no actionable thread is left and the pipeline is green. Use when the user shares an MR URL and asks to address, fix or resolve review comments, or after create-mr when review feedback arrives.
---

# MR review loop

Owns the loop **after** an MR exists. Before a push, `local-review` owns it.

Replying, resolving threads and pushing are external writes. Do them when the user asked you to
address the review; otherwise produce the triage plan only.

## Step 1 — Parse the MR

Accept an MR URL (`https://host/group/project/-/merge_requests/42`), `<project> <iid>`, or an iid
with `GITLAB_PROJECT` set.

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr get <mr>
```

Confirm it is open, note source/target, head `sha`, draft state, conflicts and pipeline status.
Make sure the local checkout is on the MR's source branch and up to date:

```sh
git fetch origin <source> && git switch <source> && git status -sb
```

If the local branch has diverged from the remote, stop and ask; never force-push over someone
else's commits.

## Step 2 — Fetch every open thread

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr discussions <mr> --unresolved
python3 <plugin-root>/scripts/integrations.py gitlab mr pipelines <mr>
```

Each thread has an id, resolvable/resolved state, and notes with author, `file:line` location and
body. Read the whole thread — later replies often narrow or withdraw the original request. Also
read failed pipeline jobs: a red pipeline is review feedback too.

## Step 3 — Triage and plan all comments first

Read every thread before changing anything; fixes often interact. Classify each:

| Class | Meaning | Action |
| --- | --- | --- |
| **Fix** | Correct and in scope | Change the code (red test first for logic defects) |
| **Clarify** | Ambiguous, or you need the reviewer's decision | Reply with a specific question; leave unresolved |
| **Decline** | Wrong, or out of scope | Reply with the reason and evidence (code, spec, test); leave it for the reviewer to resolve |
| **Already done** | Fixed by another change in this round or earlier | Reply with the commit SHA and resolve |
| **Not actionable** | Praise, FYI, bot noise | No change; resolve only if it is yours to resolve |

Verify each claim against the code before accepting it — reviewers can be wrong, and bots more
often. Present the plan to the user when it includes a decline of a human reviewer's request or
a change outside the MR's scope.

## Step 4 — Apply the fixes

- One logical fix per thread where practical, so replies can point to a commit.
- Follow the same conventions as the original change (`android-conventions`, MVI, previews,
  strings in every locale, tests at the owning layer).
- Do not widen scope. A good idea outside the MR becomes a follow-up ticket suggestion in the reply.

## Step 5 — Build and test

Run what the fixes touch: module unit tests, the app build for wiring/resource changes, lint and
format, and E2E flows when the repository has a harness and the fix touches a flow. If a check
fails, fix it before replying. Never reply "fixed" to a thread whose fix is not verified.

## Step 6 — Commit and push

```sh
git add <files>
git commit -m "fix(profile): ABC-123 address review — keep content on refresh failure"
git push
```

Push before replying so the reply can cite a commit that the reviewer can open. Never rewrite
published history on a shared MR unless the user and repository policy allow it.

## Step 7 — Reply in each thread, then resolve

Write each reply to a file and post it in its thread:

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr note <mr> --discussion <id> --body-file reply.md --write
python3 <plugin-root>/scripts/integrations.py gitlab mr resolve <mr> --discussion <id> --write
```

Reply format — short and verifiable:

```
Fixed in 1a2b3c4: the reducer now keeps `profile` on `LoadFailed`; added
`failure keeps existing content for retry` in ProfileReducerTest.
```

```
Not changing this: `ProfileUiState.error` is cleared by `LoadStarted` (ProfileReducer.kt:21),
so a retry already hides it — covered by `retry clears previous error`. Happy to revisit if I
misread the concern.
```

Resolution rules:

- Resolve threads you fixed and verified, and threads that are already done.
- **Leave clarifications and declines unresolved** for the reviewer, unless repository policy
  says the author resolves everything.
- Never resolve someone else's open question without answering it.

## Step 8 — Wait, then loop

Review feedback and pipelines take time. Check again when the user says new comments arrived, or
when the host can schedule a check-back, instead of polling in a tight loop:

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr discussions <mr> --unresolved
python3 <plugin-root>/scripts/integrations.py gitlab mr get <mr>
```

Repeat Steps 2–7 for new threads. If the same thread is reopened twice for the same issue, stop
and bring it to the user — you have misread it.

## Step 9 — Exit criteria and summary

Done when all hold:

- no unresolved thread is waiting on you (only clarifications/declines waiting on reviewers);
- the newest pipeline ran on the final commit and is green, or its failures are shown to be
  unrelated and reported;
- no merge conflicts.

Report per thread: class, what changed (commit SHA) or the reply given, resolved or waiting.
Then checks run, pipeline status, and anything that needs the reviewer or user. Never approve or
merge the MR yourself.
