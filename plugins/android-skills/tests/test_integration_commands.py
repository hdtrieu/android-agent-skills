import argparse
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import integration_commands as commands  # noqa: E402

BASES = {"jira": "https://site.example/rest/api/3",
         "confluence": "https://site.example/wiki/api/v2",
         "gitlab": "https://git.example/api/v4",
         "figma": "https://api.figma.example/v1"}


class FakeApi:
    """Records calls and replays canned responses keyed by (method, path)."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, service, method, path, query=(), body=None, write=False):
        self.calls.append({"service": service, "method": method, "path": path,
                           "query": list(query), "body": body, "write": write})
        if method != "GET" and not write:
            raise ValueError("Mutations require --write")
        response = self.responses[(method, path)]
        if isinstance(response, list) and response and isinstance(response[0], dict) and "page" in response[0]:
            page = dict(query).get("page", "1")
            match = next(r for r in response if r["page"] == page)
            return {"status": 200, "pagination": match.get("pagination", {}), "data": match["data"]}
        return {"status": 200, "pagination": {}, "data": response}


def parse(argv):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    commands.register(sub)
    return parser.parse_args(argv)


def run(api, argv, context=None):
    return commands.run(parse(argv), api, BASES.get, context or {})


def adf(*paragraphs):
    return {"type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs]}


class AdfTests(unittest.TestCase):
    def test_flattens_headings_lists_tables_links_and_code(self):
        doc = {"type": "doc", "content": [
            {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Test cases"}]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [
                    {"type": "text", "text": "spec", "marks": [{"type": "link", "attrs": {"href": "https://x.test"}}]}]}]}]},
            {"type": "table", "content": [
                {"type": "tableRow", "content": [
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "#"}]}]},
                    {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Expected"}]}]}]},
                {"type": "tableRow", "content": [
                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "1"}]}]},
                    {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "ok"}]}]}]}]},
            {"type": "codeBlock", "attrs": {"language": "kotlin"}, "content": [{"type": "text", "text": "val a = 1"}]},
        ]}
        text = commands.adf_to_text(doc)
        self.assertIn("## Test cases", text)
        self.assertIn("- spec (https://x.test)", text)
        self.assertIn("| # | Expected |\n| 1 | ok |", text)
        self.assertIn("```kotlin\nval a = 1\n```", text)

    def test_text_to_adf_round_trips_paragraphs_and_line_breaks(self):
        doc = commands.text_to_adf("first\nline two\n\nsecond")
        self.assertEqual(len(doc["content"]), 2)
        self.assertEqual(commands.adf_to_text(doc).strip(), "first\nline two\n\nsecond")


class JiraTests(unittest.TestCase):
    def test_issue_is_trimmed_with_links_attachments_and_oldest_first_comments(self):
        api = FakeApi({
            ("GET", "issue/ABC-1"): {"key": "ABC-1", "fields": {
                "summary": "Add login", "status": {"name": "In Progress"}, "issuetype": {"name": "Story"},
                "description": adf("As a user"), "labels": ["auth"],
                "parent": {"key": "ABC-0", "fields": {"summary": "Epic"}},
                "issuelinks": [{"type": {"outward": "blocks", "inward": "is blocked by"},
                                "inwardIssue": {"key": "ABC-9", "fields": {"summary": "API"}}}],
                "attachment": [{"filename": "design.png", "size": 10, "mimeType": "image/png",
                                "content": "https://site.example/a/1"}],
                "customfield_10016": 3}},
            ("GET", "issue/ABC-1/comment"): {"total": 7, "comments": [
                {"id": "2", "author": {"displayName": "QA"}, "created": "t2", "body": adf("newest")},
                {"id": "1", "author": {"displayName": "PO"}, "created": "t1", "body": adf("older")}]},
        })
        result = run(api, ["jira", "issue", "ABC-1", "--comments", "2"])
        self.assertEqual(result["url"], "https://site.example/browse/ABC-1")
        self.assertEqual(result["description"], "As a user")
        self.assertEqual(result["parent"], {"key": "ABC-0", "summary": "Epic"})
        self.assertEqual(result["links"], [{"relation": "is blocked by", "key": "ABC-9", "summary": "API"}])
        self.assertEqual(result["attachments"][0]["filename"], "design.png")
        self.assertEqual(result["customfield_10016"], 3)
        self.assertEqual([c["body"] for c in result["comments"]], ["older", "newest"])
        self.assertEqual(result["comments_total"], 7)
        self.assertIn(("orderBy", "-created"), api.calls[1]["query"])

    def test_search_follows_next_page_token_until_limit(self):
        pages = iter([{"issues": [{"key": "A-1", "fields": {}}], "nextPageToken": "t"},
                      {"issues": [{"key": "A-2", "fields": {}}], "nextPageToken": "u"}])
        bodies = []

        def api(service, method, path, query=(), body=None, write=False):
            bodies.append(body)
            return {"status": 200, "pagination": {}, "data": next(pages)}

        result = run(api, ["jira", "search", "--jql", "project = A", "--limit", "2"])
        self.assertEqual([i["key"] for i in result["issues"]], ["A-1", "A-2"])
        self.assertTrue(result["truncated"])
        self.assertNotIn("nextPageToken", bodies[0])
        self.assertEqual(bodies[1]["nextPageToken"], "t")

    def test_comment_requires_write_and_sends_adf(self):
        with tempfile.TemporaryDirectory() as folder:
            body = Path(folder) / "c.txt"
            body.write_text("Plan ready")
            api = FakeApi({("POST", "issue/ABC-1/comment"): {"id": "5", "created": "now"}})
            with self.assertRaises(ValueError):
                run(api, ["jira", "comment", "ABC-1", "--body-file", str(body)])
            result = run(api, ["jira", "comment", "ABC-1", "--body-file", str(body), "--write"])
        self.assertEqual(result["comment_id"], "5")
        self.assertEqual(api.calls[-1]["body"]["body"]["type"], "doc")


class ConfluenceTests(unittest.TestCase):
    def test_page_accepts_url_and_returns_web_url(self):
        api = FakeApi({("GET", "pages/123"): {
            "id": "123", "title": "PRD", "version": {"number": 4},
            "_links": {"webui": "/spaces/X/pages/123/PRD"},
            "body": {"storage": {"value": "<p>hi</p>"}}}})
        result = run(api, ["confluence", "page", "https://site.example/wiki/spaces/X/pages/123/PRD"])
        self.assertEqual(result["url"], "https://site.example/wiki/spaces/X/pages/123/PRD")
        self.assertEqual(result["body"], "<p>hi</p>")
        self.assertEqual(result["version"], 4)

    def test_bad_page_reference_is_a_usage_error(self):
        with self.assertRaises(commands.UsageError):
            commands.page_id("https://site.example/wiki/home")


class GitLabTests(unittest.TestCase):
    def test_mr_reference_forms(self):
        url = parse(["gitlab", "mr", "get", "https://git.example/group/sub/app/-/merge_requests/12"])
        self.assertEqual(commands.resolve_mr(url, {}), ("group%2Fsub%2Fapp", "12"))
        pair = parse(["gitlab", "mr", "get", "group/app", "7"])
        self.assertEqual(commands.resolve_mr(pair, {}), ("group%2Fapp", "7"))
        bare = parse(["gitlab", "mr", "get", "7"])
        self.assertEqual(commands.resolve_mr(bare, {"GITLAB_PROJECT": "42"}), ("42", "7"))
        with self.assertRaises(commands.UsageError):
            commands.resolve_mr(bare, {})

    def test_unresolved_discussions_paginate_and_skip_system_notes(self):
        path = "projects/g%2Fa/merge_requests/3/discussions"
        api = FakeApi({("GET", path): [
            {"page": "1", "pagination": {"X-Next-Page": "2"}, "data": [
                {"id": "d1", "notes": [{"id": 1, "body": "fix", "resolvable": True, "resolved": False,
                                        "author": {"username": "rev"},
                                        "position": {"new_path": "A.kt", "new_line": 9}}]},
                {"id": "d2", "notes": [{"id": 2, "system": True, "body": "changed"}]}]},
            {"page": "2", "data": [
                {"id": "d3", "notes": [{"id": 3, "body": "done", "resolvable": True, "resolved": True}]},
                {"id": "d4", "notes": [{"id": 4, "body": "general", "resolvable": False}]}]}]})
        result = run(api, ["gitlab", "mr", "discussions", "g/a", "3", "--unresolved"])
        self.assertEqual([t["id"] for t in result], ["d1"])
        self.assertEqual(result[0]["notes"][0]["location"], "A.kt:9")
        self.assertEqual(len(api.calls), 2)

    def test_create_uses_context_target_and_leaves_project_policy_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            description = Path(folder) / "mr.md"
            description.write_text("## Change\n")
            api = FakeApi({("POST", "projects/g%2Fa/merge_requests"): {"iid": 9, "web_url": "u"}})
            result = run(api, ["gitlab", "mr", "create", "--source", "feature/A-1-x", "--title", "feat: A-1 x",
                               "--description-file", str(description), "--draft", "--write"],
                         {"GITLAB_PROJECT": "g/a", "GIT_TARGET_BRANCH": "develop"})
        body = api.calls[0]["body"]
        self.assertEqual(body["target_branch"], "develop")
        self.assertEqual(body["title"], "Draft: feat: A-1 x")
        self.assertNotIn("squash", body)
        self.assertNotIn("remove_source_branch", body)
        self.assertEqual(result["iid"], 9)

    def test_create_without_target_fails_before_any_call(self):
        api = FakeApi({})
        with self.assertRaises(commands.UsageError):
            run(api, ["gitlab", "mr", "create", "--project", "g/a", "--source", "s", "--title", "t",
                      "--description-file", "missing.md", "--write"])
        self.assertEqual(api.calls, [])

    def test_resolve_reply_and_label_are_write_guarded(self):
        api = FakeApi({("PUT", "projects/g%2Fa/merge_requests/3/discussions/d1"): {
            "id": "d1", "notes": [{"resolvable": True, "resolved": True}]},
            ("PUT", "projects/g%2Fa/merge_requests/3"): {"iid": 3, "labels": ["review"]}})
        with self.assertRaises(ValueError):
            run(api, ["gitlab", "mr", "resolve", "g/a", "3", "--discussion", "d1"])
        self.assertEqual(run(api, ["gitlab", "mr", "resolve", "g/a", "3", "--discussion", "d1", "--write"]),
                         {"id": "d1", "resolved": True})
        self.assertEqual(api.calls[-1]["query"], [("resolved", "true")])
        run(api, ["gitlab", "mr", "label", "g/a", "3", "--add", "review", "--write"])
        self.assertEqual(api.calls[-1]["body"], {"add_labels": "review"})

    def test_file_get_decodes_base64_and_encodes_path(self):
        content = base64.b64encode("plugins { }".encode()).decode()
        api = FakeApi({("GET", "projects/g%2Fa/repository/files/app%2Fbuild.gradle.kts"): {
            "file_path": "app/build.gradle.kts", "ref": "main", "encoding": "base64", "content": content}})
        result = run(api, ["gitlab", "file", "get", "app/build.gradle.kts", "--ref", "main", "--project", "g/a"])
        self.assertEqual(result["content"], "plugins { }")


class FigmaTests(unittest.TestCase):
    def test_url_supplies_file_branch_and_node_id(self):
        args = parse(["figma", "nodes", "--file",
                      "https://www.figma.com/design/KEY1/branch/BR2/App?node-id=12-34"])
        self.assertEqual(commands.figma_target(args, {}), ("BR2", ["12:34"]))

    def test_nodes_summary_is_depth_limited(self):
        api = FakeApi({("GET", "files/K/nodes"): {"name": "App", "nodes": {"1:2": {"document": {
            "id": "1:2", "name": "Login", "type": "FRAME",
            "absoluteBoundingBox": {"width": 360, "height": 800},
            "children": [{"id": "1:3", "name": "Title", "type": "TEXT", "characters": "Sign in",
                          "children": [{"id": "1:4", "name": "deep", "type": "X"}]}]}}}}})
        result = run(api, ["figma", "nodes", "--file", "K", "--ids", "1-2", "--depth", "1"])
        node = result["nodes"]["1:2"]
        self.assertEqual(node["size"], [360, 800])
        self.assertEqual(node["children"][0]["text"], "Sign in")
        self.assertNotIn("children", node["children"][0])
        self.assertEqual(api.calls[0]["query"], [("ids", "1:2")])

    def test_images_report_export_errors(self):
        api = FakeApi({("GET", "images/K"): {"err": "bad id", "images": {}}})
        with self.assertRaises(commands.UsageError):
            run(api, ["figma", "images", "--file", "K", "--ids", "1:2"])


class CliWiringTests(unittest.TestCase):
    def test_cli_runs_high_level_command_through_request_with_env_context(self):
        spec = importlib.util.spec_from_file_location("integrations_cli", SCRIPTS / "integrations.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        env = {"GITLAB_TOKEN": "secret", "GITLAB_PROJECT": "g/a"}
        with patch.dict(os.environ, env, clear=True), \
                patch.object(cli, "load_env_file"), \
                patch.object(cli, "request", return_value={"status": 200, "pagination": {},
                                                           "data": {"iid": 3, "state": "opened"}}) as request, \
                patch("sys.stdout", new_callable=io.StringIO) as output:
            code = cli.main(["gitlab", "mr", "get", "3"])
        self.assertEqual(code, 0)
        self.assertEqual(request.call_args.args[:3], ("gitlab", "GET", "projects/g%2Fa/merge_requests/3"))
        self.assertEqual(json.loads(output.getvalue())["state"], "opened")
        self.assertNotIn("secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
