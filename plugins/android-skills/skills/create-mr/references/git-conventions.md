# Git conventions

Resolve conventions in this order, and report which source you used:

1. The user's explicit instruction for this task.
2. The repository's own rules: agent instructions (`CLAUDE.md`, `AGENTS.md`),
   `CONTRIBUTING.md`, MR templates, commit hooks, CI lint.
3. The user's environment: `GIT_BASE_BRANCH`, `GIT_TARGET_BRANCH`, `BRANCH_PATTERN`,
   `COMMIT_PATTERN` (see [integrations](../../../references/integrations.md)).
4. The defaults below.

## Default branches

| Purpose | Name | Base |
| --- | --- | --- |
| Ticket work (feature, ordinary bug) | `feature/<KEY>-<short-hyphenated-summary>` | `GIT_BASE_BRANCH`, else the remote default branch |
| Integration of several features | `merge/<purpose>` | The integration base the user/project names |
| Release assembly | `release/<version>` | Project release base |
| Emergency production fix | `hotfix/<version>` | Project production branch |

Keep the real ticket key's case (`ABC-123`), use a short meaningful suffix, and
check it with `git check-ref-format --branch`. Never fabricate a ticket key or a
version. A Jira Bug is not automatically a hotfix. If the documented base or target
does not exist on the remote, report the mismatch and ask for the mapping before
branching or publishing. Refresh the remote ref before branching from it.

Many teams use environment branches (for example `prd`, `stg`, `dev`, `sbx`) where
a merge triggers deployment. Treat such a target as deployment-impacting and say
so in the MR; do not create environment branches or change CI as a side effect.

## Default commits

Conventional Commits, with the ticket key when one exists:

```text
type(scope): KEY-123 short description
type(scope): short description
```

Scope is optional; choose the type from the change. Commit only intended files.

## Merge gates

Every merge into a protected, integration or release branch goes through an MR.
Review and required CI must pass before merge; a draft MR may be opened while
checks are pending. Never describe pending, skipped or failed CI as passed.
Opening an MR does not authorize merging, approving or deploying it. Keep reusable
`merge/*` and `release/*` branches rather than blindly deleting source branches.
