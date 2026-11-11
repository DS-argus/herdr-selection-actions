import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("open_url", Path(__file__).with_name("open_url.py"))
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


class OpenURLTests(unittest.TestCase):
    def setUp(self):
        platform = patch.object(plugin.sys, "platform", "darwin")
        platform.start()
        self.addCleanup(platform.stop)
        config = patch.dict(os.environ, HERDR_PLUGIN_CONFIG_DIR="")
        config.start()
        self.addCleanup(config.stop)

    def test_provider_configuration(self):
        import tempfile
        from urllib.parse import parse_qs, urlsplit
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, HERDR_PLUGIN_CONFIG_DIR=directory):
            path = Path(directory) / "config.toml"
            self.assertEqual(plugin.search_provider(), "google")
            path.write_text('[search]\nprovider = "duckduckgo"\n')
            provider = plugin.search_provider()
            parsed = urlsplit(plugin.search_url("한글 & private?", provider))
            self.assertEqual(parsed.netloc, "duckduckgo.com")
            self.assertEqual(parse_qs(parsed.query), {"q": ["한글 & private?"]})
            for invalid in ('[search]\nprovider="typo"', '[search]\nprovider=3', 'search=1', '[search]\nunknown=true', '[other]\nx=1', '['):
                path.write_text(invalid)
                with self.assertRaises(plugin.SelectionError):
                    plugin.search_provider()

    def test_linux_opener_and_missing_desktop(self):
        with patch.object(plugin.sys, "platform", "linux"), patch.object(plugin.shutil, "which", return_value="/usr/bin/xdg-open"), patch.dict(os.environ, DISPLAY=":99", WAYLAND_DISPLAY=""), patch.object(subprocess, "run") as run:
            plugin.open_browser("https://example.com/?a=1&b=2")
            run.assert_called_once_with(["/usr/bin/xdg-open", "https://example.com/?a=1&b=2"], check=True, timeout=10, capture_output=True)
            run.reset_mock()
            with patch.dict(os.environ, DISPLAY="", WAYLAND_DISPLAY=""):
                with self.assertRaises(plugin.SelectionError):
                    plugin.open_browser("https://example.com")
            run.assert_not_called()
            with patch.object(plugin.shutil, "which", return_value=None):
                with self.assertRaises(plugin.SelectionError):
                    plugin.open_browser("https://example.com")
            run.assert_not_called()

    def test_unsupported_platform(self):
        with patch.object(plugin.sys, "platform", "win32"), patch.object(subprocess, "run") as run:
            with self.assertRaises(plugin.SelectionError):
                plugin.open_browser("https://example.com")
            run.assert_not_called()
    def test_valid_addresses(self):
        for url in (
            "https://example.com", "http://localhost:3000/a?b=1#top",
            "https://127.0.0.1:8080", "https://[::1]:443/a",
            "HTTPS://example.com/path", "https://예시.한국/문서",
            "https://example.com/a%20b?q=hello&sort=asc",
        ):
            with self.subTest(url=url):
                self.assertEqual(plugin.validate_url("  " + url + "  "), url)

    def test_invalid_selection(self):
        for text in (
            None, 123, "", "   ", "https://", "https:///path",
            "example.com", "file:///tmp/a", "javascript:alert(1)",
            "ftp://example.com", "--help", "https://one.test https://two.test",
            "https://example.com\n", "https://exam\tple.com", "https://example.com/\x00",
            "https://example.com/\x1b[31m", "https://example.com/\u202e",
            "https://example.com\\@evil.test", "https://user:pass@example.com",
            "https://example.com:bad", "https://example.com:65536", "https://example.com:0",
            "https://example.com:", "https://[invalid]", "https://bad..host",
            "https://-bad.test", "<https://example.com>", '"https://example.com"',
            "https://example.com/" + "x" * 8192,
        ):
            with self.subTest(text=text), self.assertRaises(plugin.SelectionError):
                plugin.validate_url(text)

    def test_opener_receives_one_literal_argument(self):
        url = "https://example.com/?q=$(id);x='test'&other=1"
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON=json.dumps({"selected_text": url})), patch.object(subprocess, "run") as run:
            plugin.open_selected_url()
        run.assert_called_once_with(["/usr/bin/open", url], check=True, timeout=10, capture_output=True)

    def test_invalid_selection_never_calls_opener(self):
        for context in ("{}", "[]", "not json", '{"selected_text":"file:///tmp/test"}'):
            with self.subTest(context=context), patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON=context), patch.object(subprocess, "run") as run:
                with self.assertRaises(plugin.SelectionError):
                    plugin.open_selected_url()
                run.assert_not_called()

    def test_failure_notifications_do_not_leak_url(self):
        url = "https://example.com/?token=private"
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON=json.dumps({"selected_text": url})), patch.object(subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["open", url])), patch.object(plugin, "notify") as notify:
            self.assertEqual(plugin.main(), 1)
            self.assertNotIn(url, notify.call_args.args[0])
            self.assertNotIn("private", notify.call_args.args[0])

    def test_empty_selection_is_reported(self):
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON="{}"), patch.object(plugin, "notify") as notify:
            self.assertEqual(plugin.main(), 1)
            notify.assert_called_once()


    def test_search_encodes_one_query_parameter(self):
        from urllib.parse import parse_qs, urlsplit
        text = "  한글 오류\n메시지 & # + $(id); \"quote\"\tend  "
        url = urlsplit(plugin.search_url(text))
        self.assertEqual((url.scheme, url.netloc, url.path), ("https", "www.google.com", "/search"))
        self.assertEqual(parse_qs(url.query), {"q": ['한글 오류 메시지 & # + $(id); "quote" end']})
        self.assertEqual(url.fragment, "")

    def test_search_rejects_empty_controls_and_oversize(self):
        for text in (None, 42, "", " \n\t ", "bad\x00", "bad\x1b", "bad\u202e", "x" * 2049):
            with self.subTest(text=text), self.assertRaises(plugin.SelectionError):
                plugin.search_url(text)
        self.assertIn("q=", plugin.search_url("x" * 2048))

    def test_search_is_explicit_and_uses_argv(self):
        text = "file:///tmp/example &debug=1"
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON=json.dumps({"selected_text": text})), patch.object(subprocess, "run") as run:
            self.assertEqual(plugin.main("search"), 0)
            run.assert_called_once_with(["/usr/bin/open", plugin.search_url(text)], check=True, timeout=10, capture_output=True)
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON=json.dumps({"selected_text": text})), patch.object(subprocess, "run") as run, patch.object(plugin, "notify"):
            self.assertEqual(plugin.main("open"), 1)
            run.assert_not_called()

    def test_manifest_and_config_bind_independent_actions(self):
        import tomllib
        root = Path(__file__).parent
        manifest = tomllib.loads((root / "herdr-plugin.toml").read_text())
        actions = {action["id"]: action for action in manifest["actions"]}
        self.assertEqual(actions["open"]["command"], ["python3", "open_url.py", "open"])
        self.assertEqual(actions["search"]["command"], ["python3", "open_url.py", "search"])
        config = tomllib.loads((root / "keybindings.example.toml").read_text())
        bindings = {entry["key"]: entry for entry in config["keys"]["command"]}
        self.assertEqual(bindings["prefix+shift+o"]["command"], "ds-argus.selection-actions.open")
        self.assertEqual(bindings["prefix+shift+s"]["command"], "ds-argus.selection-actions.search")
        for key in ("prefix+shift+o", "prefix+shift+s"):
            self.assertEqual(bindings[key]["type"], "plugin_action")
    def test_error_toast_inherits_global_position(self):
        with patch.dict(os.environ, HERDR_PLUGIN_CONTEXT_JSON="{}", HERDR_BIN_PATH="/test/herdr"), patch.object(subprocess, "run") as run, patch("sys.stderr"):
            self.assertEqual(plugin.main("open"), 1)
        run.assert_called_once_with(
            ["/test/herdr", "notification", "show", "Selection actions", "--body",
             "Select one HTTP(S) URL first."],
            timeout=5, capture_output=True, check=True,
        )

    def test_validation_messages_are_english(self):
        for function, value in ((plugin.validate_url, None), (plugin.validate_url, "file:///tmp/a"),
                                (plugin.validate_url, "https://example.com\n"),
                                (plugin.validate_url, "https://user:pass@example.com"),
                                (plugin.search_url, None), (plugin.search_url, "x" * 2049),
                                (plugin.search_url, "text\x00")):
            with self.subTest(value=value):
                with self.assertRaises(plugin.SelectionError) as error:
                    function(value)
                self.assertTrue(str(error.exception).isascii())

if __name__ == "__main__":
    unittest.main()
