import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "integrations.py"
spec = importlib.util.spec_from_file_location("integrations", SCRIPT)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.service = {"base_url": "https://git.example/api/v4",
                        "auth": "private-token", "token_env": "GITLAB_TOKEN"}
        self.env = patch.dict(os.environ, {"GITLAB_TOKEN": "test-secret",
                                           "GITLAB_BASE_URL": "https://git.example/api/v4"},
                              clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_doctor_is_offline_and_never_reports_secret(self):
        with patch.object(cli.urllib.request, "build_opener") as opener:
            result = cli.doctor()
        opener.assert_not_called()
        self.assertEqual(result["services"]["gitlab"]["state"], "configured-unverified")
        self.assertNotIn("test-secret", json.dumps(result))

    def test_missing_token_disables_and_insecure_base_is_incomplete(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.doctor()["services"]["gitlab"]["state"], "disabled")
        with patch.dict(os.environ, {"GITLAB_BASE_URL": "http://git.example/api/v4"}):
            self.assertEqual(cli.doctor()["services"]["gitlab"]["state"], "incomplete")

    def test_unconfigured_service_cannot_make_requests(self):
        del os.environ["GITLAB_TOKEN"]
        with patch.object(cli.urllib.request, "build_opener") as opener:
            with self.assertRaises(ValueError):
                cli.request("gitlab", "GET", "projects/1")
        opener.assert_not_called()

    def test_write_guard_prevents_network_call(self):
        with patch.object(cli.urllib.request, "build_opener") as opener:
            with self.assertRaises(ValueError):
                cli.request("gitlab", "POST", "projects/1", body={"title": "MR"})
        opener.assert_not_called()

    def test_paths_cannot_change_origin_or_escape_api_prefix(self):
        for path in ("https://other.test/x", "//other.test/x", "../x", "%2e%2e/x",
                     "%252e%252e/x", "x/../../x", "x?token=s", "x#fragment", "\\other"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                cli.build_url(self.service["base_url"], path, [])
        self.assertEqual(cli.build_url(self.service["base_url"], "projects/group%2Frepo",
                                       [("search", "a & b")]),
                         "https://git.example/api/v4/projects/group%2Frepo?search=a+%26+b")

    def test_provider_auth_modes(self):
        with patch.dict(os.environ, {"TEST_EMAIL": "test@example.test"}):
            for auth, header, prefix in (("private-token", "PRIVATE-TOKEN", "test-secret"),
                                         ("figma-token", "X-Figma-Token", "test-secret"),
                                         ("bearer", "Authorization", "Bearer test-secret"),
                                         ("basic", "Authorization", "Basic ")):
                service = {**self.service, "auth": auth, "username_env": "TEST_EMAIL"}
                self.assertTrue(cli.headers_for(service)[header].startswith(prefix))

    def test_request_preserves_json_and_pagination_without_retry(self):
        class Response:
            status = 200
            headers = {"X-Next-Page": "2"}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b'[{"id": 1}]'
        with patch.object(cli.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = Response()
            result = cli.request("gitlab", "GET", "projects")
            build.return_value.open.assert_called_once()
            sent = build.return_value.open.call_args.args[0]
            self.assertEqual(sent.get_header("Private-token"), "test-secret")
        self.assertEqual(result["data"], [{"id": 1}])
        self.assertEqual(result["pagination"], {"X-Next-Page": "2"})

    def test_http_errors_omit_provider_body_and_do_not_retry(self):
        error = urllib.error.HTTPError("https://git.example/api/v4/projects", 401,
                                       "Unauthorized", {}, io.BytesIO(b"test-secret"))
        with patch.object(cli.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = error
            with self.assertRaisesRegex(ValueError, "HTTP 401") as raised:
                cli.request("gitlab", "GET", "projects")
            build.return_value.open.assert_called_once()
        self.assertNotIn("test-secret", str(raised.exception))

    def test_basic_auth_is_selected_when_email_is_set(self):
        with patch.dict(os.environ, {"JIRA_API_TOKEN": "t", "JIRA_EMAIL": "a@example.test",
                                     "JIRA_BASE_URL": "https://site.example/rest/api/3",
                                     "JIRA_PROJECT_KEY": "ABC"}):
            result = cli.doctor()
        self.assertEqual(result["services"]["jira"], {"state": "configured-unverified", "auth": "basic"})
        self.assertEqual(result["services"]["figma"]["state"], "disabled")
        self.assertEqual(result["context"], {"JIRA_PROJECT_KEY": "ABC"})

    def test_missing_base_url_is_incomplete(self):
        with patch.dict(os.environ, {"JIRA_API_TOKEN": "t"}):
            result = cli.doctor()
        self.assertEqual(result["services"]["jira"]["state"], "incomplete")
        self.assertIn("JIRA_BASE_URL", result["services"]["jira"]["reason"])

    def test_redirect_does_not_forward_credentials(self):
        self.assertIsNone(cli.NoRedirect().redirect_request(None, None, 302, "", {},
                                                            "https://other.test/"))

    def test_authorized_write_sends_json_once_and_handles_empty_response(self):
        class Response:
            status = 204
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b""
        with patch.object(cli.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = Response()
            result = cli.request("gitlab", "POST", "projects/1/merge_requests",
                                 body={"title": "Feature"}, write=True)
            build.return_value.open.assert_called_once()
            sent = build.return_value.open.call_args.args[0]
            self.assertEqual(sent.get_method(), "POST")
            self.assertEqual(json.loads(sent.data), {"title": "Feature"})
            self.assertEqual(sent.get_header("Content-type"), "application/json")
        self.assertEqual(result["status"], 204)
        self.assertIsNone(result["data"])

    def test_timed_out_write_is_never_retried(self):
        with patch.object(cli.urllib.request, "build_opener") as build:
            build.return_value.open.side_effect = TimeoutError()
            with self.assertRaisesRegex(ValueError, "verify before retrying"):
                cli.request("gitlab", "POST", "projects/1/merge_requests",
                            body={"title": "Feature"}, write=True)
            build.return_value.open.assert_called_once()

    def test_cli_reports_http_status_without_secret_body(self):
        error = urllib.error.HTTPError("https://git.example/api/v4/projects", 403,
                                       "Forbidden", {}, io.BytesIO(b"test-secret"))
        with patch.object(cli, "load_env_file"), \
                patch.object(cli.urllib.request, "build_opener") as build, \
                patch("sys.stderr", new_callable=io.StringIO) as output:
            build.return_value.open.side_effect = error
            code = cli.main(["request", "gitlab", "GET", "projects"])
        self.assertEqual(code, 1)
        self.assertIn("HTTP 403", output.getvalue())
        self.assertNotIn("test-secret", output.getvalue())

    def test_invalid_tls_or_userinfo_configuration_is_rejected(self):
        for base in ("http://git.example/api", "https://user:secret@git.example/api",
                     "https://git.example/api?token=secret"):
            with self.subTest(base=base), self.assertRaises(ValueError):
                cli.validate_base(base)

    def test_local_env_loads_only_configured_credentials_without_overriding_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("GITLAB_TOKEN='local'\nexport TEST_EMAIL='user@example.test'\nDEBUG=true\n")
            cli.load_env_file(path, {'GITLAB_TOKEN', 'TEST_EMAIL'})
        self.assertEqual(os.environ['GITLAB_TOKEN'], 'test-secret')
        self.assertEqual(os.environ['TEST_EMAIL'], 'user@example.test')
        self.assertNotIn('DEBUG', os.environ)

    def test_env_is_not_executed_and_does_not_expand_variables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            sentinel = Path(directory) / 'must-not-exist'
            value = f'$(touch {sentinel}) $HOME'
            path.write_text(f"TEST_VALUE='{value}'\n")
            cli.load_env_file(path, {'TEST_VALUE'})
            self.assertFalse(sentinel.exists())
        self.assertEqual(os.environ['TEST_VALUE'], value)

    def test_invalid_env_does_not_partially_load_or_print_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("TEST_EMAIL='user@example.test'\nTEST_VALUE='secret-value\n")
            with self.assertRaises(cli.CommandError) as raised:
                cli.load_env_file(path, {'TEST_EMAIL', 'TEST_VALUE'})
        self.assertNotIn('TEST_EMAIL', os.environ)
        self.assertNotIn('secret-value', str(raised.exception))

    def test_cli_doctor_uses_local_env_without_shell_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("GITLAB_TOKEN='from-file'\n")
            with patch.dict(os.environ, {}, clear=True), \
                    patch('sys.stdout', new_callable=io.StringIO) as output:
                code = cli.main(['--env-file', str(path), 'doctor'])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(result['services']['gitlab']['state'], 'configured-unverified')
        self.assertNotIn('from-file', output.getvalue())


if __name__ == "__main__":
    unittest.main()
