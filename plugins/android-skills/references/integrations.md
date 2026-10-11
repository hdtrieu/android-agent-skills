# Integration configuration

Jira, Confluence, GitLab and Figma. Prefer a connected tool (MCP connector, `glab`,
`gh`, `acli`) when the session has one. Otherwise use the bundled REST fallback,
`scripts/integrations.py` in this plugin's root (two directories above each skill
directory). It needs only Python 3 and network access.

## Configure with your own environment

Nothing company-specific ships with this plugin. Each user sets their own values
in the process environment, agent secret settings, or an optional env file.
A service is enabled when its token variable is set.

| Service | Base URL variable (example) | Credentials |
| --- | --- | --- |
| Jira Cloud | `JIRA_BASE_URL` (`https://YOUR-SITE.atlassian.net/rest/api/3`) | `JIRA_EMAIL` + `JIRA_API_TOKEN` (basic); token alone → bearer |
| Confluence Cloud v2 | `CONFLUENCE_BASE_URL` (`https://YOUR-SITE.atlassian.net/wiki/api/v2`) | `CONFLUENCE_EMAIL` + `CONFLUENCE_API_TOKEN`; token alone → bearer |
| GitLab | `GITLAB_BASE_URL` (default `https://gitlab.com/api/v4`) | `GITLAB_TOKEN` (`PRIVATE-TOKEN` header) |
| Figma | `FIGMA_BASE_URL` (default `https://api.figma.com/v1`) | `FIGMA_TOKEN` (`X-Figma-Token`) |

Optional, non-secret project context. `doctor` reports these so the agent can
resolve destinations; repository instructions take precedence over them:

| Variable | Meaning |
| --- | --- |
| `JIRA_PROJECT_KEY` | Default Jira project key, e.g. `ABC` |
| `CONFLUENCE_SPACE_ID` | Default Confluence space |
| `GITLAB_PROJECT` | Numeric ID or `group/project` path |
| `FIGMA_FILE_KEY` | Default Figma file |
| `GIT_BASE_BRANCH` | Base for new ticket branches, e.g. `develop` |
| `GIT_TARGET_BRANCH` | Default MR target, e.g. `develop` |
| `BRANCH_PATTERN` | Branch template, default `feature/{KEY}-{slug}` |
| `COMMIT_PATTERN` | Commit subject template, default `type(scope): {KEY} summary` |

The optional env file defaults to `~/.config/android-agent-skills/.env`; override it
with `ANDROID_SKILLS_ENV_FILE` or `--env-file PATH`. Copy the plugin's
`.env.example` there. The file is parsed as plain `NAME=value` lines without shell
execution or expansion; exported process values win. Only the names above are read.
Never commit it, paste tokens into chat, or put them in URLs or body files.

Atlassian scoped tokens/OAuth may need `api.atlassian.com` gateway URLs with a cloud
ID; set the matching base URL. Data Center instances are not assumed compatible
with the Cloud examples.

## Check and request

```sh
python3 scripts/integrations.py doctor
python3 scripts/integrations.py request jira GET issue/ABC-123
python3 scripts/integrations.py request confluence GET pages/PAGE_ID
python3 scripts/integrations.py request gitlab GET projects/group%2Fproject/merge_requests --query state=opened
python3 scripts/integrations.py request figma GET files/FILE_KEY/nodes --query ids=1:2
```

`doctor` makes no network request. `configured-unverified` does not prove token
validity, permissions or connectivity. Each `request` makes one call with no retry
or pagination; follow provider pagination explicitly. Percent-encode GitLab project
paths (`group%2Fproject`). Paths stay under the configured base, redirects are
refused, TLS verification stays on, and failure output omits response bodies.

For an explicitly requested write, put the JSON body in a file:

```sh
python3 scripts/integrations.py request gitlab POST projects/123/merge_requests --body-file mr.json --write
```

`--write` is a local guard, not authorization; authorization comes from the user's
task. A timeout may follow a successful write: check before retrying.

## glab

`glab` reads `GITLAB_TOKEN` and `GITLAB_HOST` itself, so the same variables work:
`glab api --hostname "$GITLAB_HOST" user`.

## Provider sources

- [Jira Cloud basic auth](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/)
- [Confluence Cloud REST v2](https://developer.atlassian.com/cloud/confluence/rest/v2/intro/)
- [GitLab REST authentication](https://docs.gitlab.com/api/rest/authentication/)
- [Figma authentication](https://developers.figma.com/docs/rest-api/authentication/)
