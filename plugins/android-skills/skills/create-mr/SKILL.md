---
name: create-mr
description: Commit, push and open a GitLab merge request (or GitHub pull request) the right way - resolve the project and target branch, run the local review gate, commit with the project's convention, write a truthful description from the template, create the MR, verify it, and hand over to mr-review. Use whenever the user asks to create/open/raise an MR or PR, "push this and open an MR", or "put this up for review". Works with or without a ticket. Not for merging or deploying.
---

# Create an MR

Read [Git conventions](references/git-conventions.md) and the repository's instructions
(`CLAUDE.md`, `CONTRIBUTING.md`, `.gitlab/merge_request_templates/`, commit hooks). A request
for conventions, a plan or a description does **not** authorize pushing; a request to create or
publish the MR does, together with the scoped commit and push it needs.

## Step 1 — Resolve repository, project and target

```sh
git remote get-url origin                         # host and project path
git branch --show-current
python3 <plugin-root>/scripts/integrations.py gitlab project <group/project>   # id + default_branch
```

- **Project**: the user's value, `GITLAB_PROJECT`, or the origin remote path.
- **Target**: the user's value, repository rules, `GIT_TARGET_BRANCH`, then the project's
  `default_branch` — in that order. Integration (`merge/*`), release (`release/*`) and
  environment branches are chosen by purpose; confirm with the user when the work belongs on
  one of them, because retargeting later is noisy.
- If the target does not exist on the remote, stop and ask for the mapping.
- For a GitHub remote, use `gh` with the same discipline (Step 5 alternative).

## Step 2 — Get the branch ready

- **Never commit on the target branch.** If you are on it, create the branch first
  (`jira-ticket` Step 4 or the conventions file).
- Inspect what you will commit: `git status --porcelain` and `git diff --cached --name-only`.
  Never stage build output, `.env` files, credentials, keystores, local review notes, IDE
  files or scratch files. Stage files by name, not with `git add -A`, when unrelated changes
  exist.
- **Run the `local-review` gate** on the diff and resolve P0/P1. Carry anything left in its
  ledger into the description. Skip it only for a diff without logic (version bump, docs,
  generated files) and say so.
- Run the checks the change needs and record the actual results: affected module tests, the app
  build when wiring/resources changed, lint/format/static analysis. If lint has pre-existing
  findings, record the count on your branch **and** on the target so a reviewer can see you
  added none.
- Commit with the resolved convention, default Conventional Commits:
  `feat(profile): ABC-123 add avatar upload`. Explain *why* in the body when it is not obvious.
  Follow the user's own rules about attribution trailers.

```sh
git push -u origin <branch>
```

## Step 3 — Check for an existing MR

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr list --source <branch> --target <target>
```

If one is open, update it (push) and report it instead of creating a duplicate.

## Step 4 — Write the description to a file

Start from the [template](assets/mr-description.md) or the repository's own MR template. Fill
every section from what was actually done; delete sections that do not apply. **No placeholder
text left behind.**

The description is a set of claims. Only state what is true:

- **Checks**: commands and real results. Not run → say "not run" and why.
- **CI**: link and status, or "pending" — never "passed" before it has.
- **Tests**: what was added; ticket test cases by number with what covers each.
- **E2E**: never claim green flows that were not run or that failed; if a flow fails identically
  on the target, say so and note `needs flow-data refresh: <flow>`; if the path has no flow,
  note `needs E2E: <scenario>`.
- **UI changes**: screenshots or preview captures, before and after.
- **Accepted findings** from the local-review ledger.
- **Deployment impact** when the target is an environment branch.

## Step 5 — Create the MR

Preferred: a connected GitLab tool or `glab`:

```sh
glab mr create --source-branch <branch> --target-branch <target> \
  --title "<title>" --description "$(cat mr.md)" [--draft]
```

Fallback, the bundled CLI (one call, write-guarded):

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr create \
  --project <group/project> --source <branch> --target <target> \
  --title "<title>" --description-file mr.md [--draft] [--label <label>] \
  [--squash | --no-squash] [--remove-source-branch | --no-remove-source-branch] --write
```

- **Title**: repository convention; default `type(scope): ABC-123 short summary`, or without the
  key when there is no ticket.
- Squash and source-branch deletion follow project policy; omit the flags to keep the project's
  defaults. Keep reusable `merge/*` and `release/*` branches.
- Use `--draft` when checks are pending or the user wants early feedback.
- Never interpolate description text into shell code; pass it as a file.
- If the create call times out, run `gitlab mr list --source <branch>` before retrying.

GitHub: `gh pr create --base <target> --head <branch> --title "<title>" --body-file mr.md [--draft]`.

## Step 6 — Verify what you created

```sh
python3 <plugin-root>/scripts/integrations.py gitlab mr get <mr-url-or-iid>
```

Confirm `state: opened`, the right source and target, draft status as intended,
`has_conflicts: false`, and the pipeline status. Report the URL.

## Step 7 — Hand over

Opening the MR is not the end of the job when the user asked you to see it through: continue
with `mr-review` once review comments or pipeline results arrive. Never approve, merge, enable
auto-merge, trigger deployments, resolve other people's threads, or re-request review bots as a
side effect of opening an MR.

## Report

MR URL, source → target, title, draft state, checks run with results, pipeline status, any
unticked claim and why, accepted findings carried into the description, and what happens next.
