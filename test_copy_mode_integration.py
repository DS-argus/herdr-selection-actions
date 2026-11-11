"""Opt-in real Herdr/PTY test; only the macOS browser opener is replaced.
Run: RUN_HERDR_INTEGRATION=1 python3 -m unittest discover -s <plugin-dir>
"""
import json
import os
from pathlib import Path
import pty
import select
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import termios
import fcntl
import time
import unittest
from urllib.parse import parse_qs, urlsplit


@unittest.skipUnless(os.environ.get("RUN_HERDR_INTEGRATION") == "1", "opt-in isolated Herdr test")
class CopyModeIntegration(unittest.TestCase):
    def test_selection_reaches_both_actions_and_survives_first_action(self):
        binary = shutil.which("herdr")
        self.assertIsNotNone(binary)
        source = str(Path(__file__).with_name("open_url.py").resolve())
        text = "https://example.com/test?q=1"
        with tempfile.TemporaryDirectory(prefix="url-qa-", dir="/tmp") as temp:
            root = Path(temp)
            for name in ("home", "config", "state", "data"):
                (root / name).mkdir()
            output_file = root / "opened.jsonl"
            shell = root / "shell"
            shell.write_text("#!/usr/bin/env python3\nimport signal,sys\nsys.stdout.write(" + repr("\x1b[2J\x1b[H" + text) + ");sys.stdout.flush()\nsignal.pause()\n")
            shell.chmod(0o755)
            # Load the actual implementation, recording only calls to open.
            runner = root / "runner.py"
            runner.write_text(
                "import importlib.util,json,os,sys\n"
                f"spec=importlib.util.spec_from_file_location('tested', {source!r})\n"
                "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\n"
                "real_run=m.subprocess.run\n"
                "def run(args,**kw):\n"
                " if args[0]=='/usr/bin/open':\n"
                f"  with open({str(output_file)!r},'a') as f:f.write(json.dumps(args)+'\\n')\n"
                "  return m.subprocess.CompletedProcess(args,0)\n"
                " return real_run(args,**kw)\n"
                "m.subprocess.run=run\nsys.exit(m.main(sys.argv[1]))\n"
            )
            (root / "herdr-plugin.toml").write_text(
                'id="qa.selection"\nname="Selection test"\nversion="1.0.0"\nmin_herdr_version="0.9.5"\nplatforms=["macos"]\n' +
                ''.join(f'\n[[actions]]\nid="{action}"\ntitle="{action}"\ncontexts=["pane"]\ncommand=["python3",{json.dumps(str(runner))},"{action}"]\n' for action in ("open", "search"))
            )
            config = root / "config.toml"
            config.write_text(
                f'onboarding=false\n[terminal]\ndefault_shell={json.dumps(str(shell))}\n'
                '[update]\nversion_check=false\nmanifest_check=false\n[keys]\nprefix="ctrl+a"\n' +
                ''.join(f'\n[[keys.command]]\nkey="prefix+shift+{key}"\ntype="plugin_action"\ncommand="qa.selection.{action}"\n' for key, action in (("o", "open"), ("s", "search")))
            )
            env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_")}
            env.update(HOME=str(root / "home"), XDG_CONFIG_HOME=str(root / "config"),
                       XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"),
                       HERDR_CONFIG_PATH=str(config), TERM="xterm-256color", SHELL=str(shell))
            sock = root / "config/herdr/sessions/test/herdr.sock"
            server = None
            client = None
            fd = None
            with (root / "process.log").open("wb") as log:
                try:
                    server = subprocess.Popen([binary, "--session", "test", "server"], env=env,
                                              stdout=log, stderr=log, start_new_session=True)
                    deadline = time.monotonic() + 10
                    while not sock.exists():
                        if time.monotonic() > deadline or server.poll() is not None:
                            self.fail("test server did not start")
                        time.sleep(0.05)
                    link = subprocess.run([binary, "--session", "test", "plugin", "link", str(root)],
                                          env=env, stdout=log, stderr=log, timeout=10)
                    self.assertEqual(link.returncode, 0)
                    client, fd = pty.fork()
                    if client == 0:
                        os.execve(binary, [binary, "--session", "test"], env)
                    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
                    rendered = bytearray()
                    def pump_until(condition, timeout=8):
                        end = time.monotonic() + timeout
                        while time.monotonic() < end:
                            if select.select([fd], [], [], 0.05)[0]:
                                try:
                                    rendered.extend(os.read(fd, 65536))
                                except OSError:
                                    pass
                            if condition():
                                return
                        self.fail("PTY timeout: " + repr(bytes(rendered[-1200:])))
                    def settle():
                        start = time.monotonic()
                        pump_until(lambda: time.monotonic() - start >= 0.2, 1)
                    def opens():
                        return [json.loads(line) for line in output_file.read_text().splitlines()] if output_file.exists() else []
                    pump_until(lambda: text.encode() in rendered)
                    os.write(fd, b"\x01["); settle()
                    os.write(fd, b"0v$"); settle()
                    os.write(fd, b"\x01O")
                    pump_until(lambda: len(opens()) == 1)
                    self.assertEqual(opens()[0], ["/usr/bin/open", text])
                    # Do not re-enter copy mode or reselect: selection must survive.
                    os.write(fd, b"\x01S")
                    pump_until(lambda: len(opens()) == 2)
                    searched = urlsplit(opens()[1][1])
                    self.assertEqual(searched.netloc, "www.google.com")
                    self.assertEqual(parse_qs(searched.query), {"q": [text]})
                finally:
                    # All processes and registration belong to this temporary HOME.
                    # No default user server, configuration, or browser is touched.
                    if client:
                        try:
                            os.kill(client, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        os.waitpid(client, 0)
                    if fd is not None:
                        os.close(fd)
                    if server and server.poll() is None:
                        os.killpg(server.pid, signal.SIGKILL)
                        server.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
