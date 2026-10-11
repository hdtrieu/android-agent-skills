#!/usr/bin/env python3
"""JSON REST fallback for Jira, Confluence, GitLab and Figma, configured only by environment."""

import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_ENV_FILE = Path.home() / ".config" / "android-agent-skills" / ".env"

# Each service is enabled when its token variable is set. Basic auth is used when
# the username variable is set too; otherwise the token goes in the auth header.
SERVICES = {
    "jira": {"base": "JIRA_BASE_URL", "user": "JIRA_EMAIL", "token": "JIRA_API_TOKEN",
             "auth": "bearer"},
    "confluence": {"base": "CONFLUENCE_BASE_URL", "user": "CONFLUENCE_EMAIL",
                   "token": "CONFLUENCE_API_TOKEN", "auth": "bearer"},
    "gitlab": {"base": "GITLAB_BASE_URL", "default_base": "https://gitlab.com/api/v4",
               "token": "GITLAB_TOKEN", "auth": "private-token"},
    "figma": {"base": "FIGMA_BASE_URL", "default_base": "https://api.figma.com/v1",
              "token": "FIGMA_TOKEN", "auth": "figma-token"},
}
# Non-secret project context reported by doctor so agents can resolve destinations.
CONTEXT = ("JIRA_PROJECT_KEY", "CONFLUENCE_SPACE_ID", "GITLAB_PROJECT", "FIGMA_FILE_KEY",
           "GIT_BASE_BRANCH", "GIT_TARGET_BRANCH", "BRANCH_PATTERN", "COMMIT_PATTERN")
KNOWN_NAMES = {spec[key] for spec in SERVICES.values() for key in ("base", "user", "token")
               if key in spec} | set(CONTEXT)
AUTH_HEADERS = {
    "bearer": "Authorization",
    "private-token": "PRIVATE-TOKEN",
    "figma-token": "X-Figma-Token",
}


class CommandError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def load_env_file(path, allowed_names=KNOWN_NAMES):
    path = Path(path)
    if not path.exists():
        return
    pending = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if not match:
            raise CommandError(f"Invalid env assignment on line {number}; values omitted")
        if match[1] not in allowed_names:
            continue
        try:
            values = shlex.split(match[2], comments=True, posix=True)
        except ValueError:
            raise CommandError(f"Invalid env quoting on line {number}; values omitted") from None
        if len(values) > 1:
            raise CommandError(f"Quote env values containing spaces on line {number}; values omitted")
        pending[match[1]] = values[0] if values else ""
    # Validate the whole file before making changes; exported process values win.
    for name, value in pending.items():
        os.environ.setdefault(name, value)


def service_config(name):
    spec = SERVICES[name]
    user = os.environ.get(spec.get("user", ""), "") if "user" in spec else ""
    return {
        "enabled": bool(os.environ.get(spec["token"])),
        "base_url": os.environ.get(spec["base"]) or spec.get("default_base", ""),
        "auth": "basic" if user else spec["auth"],
        "username_env": spec.get("user"),
        "token_env": spec["token"],
    }


def validate_base(url):
    if not isinstance(url, str):
        raise CommandError("base URL must be a string")
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or any(c.isspace() for c in url)):
        raise CommandError("base URL must be HTTPS without credentials, query or fragment")
    return url.rstrip("/")


def headers_for(service):
    auth = service.get("auth")
    token_name = service.get("token_env")
    token = os.environ.get(token_name, "") if isinstance(token_name, str) else ""
    if not token:
        raise CommandError("Missing token environment variable: " + str(token_name))
    if auth == "basic":
        username_name = service.get("username_env")
        username = os.environ.get(username_name, "") if isinstance(username_name, str) else ""
        if not username:
            raise CommandError("Missing username environment variable: " + str(username_name))
        value = base64.b64encode(f"{username}:{token}".encode()).decode()
        return {"Authorization": "Basic " + value}
    if auth not in AUTH_HEADERS:
        raise CommandError("Unsupported auth mode")
    return {AUTH_HEADERS[auth]: ("Bearer " + token if auth == "bearer" else token)}


def doctor():
    results = {}
    for name, spec in SERVICES.items():
        service = service_config(name)
        if not service["enabled"]:
            results[name] = {"state": "disabled", "set": spec["token"]}
            continue
        try:
            if not service["base_url"]:
                raise CommandError("Missing base URL environment variable: " + spec["base"])
            validate_base(service["base_url"])
            headers_for(service)
        except ValueError as exc:
            results[name] = {"state": "incomplete", "reason": str(exc)}
        else:
            results[name] = {"state": "configured-unverified", "auth": service["auth"]}
    context = {key: os.environ[key] for key in CONTEXT if os.environ.get(key)}
    return {"network_checked": False, "services": results, "context": context}


def build_url(base, path, query):
    base = validate_base(base)
    parsed = urllib.parse.urlsplit(path)
    if (not path or parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or path.startswith(("/", "\\")) or "\\" in path
            or any(c.isspace() for c in path)):
        raise CommandError("Path must be relative to the API base; use --query for parameters")
    decoded = path
    for _ in range(5):
        previous = decoded
        decoded = urllib.parse.unquote(decoded)
        if decoded == previous:
            break
    else:
        raise CommandError("Path has excessive nested encoding")
    if "\\" in decoded or any(part in (".", "..") for part in decoded.split("/")):
        raise CommandError("Path traversal is not allowed")
    url = base + "/" + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    return url


def request(name, method, path, query=(), body=None, write=False, timeout=30):
    service = service_config(name)
    if not service["enabled"]:
        raise CommandError(f"{name} is not configured; set {SERVICES[name]['token']}")
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
        raise CommandError("Unsupported request method")
    if method != "GET" and not write:
        raise CommandError("Mutations require --write and task authorization")
    if method == "GET" and body is not None:
        raise CommandError("GET requests do not accept a JSON body")
    if not 1 <= timeout <= 120:
        raise CommandError("Timeout must be between 1 and 120 seconds")
    url = build_url(service["base_url"], path, query)
    headers = {"Accept": "application/json", **headers_for(service)}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as response:
            raw = response.read()
            status = response.status
            pagination = {key: response.headers[key] for key in
                          ("Link", "X-Next-Page", "X-Page", "X-Total-Pages")
                          if key in response.headers}
    except urllib.error.HTTPError as exc:
        raise CommandError(f"{name}: HTTP {exc.code}; response body omitted") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise CommandError(name + ": network request failed; verify before retrying a write") from None
    try:
        result = json.loads(raw) if raw else None
    except (ValueError, UnicodeError):
        raise CommandError(name + ": response was not JSON") from None
    return {"status": status, "pagination": pagination, "data": result}


def query_pair(value):
    key, separator, item = value.partition("=")
    if not key or not separator:
        raise argparse.ArgumentTypeError("Use KEY=VALUE")
    return key, item


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path,
                        default=Path(os.environ.get("ANDROID_SKILLS_ENV_FILE", DEFAULT_ENV_FILE)),
                        help="optional credential file; process environment takes precedence")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="offline configuration check; no authentication probe")
    api = commands.add_parser("request", help="one JSON REST call; no retries or pagination")
    api.add_argument("service", choices=tuple(SERVICES))
    api.add_argument("method", choices=("GET", "POST", "PUT", "PATCH", "DELETE"))
    api.add_argument("path")
    api.add_argument("--query", action="append", type=query_pair, default=[])
    api.add_argument("--body-file", type=Path)
    api.add_argument("--write", action="store_true")
    api.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args(argv)
    try:
        load_env_file(args.env_file)
        if args.command == "doctor":
            result = doctor()
        else:
            body = json.loads(args.body_file.read_text(encoding="utf-8")) if args.body_file else None
            result = request(args.service, args.method, args.path, args.query,
                             body, args.write, args.timeout)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "doctor":
            return int(any(s["state"] == "incomplete" for s in result["services"].values()))
        return 0
    except CommandError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (ValueError, OSError, TypeError):
        # Body parsing errors can contain user data; expose only a safe summary.
        print("Command failed. Check environment, request path and provider access.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
