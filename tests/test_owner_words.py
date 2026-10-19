import json, os, subprocess, tempfile, unittest

from helpers import PY, script

HOOK = script("owner-words", "scripts/owner-words")
M = "FROM THE USER, word for word:"


def u(content, **kw):
    return {"type": "user", "message": {"role": "user", "content": content}, **kw}


class T(unittest.TestCase):
    def run_hook(self, entries, tool="Agent", field="prompt", text="do x", path=True, env=None):
        extra = env or {}
        env = {k: v for k, v in os.environ.items() if k != "OWNER_WORDS_NAME"}
        env.update(extra)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "t.jsonl")
        if entries is not None:
            with open(p, "w") as f:
                for e in entries:
                    f.write(json.dumps(e) + "\n")
        inp = {"tool_name": tool, "tool_input": {field: text, "description": "d"},
               "transcript_path": p if path else "/nonexistent"}
        r = subprocess.run([PY, HOOK], input=json.dumps(inp), capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0)
        return json.loads(r.stdout)["hookSpecificOutput"]["updatedInput"] if r.stdout else None

    def test_string(self):
        o = self.run_hook([u("hello world")])
        self.assertTrue(o["prompt"].startswith(M + ' "hello world"'))
        self.assertTrue(o["prompt"].endswith("do x"))
        self.assertEqual(o["description"], "d")

    def test_blocks(self):
        o = self.run_hook([u([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}])])
        self.assertIn('"a\nb"', o["prompt"])

    def test_skips(self):
        o = self.run_hook([u("real"),
                           u([{"type": "tool_result", "content": "x"}]),
                           u("meta", isMeta=True),
                           u("<task-notification>x</task-notification>"),
                           u("<system-reminder>only</system-reminder>")])
        self.assertIn('"real"', o["prompt"])

    def test_reminder_stripped(self):
        o = self.run_hook([u("please<system-reminder>secret</system-reminder> go")])
        self.assertNotIn("secret", o["prompt"])
        self.assertIn("please", o["prompt"])

    def test_marker_present(self):
        self.assertIsNone(self.run_hook([u("x")], text=M + " already"))

    def test_other_tool(self):
        self.assertIsNone(self.run_hook([u("x")], tool="Bash", field="command"))

    def test_sendmessage(self):
        o = self.run_hook([u("x")], tool="SendMessage", field="message")
        self.assertTrue(o["message"].startswith(M))

    def test_redaction(self):
        o = self.run_hook([u("key sk-abcdefghijklmnopqrstuvwxyz1234 and ghp_abcdefghij1234 op://V/i/f AKIAABCDEFGHIJKLMNOP " + "aB3dE5gH7jK9mN1pQ3sT5vW7yZ9bC2dE4fG6hJ8kL0")])
        for s in ("sk-abc", "ghp_", "op://", "AKIA", "aB3dE5gH7jK9"):
            self.assertNotIn(s, o["prompt"])
        self.assertIn("[redacted]", o["prompt"])

    def test_truncate(self):
        o = self.run_hook([u("word " * 1000)])
        self.assertIn("[…]", o["prompt"])

    def test_missing(self):
        self.assertIsNone(self.run_hook([u("x")], path=False))

    def test_custom_name(self):
        o = self.run_hook([u("hi there")], env={"OWNER_WORDS_NAME": "Alice"})
        self.assertTrue(o["prompt"].startswith('FROM ALICE, word for word: "hi there"'))
        self.assertIn("not by Alice", o["prompt"])

    def test_peer_message_skipped_for_sendmessage(self):
        entries = [u("old task"), u("<cross-session-message from=x>ping</cross-session-message>")]
        self.assertIsNone(self.run_hook(entries, tool="SendMessage", field="message"))
        self.assertIn('"old task"', self.run_hook(entries)["prompt"])

    def test_compaction_summary_skipped(self):
        o = self.run_hook([u("real words"), u("This session is being continued from a previous conversation ...")])
        self.assertIn('"real words"', o["prompt"])

    def test_none_found(self):
        self.assertIsNone(self.run_hook([u("<system-reminder>x</system-reminder>")]))


if __name__ == "__main__":
    unittest.main()
