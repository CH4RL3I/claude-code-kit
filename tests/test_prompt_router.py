import json, os, subprocess, tempfile, threading, time, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from helpers import PY, script

HOOK = script("prompt-router", "scripts/prompt-router")
MEM = """# Memory
- [Billing Dashboard](project_billing.md) - invoice calculator tool, PLAN.md is source of truth
- [Acme Shop](project_acme.md) - acme.example website and project module
- [Rate Limit](feedback_rate_limit.md) - when hitting the rate limit use a screen wait loop
- [Secret Line](reference_secret.md) - token sk-abcdefghijklmnopqrstuvwxyz123456 for Acme website
- [Mobile Build](project_mobile.md) - TestFlight build upload group assignment
"""


class T(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.mem = os.path.join(d, "MEMORY.md")
        with open(self.mem, "w") as f:
            f.write(MEM)

    def run_hook(self, payload, env=None, raw=None):
        e = dict(os.environ, PROMPT_ROUTER_MEMORY=self.mem, PROMPT_ROUTER_EMBED="0",
                 PROMPT_ROUTER_NAMES_FILE="/nonexistent/names.txt",
                 PROMPT_ROUTER_CACHE=os.path.join(os.path.dirname(self.mem), "cache", "index.json"))
        for k in ("PROMPT_ROUTER_OFF", "PROMPT_ROUTER_NAMES"):
            e.pop(k, None)
        e.update(env or {})
        inp = raw if raw is not None else json.dumps(payload)
        r = subprocess.run([PY, HOOK], input=inp, capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0)
        if not r.stdout:
            return None
        o = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(o["hookEventName"], "UserPromptSubmit")
        self.assertLessEqual(len(o["additionalContext"]), 600)
        self.assertTrue(o["additionalContext"].startswith("prompt-router:"))
        return o["additionalContext"]

    def test_short_skipped(self):
        self.assertIsNone(self.run_hook({"prompt": "Billing?"}))

    def test_slash_and_bang_skipped(self):
        self.assertIsNone(self.run_hook({"prompt": "/review the billing invoice calculator please now"}))
        self.assertIsNone(self.run_hook({"prompt": "!ls the billing invoice calculator please now"}))

    def test_subagent_skipped(self):
        self.assertIsNone(self.run_hook({"prompt": "The billing invoice calculator must be merged",
                                         "agent_id": "abc"}))

    def test_off_switch(self):
        self.assertIsNone(self.run_hook({"prompt": "The billing invoice calculator must be merged"},
                                        env={"PROMPT_ROUTER_OFF": "1"}))

    def test_match(self):
        out = self.run_hook({"prompt": "The billing invoice calculator must be merged"})
        self.assertIn("project_billing.md", out)
        self.assertNotIn("project_acme.md", out)
        out = self.run_hook({"prompt": "Rate limit reached, what do we do now"})
        self.assertIn("feedback_rate_limit.md", out)

    def test_secret_line_never_injected(self):
        out = self.run_hook({"prompt": "Rebuild the acme website and project module quickly"})
        self.assertIn("project_acme.md", out)
        self.assertNotIn("reference_secret.md", out)
        self.assertNotIn("sk-abc", out)

    def test_no_match(self):
        self.assertIsNone(self.run_hook({"prompt": "What time is it right now in Lisbon actually?"}))

    def test_garbage_stdin(self):
        self.assertIsNone(self.run_hook(None, raw="not json {{{"))
        self.assertIsNone(self.run_hook(None, raw=""))
        self.assertIsNone(self.run_hook(None, raw="[1,2]"))
        self.assertIsNone(self.run_hook({"prompt": 42}))

    def test_keyword_match_basic(self):
        out = self.run_hook({"prompt": "Upload the TestFlight build for the mobile app"})
        self.assertIn("project_mobile.md", out)

    def test_names_boost(self):
        p = "billing invoices overview for me"
        self.assertIsNone(self.run_hook({"prompt": p}))
        out = self.run_hook({"prompt": p}, env={"PROMPT_ROUTER_NAMES": "billing"})
        self.assertIn("project_billing.md", out)

    def test_memory_autodetected_per_project(self):
        cfg = tempfile.mkdtemp()
        proj = os.path.join(cfg, "projects", "-work-app", "memory")
        os.makedirs(proj)
        with open(os.path.join(proj, "MEMORY.md"), "w") as f:
            f.write(MEM)
        e = {"PROMPT_ROUTER_MEMORY": "", "CLAUDE_CONFIG_DIR": cfg}
        out = self.run_hook({"prompt": "Upload the TestFlight build for the mobile app", "cwd": "/work/app/sub"}, env=e)
        self.assertIn("project_mobile.md", out)
        self.assertIsNone(self.run_hook({"prompt": "Upload the TestFlight build for the mobile app", "cwd": "/other"}, env=e))


CONCEPTS = [["build", "upload", "testflight", "release"],
            ["rate", "limit"], ["acme", "website", "shop"], ["weather", "rain"]]


def fake_vec(text):
    t = text.lower()
    return [float(sum(t.count(w) for w in g)) for g in CONCEPTS] + [0.001]


class FakeOllama(BaseHTTPRequestHandler):
    calls = []
    delay = 0.0

    def do_POST(self):
        n = int(self.headers["Content-Length"])
        body = json.loads(self.rfile.read(n))
        FakeOllama.calls.append(body["input"])
        time.sleep(FakeOllama.delay)
        out = json.dumps({"embeddings": [fake_vec(x) for x in body["input"]]}).encode()
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except OSError:   # client timed out and hung up: expected in the slow-server test
            pass

    def log_message(self, *a):
        pass


class Embed(T):
    """Semantic path with a fake local embedding server (no real model)."""

    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), FakeOllama)
        cls.url = "http://127.0.0.1:%d" % cls.srv.server_port
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def setUp(self):
        super().setUp()
        FakeOllama.calls = []
        FakeOllama.delay = 0.0
        self.cache = os.path.join(os.path.dirname(self.mem), "cache", "index.json")
        self.env = {"PROMPT_ROUTER_EMBED": "1", "PROMPT_ROUTER_OLLAMA": self.url,
                    "PROMPT_ROUTER_MODEL": "fake"}

    def hook(self, prompt, **extra):
        return self.run_hook({"prompt": prompt}, env=dict(self.env, **extra))

    def test_paraphrase_found_only_with_embeddings(self):
        p = "Ship a new release now and try it out please"
        self.assertIsNone(self.run_hook({"prompt": p}))            # keyword-only: no overlap
        out = self.hook(p)
        self.assertIn("project_mobile.md", out)
        self.assertNotIn("reference_secret.md", out)

    def test_unrelated_prompt_injects_nothing(self):
        self.assertIsNone(self.hook("What time is it right now in Lisbon actually?"))

    def test_keyword_hit_still_wins_with_embeddings(self):
        out = self.hook("The billing invoice calculator must be merged")
        self.assertIn("project_billing.md", out)

    def test_secret_line_never_embedded(self):
        self.hook("Rebuild the acme website and project module quickly")
        sent = " ".join(x for call in FakeOllama.calls for x in call)
        self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz123456", sent)
        with open(self.cache) as f:
            self.assertEqual(len(json.load(f)["lines"]), 4)    # 5 lines minus the secret one

    def test_cache_built_then_reused_then_invalidated(self):
        self.hook("Ship a new release now and try it out please")
        first = [c for c in FakeOllama.calls if len(c) > 1]
        self.assertEqual(sum(len(c) for c in first), 4)
        FakeOllama.calls = []
        self.hook("Ship a new release now and try it out please")
        self.assertEqual([c for c in FakeOllama.calls if len(c) > 1], [])   # only the prompt
        with open(self.mem, "a") as f:                                       # one line changes
            f.write("- [Weather](feedback_weather.md) - weather and rain notes for travel\n")
        FakeOllama.calls = []
        out = self.hook("Weather rain tomorrow in Hamburg actually?")
        self.assertEqual(len([c for c in FakeOllama.calls if "weather and rain" in c[0]]), 1)
        self.assertIn("feedback_weather.md", out)
        with open(self.cache) as f:
            self.assertEqual(len(json.load(f)["lines"]), 5)

    def test_model_change_drops_cache(self):
        self.hook("Ship a new release now and try it out please")
        FakeOllama.calls = []
        self.env["PROMPT_ROUTER_MODEL"] = "fake2"
        self.hook("Ship a new release now and try it out please")
        self.assertEqual(sum(len(c) for c in FakeOllama.calls if len(c) > 1), 4)

    def test_server_down_falls_back_to_keywords(self):
        env = dict(self.env, PROMPT_ROUTER_OLLAMA="http://127.0.0.1:9")
        out = self.run_hook({"prompt": "Upload the TestFlight build for the mobile app"}, env=env)
        self.assertIn("project_mobile.md", out)
        self.assertIsNone(self.run_hook({"prompt": "What time is it right now in Lisbon actually?"}, env=env))

    def test_slow_server_times_out_fast(self):
        FakeOllama.delay = 1.5
        t = time.time()
        out = self.hook("Upload the TestFlight build for the mobile app")
        self.assertLess(time.time() - t, 1.0)
        self.assertIn("project_mobile.md", out)

    def test_bad_server_answer_falls_back(self):
        out = self.run_hook({"prompt": "Upload the TestFlight build for the mobile app"},
                            env=dict(self.env, PROMPT_ROUTER_OLLAMA=self.url + "x"))
        self.assertIn("project_mobile.md", out)

    def test_embed_switch_off(self):
        out = self.hook("Ship a new release now and try it out please", PROMPT_ROUTER_EMBED="0")
        self.assertIsNone(out)
        self.assertEqual(FakeOllama.calls, [])

    def test_many_missing_lines_use_background_rebuild(self):
        with open(self.mem, "a") as f:
            for i in range(12):
                f.write("- [Extra %d](extra_%d.md) - line %d about Acme website\n" % (i, i, i))
        out = self.hook("Ship a new release now and try it out please")
        self.assertIsNone(out)                    # keyword fallback for this prompt
        for _ in range(40):                       # detached rebuild fills the cache
            time.sleep(0.1)
            try:
                with open(self.cache) as f:
                    if len(json.load(f)["lines"]) == 16:
                        break
            except Exception:
                pass
        with open(self.cache) as f:
            self.assertEqual(len(json.load(f)["lines"]), 16)
        self.assertIn("project_mobile.md", self.hook("Ship a new release now and try it out please"))


if __name__ == "__main__":
    unittest.main()
