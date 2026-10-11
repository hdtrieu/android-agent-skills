---
name: local-review
description: Review an uncommitted or unpushed Android diff in a loop until it is clean - delegate to the read-only android-code-reviewer agent, fix what it ranks P0/P1, check the diff against the ticket's QA test cases, re-review, and keep a per-branch decision ledger so a deliberately accepted finding is not re-litigated every round. Use when asked to review local changes, check a diff before pushing, "review this before I open an MR", or whether a ticket's test cases are covered. This is the pre-MR gate; mr-review owns the loop after an MR exists.
---

# Local review loop

The cheap gate: every P0/P1 fixed here costs no MR review round. This skill owns the **local**
loop before a push. Once an MR exists, `mr-review` owns it.

A request for *a review* produces findings only. Run the fix loop (Steps 4–5) only when the user
asked you to fix, or the review is part of an implementation you were asked to finish.

Skip the gate only for a diff with no logic in it (version bump, docs, generated files) — and say
so in the MR description.

## Step 1 — Find the change and open the ledger

```sh
git status --short
git diff HEAD --stat
BRANCH=$(git branch --show-current)
LEDGER="$(git rev-parse --git-dir)/android-review-$(printf %s "$BRANCH" | tr '/' '-').md"
```

Untracked files are part of the change; read them in full. If the working tree is clean, the
change is committed: compare against the base (`git diff <base>...HEAD`, base from the user,
`GIT_TARGET_BRANCH`, the MR target, or the remote default branch).

**Why a ledger.** Each review round is a fresh agent with no memory. Without the ledger, a
finding you decided not to fix comes back every round. It lives inside the Git directory, so it
never lands in the repository and needs no ignore entry. `--git-dir` resolves per worktree, and
the branch is in the name, so last week's decisions do not leak onto an unrelated branch.

## Step 2 — Pick up the ticket's test cases

If the branch name contains a ticket key, QA's test cases may be on the ticket and they are the
acceptance criteria for this change:

```sh
TICKET=$(git branch --show-current | grep -oE '[A-Z][A-Z0-9]+-[0-9]+' | head -1)
python3 <plugin-root>/scripts/integrations.py jira issue "$TICKET" --comments 50
```

Use a large comment window: the command returns the N *most recent* comments, and test cases are
usually posted early and buried under discussion. No ticket, no Jira access, or no test cases is
a normal answer — say which one and carry on; never invent cases.

Test cases usually arrive as a table (`#`, `Type`, `Priority`, `Scenario`, `Steps`, `Expected`).
`Type` decides what the diff can show: a `Unit` case should be visible as a test; an
`Upgrade`/`Manual` case cannot be proven from code. A heading marked draft or AI-generated is
intent, not QA sign-off — weigh it as such.

## Step 3 — Review

Delegate to the **`android-code-reviewer`** agent when the host supports subagents; otherwise
apply its checklist yourself in the same order. Pass the ledger and test cases:

```
Review the diff in <checkout>. Base for committed work: <base>.
Prior review decisions on this branch are in <LEDGER> — read it first; do not re-raise an
entry there unless the diff has made it materially worse, and then label it `re-raised`.

The ticket's QA test cases are below. Report, separately from code findings, every case the
diff does not visibly satisfy — by number, not a count. Judge only what the diff shows; a case
that needs server state or a device cannot be confirmed from code, so say that.

<TEST CASES or "none">
```

Keep the two answers apart. A missing test case is unfinished work, not a code defect: write the
test, or state that the case is not coverable from code.

The agent reports; it never edits. Fixing is yours.

## Step 4 — Triage every finding

Each finding gets exactly one outcome:

| Outcome | When | What you do |
| --- | --- | --- |
| **Fix** | Default for P0 and P1 | Change the code; add the red test first when it is a logic defect |
| **Accept** | Real but out of scope, or cost outweighs value | Append to the ledger with the reason |
| **Reject** | The finding is wrong | Append to the ledger saying *why it is wrong* |

P2 is your call — fix the cheap ones, ledger the rest. **A P0 is never accepted on your own
authority**; ask the user.

Ledger entry format — severity, location, title, decision and reason:

```
P1 feature/profile/.../ProfileViewModel.kt:88 — state copied from pre-suspend snapshot
   accepted: screen is being replaced in ABC-412; fixing here doubles the diff. In MR description.

P2 feature/profile/.../ProfileScreen.kt:140 — hard-coded 12.dp
   rejected: value is inside a @Preview wrapper, which the token rule does not govern.
```

Never delete an entry to make a round look clean. Remove one only when the finding is genuinely
fixed in the same round.

## Step 5 — Verify, then re-review

After fixes, run the checks the change needs (module unit tests, the app build when wiring or
resources changed, lint/format), then run Step 3 again. Fixes are new code and get reviewed.

**Stop** when:

- a round returns no P0 and no P1 — done;
- the only findings left are ledger entries the agent honored;
- **the same finding survives two fix attempts** — stop and bring it to the user; a third round
  will not fix a misunderstanding;
- a fix needs a change outside the diff's scope — ledger it and say so.

More than three rounds usually means the diff is too big. Say so instead of grinding.

## Step 6 — Report

State the verdict, the number of rounds, the checks run with results, and **read the ledger
out**. Anything still in it goes in the MR description so the human reviewer sees the same call.

Report test-case coverage separately and by name:

```
Clean after 2 rounds. Checks: :feature:profile:testDebugUnitTest ✔, :app:assembleDebug ✔, detekt ✔.
Accepted (in MR description):
  P1 ProfileViewModel.kt:88 — pre-suspend snapshot, deferred to ABC-412

Test cases (ABC-123): 4 of 5 covered
  TC5 — not covered: needs a server account with no profile; manual step for QA
```

## Limits

Advisory, not a guarantee: it reviews only what the diff changes and is no substitute for human
review or CI. A clean round means the rules hold, not that the change is correct.
