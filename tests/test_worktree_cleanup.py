import json, os, subprocess, tempfile, unittest

from helpers import PY, script

CLEAN = script("worktree-cleanup", "scripts/worktree-cleanup")


def sh(*cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       env=dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@e.x",
                                GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@e.x"))
    assert r.returncode == 0, (cmd, r.stderr)
    return r.stdout


class T(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        base = os.path.realpath(self.t.name)
        self.root = os.path.join(base, "code")
        self.home = os.path.join(base, "home")
        os.makedirs(self.root)
        os.makedirs(self.home)
        remote = os.path.join(base, "remote.git")
        sh("git", "init", "-q", "--bare", "-b", "main", remote)
        self.repo = os.path.join(self.root, "app")
        sh("git", "init", "-q", "-b", "main", self.repo)
        sh("git", "remote", "add", "origin", remote, cwd=self.repo)
        open(os.path.join(self.repo, "a.txt"), "w").write("a")
        sh("git", "add", "a.txt", cwd=self.repo)
        sh("git", "commit", "-q", "-m", "init", cwd=self.repo)
        sh("git", "push", "-q", "-u", "origin", "main", cwd=self.repo)
        self.wt = {}
        for name in ("pushed", "unpushed", "dirty"):
            p = os.path.join(base, "wt-" + name)
            sh("git", "worktree", "add", "-q", "-b", name, p, cwd=self.repo)
            self.wt[name] = p
        sh("git", "push", "-q", "-u", "origin", "pushed", cwd=self.wt["pushed"])
        sh("git", "push", "-q", "-u", "origin", "unpushed", cwd=self.wt["unpushed"])
        open(os.path.join(self.wt["unpushed"], "b.txt"), "w").write("b")
        sh("git", "add", "b.txt", cwd=self.wt["unpushed"])
        sh("git", "commit", "-q", "-m", "local", cwd=self.wt["unpushed"])
        open(os.path.join(self.wt["dirty"], "u.txt"), "w").write("untracked")

    def tearDown(self):
        self.t.cleanup()

    def run_cli(self, *args, roots=True, stdin="", idle_hours="0"):
        env = dict(os.environ, HOME=self.home, WORKTREE_CLEANUP_IDLE_HOURS=idle_hours)
        env.pop("WORKTREE_CLEANUP_ROOTS", None)
        if roots:
            env["WORKTREE_CLEANUP_ROOTS"] = self.root
        return subprocess.run([PY, CLEAN, *args], input=stdin, capture_output=True, text=True, env=env)

    def test_no_roots_does_nothing(self):
        r = self.run_cli(roots=False)
        self.assertIn("no scan roots", r.stdout)
        self.assertTrue(os.path.isdir(self.wt["pushed"]))

    def test_dry_run_verdicts(self):
        out = self.run_cli().stdout
        self.assertIn("would remove: " + self.wt["pushed"], out)
        self.assertIn("keep: " + self.wt["unpushed"], out)
        self.assertIn("1 commits not pushed", out)
        self.assertIn("keep: " + self.wt["dirty"], out)
        for p in self.wt.values():
            self.assertTrue(os.path.isdir(p))

    def test_really_removes_only_clean_pushed(self):
        self.run_cli("--really")
        self.assertFalse(os.path.isdir(self.wt["pushed"]))
        self.assertTrue(os.path.isdir(self.wt["unpushed"]))
        self.assertTrue(os.path.isdir(self.wt["dirty"]))
        self.assertIn("pushed", sh("git", "branch", cwd=self.repo))  # branch kept

    def test_recently_used_is_kept(self):
        self.assertIn("h ago", self.run_cli(idle_hours="24").stdout)
        self.run_cli("--really", idle_hours="24")
        self.assertTrue(os.path.isdir(self.wt["pushed"]))

    def test_locked_is_kept(self):
        sh("git", "worktree", "lock", self.wt["pushed"], cwd=self.repo)
        self.assertIn("keep: " + self.wt["pushed"] + " (locked)", self.run_cli().stdout)

    def test_hook_ignores_non_push(self):
        r = self.run_cli("hook", stdin=json.dumps({"hook_event_name": "PostToolUse",
                                                   "tool_input": {"command": "ls"}}))
        self.assertEqual(r.returncode, 0)
        import time; time.sleep(0.5)
        self.assertTrue(os.path.isdir(self.wt["pushed"]))

    def test_hook_after_push_cleans_in_background(self):
        r = self.run_cli("hook", stdin=json.dumps({"hook_event_name": "PostToolUse",
                                                   "tool_input": {"command": "git push"}}))
        self.assertEqual(r.returncode, 0)
        import time
        for _ in range(50):
            if not os.path.isdir(self.wt["pushed"]):
                break
            time.sleep(0.2)
        self.assertFalse(os.path.isdir(self.wt["pushed"]))
        self.assertTrue(os.path.isdir(self.wt["dirty"]))

    def test_roots_file(self):
        os.makedirs(os.path.join(self.home, ".config", "worktree-cleanup"))
        with open(os.path.join(self.home, ".config", "worktree-cleanup", "roots.txt"), "w") as f:
            f.write("# mine\n" + self.root + "\n")
        self.assertIn("would remove", self.run_cli(roots=False).stdout)


if __name__ == "__main__":
    unittest.main()
