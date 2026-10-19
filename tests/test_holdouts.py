import json, os, subprocess, tempfile, unittest

from helpers import PY, script


def guard(payload, raw=None):
    inp = raw if raw is not None else json.dumps(payload)
    r = subprocess.run([PY, script("holdouts", "scripts/holdout-guard")], input=inp, capture_output=True, text=True)
    return r.returncode, r.stdout


def denied(out):
    return bool(out) and json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "deny"


class Guard(unittest.TestCase):
    def test_main_allowed(self):
        rc, out = guard({"tool_name": "Read", "tool_input": {"file_path": "/home/x/.holdouts/p/s.md"}})
        self.assertEqual((rc, out), (0, ""))

    def test_builder_blocked_read_and_bash(self):
        for tn, ti in [("Read", {"file_path": "/home/x/.holdouts/p/s.md"}),
                       ("Bash", {"command": "cat ~/.holdouts/p/s.md"}),
                       ("Grep", {"pattern": "x", "path": "/home/x/.holdouts"}),
                       ("Write", {"file_path": "/home/x/.holdouts/a.md", "content": "x"}),
                       ("Bash", {"command": "holdout path p s"})]:
            rc, out = guard({"agent_id": "a1", "agent_type": "general-purpose", "tool_name": tn, "tool_input": ti})
            self.assertEqual(rc, 0)
            self.assertTrue(denied(out), (tn, out))

    def test_validator_allowed(self):
        rc, out = guard({"agent_id": "a1", "agent_type": "holdout-validator", "tool_name": "Read",
                         "tool_input": {"file_path": "/home/x/.holdouts/p/s.md"}})
        self.assertEqual((rc, out), (0, ""))

    def test_namespaced_validator_allowed(self):
        rc, out = guard({"agent_id": "a1", "agent_type": "holdouts:holdout-validator", "tool_name": "Read",
                         "tool_input": {"file_path": "/home/x/.holdouts/p/s.md"}})
        self.assertEqual((rc, out), (0, ""))

    def test_custom_dir_blocked(self):
        env = dict(os.environ, HOLDOUTS_DIR="/srv/secret-scenarios")
        r = subprocess.run([PY, script("holdouts", "scripts/holdout-guard")], capture_output=True, text=True, env=env,
                           input=json.dumps({"agent_id": "a1", "agent_type": "general-purpose", "tool_name": "Read",
                                             "tool_input": {"file_path": "/srv/secret-scenarios/p/s.md"}}))
        self.assertTrue(denied(r.stdout))

    def test_unrelated_allowed(self):
        rc, out = guard({"agent_id": "a1", "agent_type": "general-purpose", "tool_name": "Bash",
                         "tool_input": {"command": "ls /tmp && echo holdouts are great"}})
        self.assertEqual((rc, out), (0, ""))

    def test_garbage(self):
        for raw in ["", "not json", "[]", "null", '{"agent_id": 5, "tool_input": 3}']:
            rc, out = guard(None, raw=raw)
            self.assertEqual((rc, out), (0, ""), raw)


class Cli(unittest.TestCase):
    def run_cli(self, home, *args, stdin=""):
        env = dict(os.environ, HOME=home)
        env.pop("HOLDOUTS_DIR", None)
        return subprocess.run([PY, script("holdouts", "bin/holdout"), *args], input=stdin, capture_output=True, text=True, env=env)

    def test_add_ls_path(self):
        with tempfile.TemporaryDirectory() as h:
            r = self.run_cli(h, "add", "proj", "feat-1", stdin="# S1\nGiven x")
            self.assertEqual(r.returncode, 0, r.stderr)
            p = os.path.join(h, ".holdouts", "proj", "feat-1.md")
            self.assertEqual(r.stdout.strip(), p)
            self.assertEqual(open(p).read(), "# S1\nGiven x")
            self.assertEqual(oct(os.stat(os.path.dirname(p)).st_mode & 0o777), "0o700")
            self.run_cli(h, "add", "other", "z", stdin="y")
            self.assertEqual(self.run_cli(h, "ls", "proj").stdout.split(), ["proj/feat-1"])
            self.assertEqual(self.run_cli(h, "ls").stdout.split(), ["other/z", "proj/feat-1"])
            self.assertEqual(self.run_cli(h, "path", "proj", "feat-1").stdout.strip(), p)
            self.assertNotEqual(self.run_cli(h, "path", "proj", "nope").returncode, 0)

    def test_custom_dir(self):
        with tempfile.TemporaryDirectory() as h:
            env = dict(os.environ, HOME=h, HOLDOUTS_DIR=os.path.join(h, "elsewhere"))
            r = subprocess.run([PY, script("holdouts", "bin/holdout"), "add", "p", "s"], input="x",
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.stdout.strip(), os.path.join(h, "elsewhere", "p", "s.md"))

    def test_rejects_bad_names_and_empty(self):
        with tempfile.TemporaryDirectory() as h:
            self.assertNotEqual(self.run_cli(h, "add", "../x", "s", stdin="a").returncode, 0)
            self.assertNotEqual(self.run_cli(h, "add", "p", "s", stdin="  ").returncode, 0)
            self.assertEqual(self.run_cli(h, "ls").stdout, "")


if __name__ == "__main__":
    unittest.main()
