import os, stat, subprocess, tempfile, unittest

from helpers import PY, script

HEALTH = script("mcp-health", "bin/mcp-health")
LISTING = """Checking MCP server health...

alpha: npx alpha-mcp - ✔ Connected
beta: https://beta.example/mcp (HTTP) - ! Needs authentication
gamma: node gamma.js - ✘ Failed to connect
"""


class T(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.bin = os.path.join(self.t.name, "bin")
        os.makedirs(self.bin)
        fake = os.path.join(self.bin, "claude")
        with open(fake, "w") as f:
            f.write("#!/bin/sh\ncat <<'EOT'\n" + LISTING + "EOT\n")
        os.chmod(fake, os.stat(fake).st_mode | stat.S_IXUSR)

    def tearDown(self):
        self.t.cleanup()

    def run_cli(self, *args, **env):
        e = dict(os.environ, HOME=self.t.name, PATH=self.bin + ":" + os.environ["PATH"],
                 MCP_HEALTH_HOME=os.path.join(self.t.name, "state"))
        for k in ("MCP_HEALTH_IGNORE", "MCP_HEALTH_PROXY_PORT", "MCP_HEALTH_PROXY_LOG"):
            e.pop(k, None)
        e.update(env)
        return subprocess.run([PY, HEALTH, *args], capture_output=True, text=True, env=e)

    def test_table_and_exit_code(self):
        r = self.run_cli()
        self.assertEqual(r.returncode, 1)
        self.assertIn("alpha", r.stdout)
        self.assertRegex(r.stdout, r"! beta\s+needs login")
        self.assertRegex(r.stdout, r"✘ gamma\s+broken")

    def test_ignore_file(self):
        ign = os.path.join(self.t.name, "ign.txt")
        open(ign, "w").write("# deliberately unused\nbeta\ngamma\n")
        r = self.run_cli(MCP_HEALTH_IGNORE=ign)
        self.assertEqual(r.returncode, 0)
        self.assertIn("(ignored)", r.stdout)

    def test_proxy_down_is_reported(self):
        r = self.run_cli(MCP_HEALTH_PROXY_PORT="9")
        self.assertIn("shared proxy :9", r.stdout)
        self.assertIn("down", r.stdout)

    def test_no_proxy_line_by_default(self):
        self.assertNotIn("shared proxy", self.run_cli().stdout)

    def test_notify_writes_log(self):
        r = self.run_cli("--notify")
        self.assertEqual(r.returncode, 0)
        log = open(os.path.join(self.t.name, "state", "health.log")).read()
        self.assertIn("attention=2", log)

    def test_unparseable(self):
        with open(os.path.join(self.bin, "claude"), "w") as f:
            f.write("#!/bin/sh\necho nothing useful\n")
        self.assertEqual(self.run_cli().returncode, 2)


if __name__ == "__main__":
    unittest.main()
