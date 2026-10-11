"""High-level Jira, Confluence, GitLab and Figma commands built on one REST primitive.

The host CLI supplies `call(service, method, path, query, body, write)` returning
`{"status", "pagination", "data"}`, `base(service)` returning the configured API base,
and `context` defaults. Paths are relative to each configured base:
Jira `.../rest/api/3`, Confluence `.../wiki/api/v2`, GitLab `.../api/v4`, Figma `.../v1`.
"""

import argparse
import base64
import json
from pathlib import Path
import re
import urllib.parse


class UsageError(ValueError):
    pass


def csv(value):
    return [item.strip() for item in value.split(",") if item.strip()]


def read_text(path):
    return Path(path).read_text(encoding="utf-8")


# ---------------------------------------------------------------- Atlassian document format

def adf_to_text(node):
    """Flatten Atlassian Document Format to readable plain text (tables as pipe rows)."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(child) for child in node)
    kind = node.get("type")
    attrs = node.get("attrs") or {}
    children = node.get("content") or []
    if kind == "text":
        text = node.get("text", "")
        for mark in node.get("marks") or []:
            if mark.get("type") == "link" and (mark.get("attrs") or {}).get("href") not in (None, text):
                text += f" ({mark['attrs']['href']})"
            elif mark.get("type") == "code":
                text = f"`{text}`"
        return text
    if kind == "hardBreak":
        return "\n"
    if kind in ("mention", "emoji", "status", "date"):
        return str(attrs.get("text") or attrs.get("shortName") or attrs.get("timestamp") or "")
    if kind == "inlineCard" or kind == "blockCard":
        return str(attrs.get("url", ""))
    if kind == "heading":
        return "#" * int(attrs.get("level", 1)) + " " + adf_to_text(children) + "\n\n"
    if kind == "paragraph":
        return adf_to_text(children) + "\n\n"
    if kind in ("bulletList", "orderedList"):
        lines = []
        for index, item in enumerate(children, 1):
            marker = f"{index}." if kind == "orderedList" else "-"
            body = adf_to_text(item.get("content") or []).strip().replace("\n\n", "\n")
            lines.append(f"{marker} " + body.replace("\n", "\n  "))
        return "\n".join(lines) + "\n\n"
    if kind == "codeBlock":
        return "```" + str(attrs.get("language") or "") + "\n" + adf_to_text(children) + "\n```\n\n"
    if kind == "table":
        rows = []
        for row in children:
            cells = [adf_to_text(cell.get("content") or []).strip().replace("\n\n", " ").replace("\n", " ")
                     for cell in row.get("content") or []]
            rows.append("| " + " | ".join(cells) + " |")
        return "\n".join(rows) + "\n\n"
    if kind == "rule":
        return "---\n\n"
    if kind in ("mediaSingle", "mediaGroup", "media"):
        return "[attachment]\n\n" if kind != "media" else ""
    return adf_to_text(children)


def text_to_adf(text):
    """Plain text to ADF: blank lines separate paragraphs, single newlines become hard breaks."""
    blocks = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        content = []
        for index, line in enumerate(paragraph.split("\n")):
            if index:
                content.append({"type": "hardBreak"})
            if line:
                content.append({"type": "text", "text": line})
        blocks.append({"type": "paragraph", "content": content})
    return {"type": "doc", "version": 1, "content": blocks}


def text_value(value):
    return adf_to_text(value).strip() if isinstance(value, (dict, list)) else value


# ---------------------------------------------------------------- Jira

ISSUE_FIELDS = ["summary", "status", "issuetype", "priority", "assignee", "reporter", "labels",
                "components", "fixVersions", "parent", "description", "subtasks", "issuelinks",
                "attachment", "created", "updated"]
SEARCH_FIELDS = ["summary", "status", "issuetype", "priority", "assignee", "labels", "parent", "updated"]


def site_root(api_base):
    parts = urllib.parse.urlsplit(api_base)
    return f"{parts.scheme}://{parts.netloc}"


def name_of(value):
    if isinstance(value, dict):
        return value.get("displayName") or value.get("name") or value.get("value") or value.get("key")
    return value


def trim_issue(issue, browse_root):
    fields = issue.get("fields") or {}
    out = {"key": issue.get("key"), "url": f"{browse_root}/browse/{issue.get('key')}"}
    simple = {"summary": "summary", "status": "status", "issuetype": "type", "priority": "priority",
              "assignee": "assignee", "reporter": "reporter", "created": "created", "updated": "updated"}
    for source, target in simple.items():
        if source in fields:
            out[target] = name_of(fields[source])
    for source in ("labels",):
        if source in fields:
            out[source] = fields[source]
    for source in ("components", "fixVersions"):
        if source in fields:
            out[source] = [name_of(item) for item in fields[source] or []]
    if fields.get("parent"):
        parent = fields["parent"]
        out["parent"] = {"key": parent.get("key"),
                         "summary": (parent.get("fields") or {}).get("summary")}
    if "description" in fields:
        out["description"] = text_value(fields["description"]) or ""
    if fields.get("subtasks"):
        out["subtasks"] = [{"key": s.get("key"), "summary": (s.get("fields") or {}).get("summary"),
                            "status": name_of((s.get("fields") or {}).get("status"))}
                           for s in fields["subtasks"]]
    if fields.get("issuelinks"):
        links = []
        for link in fields["issuelinks"]:
            direction = "outward" if "outwardIssue" in link else "inward"
            other = link.get(direction + "Issue") or {}
            links.append({"relation": (link.get("type") or {}).get(direction),
                          "key": other.get("key"),
                          "summary": (other.get("fields") or {}).get("summary")})
        out["links"] = links
    if fields.get("attachment"):
        out["attachments"] = [{"filename": a.get("filename"), "size": a.get("size"),
                               "mimeType": a.get("mimeType"), "url": a.get("content")}
                              for a in fields["attachment"]]
    for key, value in fields.items():
        if not key.startswith("customfield_") or value is None:
            continue
        if isinstance(value, dict) and value.get("type") == "doc":
            out[key] = text_value(value)
        elif isinstance(value, dict):
            out[key] = name_of(value)
        elif isinstance(value, list):
            out[key] = [name_of(item) for item in value]
        else:
            out[key] = value
    return out


def jira_issue(call, base, args):
    fields = args.fields or ISSUE_FIELDS
    data = call("jira", "GET", f"issue/{args.key}", [("fields", ",".join(fields))])["data"]
    if args.raw:
        result = data
    else:
        result = trim_issue(data, site_root(base("jira")))
    if args.comments:
        page = call("jira", "GET", f"issue/{args.key}/comment",
                    [("maxResults", str(args.comments)), ("orderBy", "-created")])["data"] or {}
        comments = [{"id": c.get("id"), "author": name_of(c.get("author")),
                     "created": c.get("created"), "body": text_value(c.get("body"))}
                    for c in page.get("comments", [])]
        # Fetched newest first so the window holds the latest; print oldest first to read as a thread.
        result["comments"] = list(reversed(comments))
        result["comments_total"] = page.get("total")
    return result


def jira_search(call, base, args):
    fields = args.fields or SEARCH_FIELDS
    issues, token = [], None
    while len(issues) < args.limit:
        body = {"jql": args.jql, "fields": fields, "maxResults": min(100, args.limit - len(issues))}
        if token:
            body["nextPageToken"] = token
        # The JQL endpoint is a read that happens to use POST; it changes nothing.
        page = call("jira", "POST", "search/jql", (), body, True)["data"] or {}
        batch = page.get("issues") or []
        issues.extend(batch)
        token = page.get("nextPageToken")
        if not token or not batch:
            break
    issues = issues[:args.limit]
    root = site_root(base("jira"))
    return {"count": len(issues), "truncated": bool(token) and len(issues) >= args.limit,
            "issues": issues if args.raw else [trim_issue(i, root) for i in issues]}


def jira_myself(call, base, args):
    data = call("jira", "GET", "myself")["data"] or {}
    return {"accountId": data.get("accountId"), "displayName": data.get("displayName"),
            "timeZone": data.get("timeZone")}


def jira_fields(call, base, args):
    data = call("jira", "GET", "field")["data"] or []
    needle = (args.name or "").lower()
    return [{"id": f.get("id"), "name": f.get("name"), "custom": f.get("custom"),
             "type": (f.get("schema") or {}).get("type")}
            for f in data if needle in (f.get("name") or "").lower()]


def jira_comment(call, base, args):
    body = {"body": text_to_adf(read_text(args.body_file))}
    data = call("jira", "POST", f"issue/{args.key}/comment", (), body, args.write)["data"] or {}
    return {"issue": args.key, "comment_id": data.get("id"), "created": data.get("created")}


# ---------------------------------------------------------------- Confluence

def page_id(ref):
    ref = str(ref)
    if ref.isdigit():
        return ref
    match = re.search(r"/pages/(\d+)", ref) or re.search(r"[?&]pageId=(\d+)", ref)
    if not match:
        raise UsageError("Pass a numeric page id or a Confluence page URL")
    return match[1]


def wiki_root(api_base):
    return api_base.rsplit("/api/", 1)[0]


def trim_page(page, root):
    links = page.get("_links") or {}
    out = {"id": page.get("id"), "title": page.get("title"), "status": page.get("status"),
           "spaceId": page.get("spaceId"), "parentId": page.get("parentId"),
           "version": (page.get("version") or {}).get("number"),
           "url": root + links["webui"] if links.get("webui") else None}
    body = page.get("body") or {}
    for representation, content in body.items():
        if isinstance(content, dict) and "value" in content:
            value = content["value"]
            if representation == "atlas_doc_format":
                value = adf_to_text(json.loads(value)).strip()
            out["body"] = value
            out["body_format"] = representation
    return out


def confluence_page(call, base, args):
    data = call("confluence", "GET", f"pages/{page_id(args.ref)}",
                [("body-format", args.body_format)])["data"]
    return data if args.raw else trim_page(data, wiki_root(base("confluence")))


def confluence_children(call, base, args):
    data = call("confluence", "GET", f"pages/{page_id(args.ref)}/children",
                [("limit", str(args.limit))])["data"] or {}
    root = wiki_root(base("confluence"))
    return [trim_page(p, root) for p in data.get("results", [])]


def confluence_search(call, base, args, context):
    query = [("title", args.title), ("limit", str(args.limit))]
    space = args.space_id or context.get("CONFLUENCE_SPACE_ID")
    if space:
        query.append(("space-id", space))
    data = call("confluence", "GET", "pages", query)["data"] or {}
    root = wiki_root(base("confluence"))
    return [trim_page(p, root) for p in data.get("results", [])]


# ---------------------------------------------------------------- GitLab

MR_URL = re.compile(r"https?://[^/]+/(.+?)/-/merge_requests/(\d+)")


def project_ref(value):
    value = str(value)
    return value if value.isdigit() else urllib.parse.quote(value, safe="")


def resolve_mr(args, context):
    """Accept `<mr-url>`, `<project> <iid>` or `<iid>` with GITLAB_PROJECT as the project."""
    ref, iid = args.ref, args.iid
    match = MR_URL.match(ref or "")
    if match:
        return project_ref(match[1]), match[2]
    if iid is None and ref and ref.isdigit() and context.get("GITLAB_PROJECT"):
        return project_ref(context["GITLAB_PROJECT"]), ref
    if ref and iid:
        return project_ref(ref), iid
    raise UsageError("Pass an MR URL, '<project> <iid>', or an iid with GITLAB_PROJECT set")


def resolve_project(value, context):
    project = value or context.get("GITLAB_PROJECT")
    if not project:
        raise UsageError("Pass --project or set GITLAB_PROJECT")
    return project_ref(project)


def paginate(call, service, path, query=(), limit=1000):
    items, page = [], "1"
    while page and len(items) < limit:
        result = call(service, "GET", path, list(query) + [("per_page", "100"), ("page", page)])
        items.extend(result["data"] or [])
        page = (result.get("pagination") or {}).get("X-Next-Page") or None
    return items[:limit]


def trim_mr(mr):
    pipeline = mr.get("head_pipeline") or mr.get("pipeline") or {}
    return {"iid": mr.get("iid"), "title": mr.get("title"), "state": mr.get("state"),
            "draft": mr.get("draft"), "source_branch": mr.get("source_branch"),
            "target_branch": mr.get("target_branch"), "sha": mr.get("sha"),
            "author": (mr.get("author") or {}).get("username"),
            "reviewers": [r.get("username") for r in mr.get("reviewers") or []],
            "labels": mr.get("labels"), "has_conflicts": mr.get("has_conflicts"),
            "merge_status": mr.get("detailed_merge_status") or mr.get("merge_status"),
            "pipeline": {"status": pipeline.get("status"), "url": pipeline.get("web_url")}
            if pipeline else None,
            "web_url": mr.get("web_url")}


def gitlab_project(call, base, args, context):
    data = call("gitlab", "GET", f"projects/{resolve_project(args.project, context)}")["data"] or {}
    return {"id": data.get("id"), "path": data.get("path_with_namespace"),
            "default_branch": data.get("default_branch"), "web_url": data.get("web_url")}


def gitlab_mr_get(call, base, args, context):
    project, iid = resolve_mr(args, context)
    data = call("gitlab", "GET", f"projects/{project}/merge_requests/{iid}")["data"]
    return data if args.raw else trim_mr(data)


def gitlab_mr_list(call, base, args, context):
    query = [("state", args.state)]
    for key, value in (("source_branch", args.source), ("target_branch", args.target)):
        if value:
            query.append((key, value))
    items = paginate(call, "gitlab", f"projects/{resolve_project(args.project, context)}/merge_requests",
                     query, args.limit)
    return [trim_mr(mr) for mr in items]


def gitlab_mr_create(call, base, args, context):
    project = resolve_project(args.project, context)
    target = args.target or context.get("GIT_TARGET_BRANCH")
    if not target:
        raise UsageError("Pass --target or set GIT_TARGET_BRANCH")
    title = ("Draft: " + args.title) if args.draft and not args.title.lower().startswith("draft:") else args.title
    body = {"source_branch": args.source, "target_branch": target, "title": title,
            "description": read_text(args.description_file)}
    if args.squash is not None:
        body["squash"] = args.squash
    if args.remove_source_branch is not None:
        body["remove_source_branch"] = args.remove_source_branch
    if args.label:
        body["labels"] = ",".join(args.label)
    data = call("gitlab", "POST", f"projects/{project}/merge_requests", (), body, args.write)["data"]
    return trim_mr(data or {})


def trim_note(note):
    position = note.get("position") or {}
    path = position.get("new_path") or position.get("old_path")
    line = position.get("new_line") or position.get("old_line")
    return {"id": note.get("id"), "author": (note.get("author") or {}).get("username"),
            "created": note.get("created_at"), "system": note.get("system"),
            "resolved": note.get("resolved"),
            "location": f"{path}:{line}" if path and line else path,
            "body": note.get("body")}


def gitlab_mr_discussions(call, base, args, context):
    project, iid = resolve_mr(args, context)
    threads = paginate(call, "gitlab", f"projects/{project}/merge_requests/{iid}/discussions")
    out = []
    for thread in threads:
        notes = [n for n in thread.get("notes") or [] if not n.get("system")]
        if not notes:
            continue
        resolvable = any(n.get("resolvable") for n in notes)
        resolved = resolvable and all(n.get("resolved") for n in notes if n.get("resolvable"))
        if args.unresolved and (not resolvable or resolved):
            continue
        out.append({"id": thread.get("id"), "resolvable": resolvable, "resolved": resolved,
                    "notes": [trim_note(n) for n in notes]})
    return out


def gitlab_mr_note(call, base, args, context):
    project, iid = resolve_mr(args, context)
    body = {"body": read_text(args.body_file)}
    if args.discussion:
        path = f"projects/{project}/merge_requests/{iid}/discussions/{args.discussion}/notes"
    else:
        path = f"projects/{project}/merge_requests/{iid}/notes"
    data = call("gitlab", "POST", path, (), body, args.write)["data"] or {}
    return trim_note(data)


def gitlab_mr_resolve(call, base, args, context):
    project, iid = resolve_mr(args, context)
    data = call("gitlab", "PUT", f"projects/{project}/merge_requests/{iid}/discussions/{args.discussion}",
                [("resolved", "false" if args.unresolve else "true")], None, args.write)["data"] or {}
    return {"id": data.get("id"),
            "resolved": all(n.get("resolved") for n in data.get("notes") or [] if n.get("resolvable"))}


def gitlab_mr_label(call, base, args, context):
    project, iid = resolve_mr(args, context)
    if not args.add and not args.remove:
        raise UsageError("Pass --add and/or --remove")
    body = {}
    if args.add:
        body["add_labels"] = ",".join(args.add)
    if args.remove:
        body["remove_labels"] = ",".join(args.remove)
    data = call("gitlab", "PUT", f"projects/{project}/merge_requests/{iid}", (), body, args.write)["data"]
    return {"iid": (data or {}).get("iid"), "labels": (data or {}).get("labels")}


def gitlab_mr_pipelines(call, base, args, context):
    project, iid = resolve_mr(args, context)
    items = call("gitlab", "GET", f"projects/{project}/merge_requests/{iid}/pipelines")["data"] or []
    return [{"id": p.get("id"), "sha": p.get("sha"), "ref": p.get("ref"), "status": p.get("status"),
             "source": p.get("source"), "url": p.get("web_url")} for p in items[:args.limit]]


def gitlab_mr_changes(call, base, args, context):
    project, iid = resolve_mr(args, context)
    items = paginate(call, "gitlab", f"projects/{project}/merge_requests/{iid}/diffs")
    return [{"path": d.get("new_path"), "old_path": d.get("old_path"), "new": d.get("new_file"),
             "deleted": d.get("deleted_file"), "renamed": d.get("renamed_file"),
             "diff": None if args.names_only else d.get("diff")} for d in items]


def gitlab_file_get(call, base, args, context):
    project = resolve_project(args.project, context)
    path = urllib.parse.quote(args.path, safe="")
    data = call("gitlab", "GET", f"projects/{project}/repository/files/{path}", [("ref", args.ref)])["data"] or {}
    content = data.get("content", "")
    if data.get("encoding") == "base64":
        raw = base64.b64decode(content)
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise UsageError("File is binary; fetch it through the raw request command") from None
    return {"path": data.get("file_path"), "ref": data.get("ref"), "blob_id": data.get("blob_id"),
            "size": data.get("size"), "content": content}


# ---------------------------------------------------------------- Figma

FIGMA_URL = re.compile(r"figma\.com/(?:design|file|proto|board)/([A-Za-z0-9]+)(?:/branch/([A-Za-z0-9]+))?")


def figma_target(args, context):
    """Return (file_key, node_ids) from --file (key or URL) and --ids."""
    ref = args.file or context.get("FIGMA_FILE_KEY")
    if not ref:
        raise UsageError("Pass --file (key or URL) or set FIGMA_FILE_KEY")
    ids = list(args.ids or [])
    match = FIGMA_URL.search(ref)
    if match:
        key = match[2] or match[1]
        node = urllib.parse.parse_qs(urllib.parse.urlsplit(ref).query).get("node-id")
        if node and not ids:
            ids = [node[0].replace("-", ":")]
    else:
        key = ref
    return key, [i.replace("-", ":") for i in ids]


def summarize_node(node, depth):
    out = {"id": node.get("id"), "name": node.get("name"), "type": node.get("type")}
    box = node.get("absoluteBoundingBox")
    if box:
        out["size"] = [box.get("width"), box.get("height")]
    if node.get("characters"):
        out["text"] = node["characters"]
    if depth > 0 and node.get("children"):
        out["children"] = [summarize_node(child, depth - 1) for child in node["children"]]
    return out


def figma_nodes(call, base, args, context):
    key, ids = figma_target(args, context)
    if not ids:
        raise UsageError("Pass --ids or a URL with node-id")
    query = [("ids", ",".join(ids))]
    data = call("figma", "GET", f"files/{key}/nodes", query)["data"] or {}
    if args.raw:
        return data
    return {"file": key, "name": data.get("name"),
            "nodes": {nid: summarize_node((value or {}).get("document") or {}, args.depth)
                      for nid, value in (data.get("nodes") or {}).items()}}


def figma_images(call, base, args, context):
    key, ids = figma_target(args, context)
    if not ids:
        raise UsageError("Pass --ids or a URL with node-id")
    query = [("ids", ",".join(ids)), ("format", args.format)]
    if args.scale:
        query.append(("scale", str(args.scale)))
    data = call("figma", "GET", f"images/{key}", query)["data"] or {}
    if data.get("err"):
        raise UsageError("Figma image export failed: " + str(data["err"]))
    return {"file": key, "format": args.format, "images": data.get("images")}


# ---------------------------------------------------------------- argument wiring

def add_mr_ref(parser):
    parser.add_argument("ref", help="MR URL, project path/id, or iid when GITLAB_PROJECT is set")
    parser.add_argument("iid", nargs="?")


def add_write(parser):
    parser.add_argument("--write", action="store_true", help="required for this mutation")


def register(commands):
    """Add jira/confluence/gitlab/figma command groups to an argparse subparsers object."""
    jira = commands.add_parser("jira", help="Jira Cloud commands").add_subparsers(dest="action", required=True)
    p = jira.add_parser("issue", help="one issue with links, attachments and optional comments")
    p.add_argument("key")
    p.add_argument("--comments", type=int, default=0, help="include the N most recent comments")
    p.add_argument("--fields", type=csv, help="comma-separated field ids (default: the useful set)")
    p.add_argument("--raw", action="store_true")
    p.set_defaults(handler=jira_issue)
    p = jira.add_parser("search", help="JQL search with token pagination")
    p.add_argument("--jql", required=True)
    p.add_argument("--fields", type=csv)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--raw", action="store_true")
    p.set_defaults(handler=jira_search)
    p = jira.add_parser("myself", help="the authenticated account")
    p.set_defaults(handler=jira_myself)
    p = jira.add_parser("fields", help="find field ids by name, e.g. story points")
    p.add_argument("--name", default="")
    p.set_defaults(handler=jira_fields)
    p = jira.add_parser("comment", help="add a plain-text comment")
    p.add_argument("key")
    p.add_argument("--body-file", required=True)
    add_write(p)
    p.set_defaults(handler=jira_comment)

    wiki = commands.add_parser("confluence", help="Confluence Cloud v2 commands").add_subparsers(
        dest="action", required=True)
    p = wiki.add_parser("page", help="a page by id or URL")
    p.add_argument("ref")
    p.add_argument("--format", dest="body_format", default="storage",
                   choices=("storage", "atlas_doc_format", "view"))
    p.add_argument("--raw", action="store_true")
    p.set_defaults(handler=confluence_page)
    p = wiki.add_parser("children", help="direct child pages")
    p.add_argument("ref")
    p.add_argument("--limit", type=int, default=50)
    p.set_defaults(handler=confluence_children)
    p = wiki.add_parser("search", help="pages by exact title")
    p.add_argument("--title", required=True)
    p.add_argument("--space-id")
    p.add_argument("--limit", type=int, default=25)
    p.set_defaults(handler=confluence_search, needs_context=True)

    gitlab = commands.add_parser("gitlab", help="GitLab REST v4 commands").add_subparsers(
        dest="group", required=True)
    p = gitlab.add_parser("project", help="project id, path and default branch")
    p.add_argument("project", nargs="?")
    p.set_defaults(handler=gitlab_project, needs_context=True)
    mr = gitlab.add_parser("mr", help="merge requests").add_subparsers(dest="action", required=True)
    p = mr.add_parser("get", help="state, branches, conflicts and head pipeline")
    add_mr_ref(p)
    p.add_argument("--raw", action="store_true")
    p.set_defaults(handler=gitlab_mr_get, needs_context=True)
    p = mr.add_parser("list", help="MRs filtered by branch and state")
    p.add_argument("--project")
    p.add_argument("--source")
    p.add_argument("--target")
    p.add_argument("--state", default="opened", choices=("opened", "closed", "merged", "all"))
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(handler=gitlab_mr_list, needs_context=True)
    p = mr.add_parser("create", help="open an MR from a description file")
    p.add_argument("--project")
    p.add_argument("--source", required=True)
    p.add_argument("--target", help="default: GIT_TARGET_BRANCH")
    p.add_argument("--title", required=True)
    p.add_argument("--description-file", required=True)
    p.add_argument("--draft", action="store_true")
    p.add_argument("--label", action="append", default=[])
    p.add_argument("--squash", action=argparse.BooleanOptionalAction, default=None,
                   help="default: project setting")
    p.add_argument("--remove-source-branch", action=argparse.BooleanOptionalAction, default=None,
                   help="default: project setting")
    add_write(p)
    p.set_defaults(handler=gitlab_mr_create, needs_context=True)
    p = mr.add_parser("discussions", help="review threads with file:line locations")
    add_mr_ref(p)
    p.add_argument("--unresolved", action="store_true")
    p.set_defaults(handler=gitlab_mr_discussions, needs_context=True)
    p = mr.add_parser("note", help="post a general note, or reply in a thread with --discussion")
    add_mr_ref(p)
    p.add_argument("--body-file", required=True)
    p.add_argument("--discussion")
    add_write(p)
    p.set_defaults(handler=gitlab_mr_note, needs_context=True)
    p = mr.add_parser("resolve", help="resolve (or --unresolve) a thread")
    add_mr_ref(p)
    p.add_argument("--discussion", required=True)
    p.add_argument("--unresolve", action="store_true")
    add_write(p)
    p.set_defaults(handler=gitlab_mr_resolve, needs_context=True)
    p = mr.add_parser("label", help="add/remove labels")
    add_mr_ref(p)
    p.add_argument("--add", action="append", default=[])
    p.add_argument("--remove", action="append", default=[])
    add_write(p)
    p.set_defaults(handler=gitlab_mr_label, needs_context=True)
    p = mr.add_parser("pipelines", help="pipelines for the MR, newest first")
    add_mr_ref(p)
    p.add_argument("--limit", type=int, default=5)
    p.set_defaults(handler=gitlab_mr_pipelines, needs_context=True)
    p = mr.add_parser("changes", help="changed files and diffs")
    add_mr_ref(p)
    p.add_argument("--names-only", action="store_true")
    p.set_defaults(handler=gitlab_mr_changes, needs_context=True)
    files = gitlab.add_parser("file", help="repository files").add_subparsers(dest="action", required=True)
    p = files.add_parser("get", help="text file content at a ref")
    p.add_argument("path")
    p.add_argument("--ref", required=True)
    p.add_argument("--project")
    p.set_defaults(handler=gitlab_file_get, needs_context=True)

    figma = commands.add_parser("figma", help="Figma REST commands").add_subparsers(dest="action", required=True)
    for name, handler, help_text in (("nodes", figma_nodes, "node tree summary"),
                                     ("images", figma_images, "rendered image URLs")):
        p = figma.add_parser(name, help=help_text)
        p.add_argument("--file", help="file key or figma.com URL (node-id is read from the URL)")
        p.add_argument("--ids", type=csv, help="comma-separated node ids, 1:2 or 1-2")
        if name == "nodes":
            p.add_argument("--depth", type=int, default=2)
            p.add_argument("--raw", action="store_true")
        else:
            p.add_argument("--format", default="svg", choices=("svg", "png", "jpg", "pdf"))
            p.add_argument("--scale", type=float)
        p.set_defaults(handler=handler, needs_context=True)


def run(args, call, base, context):
    if getattr(args, "needs_context", False):
        return args.handler(call, base, args, context)
    return args.handler(call, base, args)
