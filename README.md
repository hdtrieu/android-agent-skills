# Android Agent Skills

A Claude Code plugin marketplace with skills for Android engineering: Kotlin/Compose
conventions, Clean Architecture + MVI, tests, local review, root-cause analysis,
Maestro E2E, implementation plans, Jira ticket branches and GitLab merge requests.

Nothing company-specific is bundled. Jira, Confluence, GitLab and Figma access, and
your team's branch and commit rules, come from **your own environment variables** or
your repository's instructions.

## Install

In Claude Code:

```text
/plugin marketplace add hdtrieu/android-agent-skills
/plugin install android-skills@android-agent-skills
```

Skills are namespaced, e.g. `/android-skills:jira-ticket ABC-123`. Claude also loads
them automatically when a task matches their description.

## Skills

| Skill | Purpose |
| --- | --- |
| `android-conventions` | Kotlin, Compose, Hilt, Coroutines and layer rules for writing or reviewing code |
| `implement-mvi-feature` | Plan/implement a screen with Action/UiState/Result, pure Reducer, ViewModel |
| `writing-tests` | Choose the right test layer; 12 regression archetypes; deterministic coroutine tests |
| `local-review` | Review staged, unstaged and untracked changes for demonstrated defects |
| `root-cause-analysis` | Diagnose a defect from evidence before fixing it |
| `maestro-e2e` | Write and run Maestro flows; screenshots against the design |
| `implementation-plan` | Ticket + PRD + discussions + repos → scoped, estimated plan with Gantt |
| `jira-ticket` | Read a Jira ticket, extract acceptance criteria, prepare the branch |
| `create-mr` | Commit, push and open a GitLab MR (or GitHub PR) with review/CI gates |
| `project-integrations` | Jira, Confluence, GitLab and Figma access and the REST fallback |

Shared references: [MVI contract](plugins/android-skills/references/mvi.md),
[module structure](plugins/android-skills/references/module-structure.md),
[Now in Android mapping](plugins/android-skills/references/now-in-android.md),
[integrations](plugins/android-skills/references/integrations.md).

## Agent

`android-code-reviewer` is a read-only Claude Code subagent for an independent review
before you push or open an MR. Ask "review my changes with android-code-reviewer" or
mention `@android-code-reviewer`. It reads staged, unstaged, untracked or committed
changes, loads the matching skills and your repository's rules, and reports P0/P1/P2
findings with a concrete fix each. It never edits, builds or pushes.

## Configure integrations

Connected tools (MCP connectors, `glab`, `gh`) are used first. Without them, the
plugin's Python 3 REST fallback reads only these variables. A service is enabled
when its token is set:

| Service | Variables |
| --- | --- |
| Jira | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| Confluence | `CONFLUENCE_BASE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN` |
| GitLab | `GITLAB_BASE_URL` (default `https://gitlab.com/api/v4`), `GITLAB_TOKEN` |
| Figma | `FIGMA_TOKEN` |

Optional team context: `JIRA_PROJECT_KEY`, `GITLAB_PROJECT`, `GIT_BASE_BRANCH`,
`GIT_TARGET_BRANCH`, `BRANCH_PATTERN`, `COMMIT_PATTERN`, `CONFLUENCE_SPACE_ID`,
`FIGMA_FILE_KEY`.

Set them in your shell profile or Claude Code settings (`env` in
`~/.claude/settings.json`), or in an env file:

```sh
mkdir -p ~/.config/android-agent-skills
curl -fsSL https://raw.githubusercontent.com/hdtrieu/android-agent-skills/main/plugins/android-skills/.env.example \
  -o ~/.config/android-agent-skills/.env
chmod 600 ~/.config/android-agent-skills/.env
# edit the file, then ask Claude to run the project-integrations doctor
```

The env file is parsed as plain `NAME=value` lines without shell execution; exported
variables win. `doctor` checks configuration offline and never prints secrets. Write
requests need an explicit `--write` flag, and the skills do not push, comment, change
ticket status or open MRs unless you ask.

## Optional companions

- Google's official [android/skills](https://github.com/android/skills) (Navigation 3,
  edge-to-edge, adaptive, CameraX, R8, …) work well alongside these skills.
- [Ponytail](https://github.com/DietrichGebert/ponytail) for minimal-diff guidance.

## Development

```sh
cd plugins/android-skills
python3 -m unittest discover -s tests -v
claude plugin validate .
```

## License

[MIT](LICENSE)
