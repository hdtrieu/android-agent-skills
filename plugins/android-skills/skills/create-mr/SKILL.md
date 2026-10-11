---
name: create-mr
description: Prepare, push and open a GitLab merge request (or GitHub pull request) with the project's branch naming, Conventional Commits and review/CI gates. Use for MR creation or preparation, not for merging or deployment.
---

# Create an MR

Read [Git conventions](references/git-conventions.md) and the target repository's
instructions. For GitLab access read [integrations](../../references/integrations.md).
A request for conventions, a plan or a description does not authorize pushing.

## Resolve purpose and branches

Identify the repository, remote project (`GITLAB_PROJECT` or the origin remote),
ticket (if any), source branch, intended environment and target branch
(`GIT_TARGET_BRANCH`, repository rules, or the user). Inspect status and preserve
unrelated edits. Do not default to the remote's `main`/`master` when the project
documents another target. If the target is missing, report it and ask.

## Prepare a reviewable change

Run `local-review` on the scoped diff and the repository's relevant checks; use
its harness instead of inventing a pipeline. Commit only the intended files using
the resolved commit convention. Do not invent a ticket key.

Write the description to a file from the [template](assets/mr-description.md).
Fill only relevant sections: change, ticket link, source/target and purpose,
tested commit, checks actually run, CI and review status, deployment impact.

## Publish only the requested MR

When publishing is requested, push the source branch, then check for an existing
open MR with the same source/target and reuse it rather than duplicating.

Create the MR with, in order of preference:

1. A connected GitLab tool or authenticated `glab mr create --source-branch ... --target-branch ... --title ... --description "$(cat FILE)"`
   (for GitHub repositories, `gh pr create --base ... --head ... --title ... --body-file FILE`).
2. The REST fallback: write a JSON file with `source_branch`, `target_branch`,
   `title`, `description` (read from the description file), run `doctor`, then
   `python3 <plugin-root>/scripts/integrations.py request gitlab POST projects/<id-or-encoded-path>/merge_requests --body-file MR_JSON --write`.

Never interpolate description text into shell code. If the write times out, list
existing MRs before retrying.

Fetch the created MR and confirm URL, source, target, state, draft, conflicts and
pipeline status. Do not trigger review bots, approve, auto-merge, resolve others'
discussions or deploy as a side effect.

Report the URL (or the prepared description), source/target, checks actually run,
pending review/CI and any deviation from the conventions.
