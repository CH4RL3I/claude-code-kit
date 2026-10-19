import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from helpers import load


vor = load("long-run", "scripts/state-before-compact")
nach = load("long-run", "scripts/state-after-compact")


class Hooks(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.cwd = Path(self.t.name) / "proj"
        self.cwd.mkdir()
        st = Path(self.t.name) / "state"
        vor.STATE_DIR = st
        nach.STATE_DIR = st
        os.environ.pop("LONG_RUN_BLOCK_ONCE", None)

    def tearDown(self):
        self.t.cleanup()
        os.environ.pop("LONG_RUN_BLOCK_ONCE", None)

    def pl(self):
        return {"cwd": str(self.cwd), "session_id": "s1"}

    def test_no_state_no_output(self):
        self.assertIsNone(vor.decide(self.pl()))
        self.assertIsNone(nach.build(self.pl()))

    def test_no_cwd(self):
        self.assertIsNone(vor.decide({}))
        self.assertIsNone(nach.build({}))

    def test_vor_default_never_blocks_but_snapshots(self):
        (self.cwd / "STATE.md").write_text("# STATE\n")
        old = time.time() - 9999
        os.utime(self.cwd / "STATE.md", (old, old))
        self.assertIsNone(vor.decide(self.pl()))
        self.assertTrue((vor.STATE_DIR / "s1.json").exists())

    def test_vor_block_once_when_stale(self):
        os.environ["LONG_RUN_BLOCK_ONCE"] = "1"
        (self.cwd / "STATE.md").write_text("# STATE\n")
        old = time.time() - 9999
        os.utime(self.cwd / "STATE.md", (old, old))
        out = vor.decide(self.pl())
        self.assertEqual(out["decision"], "block")
        self.assertIn("STATE.md", out["reason"])
        self.assertIsNone(vor.decide(self.pl()))  # retry passes

    def test_vor_fresh_state_not_blocked(self):
        os.environ["LONG_RUN_BLOCK_ONCE"] = "1"
        (self.cwd / "STATE.md").write_text("# STATE\n")
        self.assertIsNone(vor.decide(self.pl()))

    def test_nach_injects_and_truncates(self):
        (self.cwd / ".claude").mkdir()
        (self.cwd / ".claude/STATE.md").write_text("x" * 9000)
        out = nach.build(self.pl())["hookSpecificOutput"]
        self.assertEqual(out["hookEventName"], "SessionStart")
        c = out["additionalContext"]
        self.assertTrue(c.startswith("STATE.md (source of truth after compaction):"))
        self.assertLess(len(c), 4200)

    def test_nach_stale_note(self):
        (self.cwd / "STATE.md").write_text("# STATE\nstatus")
        vor.decide(self.pl())
        c = nach.build(self.pl())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("not updated", c)
        time.sleep(0.01)
        os.utime(self.cwd / "STATE.md", (time.time() + 5, time.time() + 5))
        c = nach.build(self.pl())["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("not updated", c)


if __name__ == "__main__":
    unittest.main()
