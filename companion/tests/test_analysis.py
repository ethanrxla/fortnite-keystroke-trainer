import json
import tempfile
import unittest
from pathlib import Path

from keystroke_lab import actions, analysis, binds as binds_cmd, drills
from keystroke_lab.habits import Habits
from keystroke_lab.jev_client import JevClient, choice_question
from keystroke_lab.keyboard_overlay import KeyTracker

PROFILE = dict(drills.DEFAULT_BINDS)
PROFILE.update({"sprint": "1", "tab_edit": "tab"})


class FakeJev:
    available = True
    shadow = False

    def __init__(self, choice="slip", confidence=0.95):
        self.calls = 0
        self.choice, self.confidence = choice, confidence

    def decide(self, state, questions, **kwargs):
        self.calls += 1
        return {q: {"choice": self.choice, "confidence": self.confidence, "probabilities": {k: (.95 if k==self.choice else .05/3) for k in analysis.INTENT_OPTIONS}} for q in questions}


class FullProfileTests(unittest.TestCase):
    def test_wasd_and_sprint_are_not_strays(self):
        t = KeyTracker(PROFILE)
        for key in "wasd1":
            self.assertEqual(t.press(key, 100.0 + ord(key))[0], "ok", key)

    def test_shared_key_lists_every_action(self):
        t = KeyTracker({"ramp": "space", "crouch": "space", "jump": "e"})
        self.assertEqual(t.names["space"], "ramp/crouch")

    def test_habit_promotion_needs_presses_and_minutes(self):
        h = Habits(path=None, min_presses=3, min_minutes=2)
        t = KeyTracker({"wall": "q"}, habits=h)
        self.assertEqual(t.press("x", 0.0)[0], "unmapped")
        t.release("x")
        self.assertEqual(t.press("x", 1.0)[0], "unmapped")
        t.release("x")
        self.assertEqual(t.press("x", 61.0)[0], "habit")

    def test_catalogue_defaults_cover_every_action(self):
        self.assertTrue(set(actions.DEFAULTS) <= set(drills.DEFAULT_BINDS))
        self.assertIn("sprint", drills.DEFAULT_BINDS)

    def test_apply_choice_reports_shared_key_and_slot_alias(self):
        b = {"crouch": "space"}
        self.assertEqual(binds_cmd.apply_choice(b, "ramp", "space"), ["crouch"])
        binds_cmd.apply_choice(b, "slot1", "o")
        self.assertEqual(b["swap_weapon"], "o")


class AnalyzerTests(unittest.TestCase):
    def make(self, jev, llm=lambda *a: ""):
        t = KeyTracker(PROFILE)
        return analysis.Analyzer(t, jev=jev, llm=llm)

    def feed(self, a, n=3, key="caps_lock"):
        for i in range(n):
            a.note(key, float(i))
            a.add_stray(key, float(i), [("tab", "inventory")], {"reviewed_correction": True})

    def test_waits_for_enough_strays(self):
        a = self.make(FakeJev())
        self.feed(a, 2)
        self.assertFalse(a.ready(100.0))
        self.feed(a, 1)
        self.assertTrue(a.ready(100.0))

    def test_one_batched_call_and_cache(self):
        jev = FakeJev()
        a = self.make(jev)
        self.feed(a, 3)
        a.resolve(100.0)
        self.assertEqual(jev.calls, 1)
        self.feed(a, 3)
        a.resolve(200.0)
        self.assertEqual(jev.calls, 1)  # identical (key, neighbours) served from cache
        self.assertEqual(a.stats["cache_hits"], 3)

    def test_low_confidence_falls_back_to_local_guess(self):
        a = self.make(FakeJev(choice="deliberate", confidence=0.5))
        self.feed(a, 3)
        findings = a.resolve(100.0)
        self.assertTrue(all(f["intent"] == "insufficient_evidence" and f["confidence"] < 0.8 for f in findings))

    def test_template_names_the_keys(self):
        a = self.make(FakeJev())
        self.feed(a, 3)
        a.resolve(100.0)
        text = a.tip(100.0)
        self.assertIn("caps_lock", text)
        self.assertIn("Possible input slip", text)

    def test_llm_is_rate_limited_and_optional(self):
        calls = []
        a = self.make(FakeJev(), llm=lambda s, b: calls.append(s) or "reworded tip")
        self.feed(a, 3)
        a.resolve(100.0)
        self.assertEqual(a.tip(100.0), "reworded tip")
        self.assertNotEqual(a.tip(110.0), "reworded tip")  # inside the cooldown: template text, no second call
        self.assertEqual(len(calls), 1)
        self.assertNotIn("ms_ago", json.dumps(calls[0]))  # counts only, no timing or typed text

    def test_no_key_means_no_call(self):
        jev = JevClient(key="")
        self.assertFalse(jev.available)
        self.assertIsNone(jev.decide({}, {'case': choice_question('Classify evidence', {'insufficient_evidence':'unknown'})}))

    def test_old_history_is_not_sent_as_recent_and_all_verified_binds_are_sent(self):
        from keystroke_lab.bind_profiles import Binding, BindProfile
        p = BindProfile('C:/private-player-folder/keybinds.json', 1, (Binding('reload', ('mouse_middle',), 'combat', True),
                               Binding('crouch', ('mouse_x2',), 'move', True),
                               Binding('emote', ('alt_l',), 'ui', True),
                               Binding('swap_weapon', ('o',), verified=False)))
        posted = []
        c = JevClient(key='test', post=lambda body: posted.append(body) or {'answers': {}})
        a = analysis.Analyzer(KeyTracker(p), jev=c)
        a.note('f', 1.)
        a.add_stray('g', 100., [])
        a.resolve(100.)
        self.assertEqual(posted[0]['state']['events'][0]['just_before'], [])
        self.assertNotIn('private-player-folder', json.dumps(posted))
        self.assertEqual({b['action'] for b in posted[0]['state']['verified_bindings']}, {'reload', 'crouch', 'emote'})

    def test_broker_deferral_preserves_queue_without_caching_a_fake_decision(self):
        class Broker:
            def key(self, *args): return 'key'
            def acquire(self, *args): return None
        c = JevClient(key='test', post=lambda _: self.fail('network'), broker=Broker())
        a = self.make(c)
        self.feed(a)
        self.assertEqual(a.resolve(100.), [])
        self.assertEqual(len(a.queue), 3)
        self.assertEqual(a.cache, {})
        self.assertEqual(a.stats['jev_calls'], 0)

    def test_failed_request_is_not_cached_and_pause_invalidates_evidence(self):
        c = JevClient(key='test', post=lambda _: None)
        a = self.make(c)
        self.feed(a)
        a.resolve(100.)
        self.assertEqual(a.cache, {})
        a.note('f', 101.)
        a.invalidate(a.profile_revision, a.profile_id)
        self.assertEqual(a.recent, [])
        self.assertEqual(a.findings, [])


class JevClientTests(unittest.TestCase):
    def test_parses_answers_and_counts_usage(self):
        posted = {}

        def post(body):
            posted.update(body)
            return {"answers": {"q": {"choice": "a", "confidence": 0.9, "probabilities": {"a": 0.9, "b": 0.1}}},
                    "usage": {"input_tokens": 10, "output_tokens": 2}}

        c = JevClient(key="k", post=post)
        out = c.decide({"x": 1}, {"q": {"type": "choice", "instructions": "i", "criteria": {"a": "", "b": ""}}})
        self.assertEqual(out["q"]["choice"], "a")
        self.assertEqual(c.tokens, {"input": 10, "output": 2})
        self.assertEqual(posted["model"], "jev-1.13.0")

    def test_retries_once_on_429_then_gives_up_cleanly(self):
        class Boom(Exception):
            code = 429

        def post(body):
            raise Boom()

        c = JevClient(key="k", post=post, sleep=lambda s: None)
        self.assertIsNone(c.decide({}, {'case': choice_question('Classify evidence', {'insufficient_evidence':'unknown'})}))
        self.assertEqual(c.calls, 2)

    def test_call_cap(self):
        c = JevClient(key="k", post=lambda b: {"answers": {}}, max_calls=1)
        c.decide({}, {'case': choice_question('Classify evidence', {'insufficient_evidence':'unknown'})})
        self.assertFalse(c.available)


if __name__ == "__main__":
    unittest.main()


class BindServerTests(unittest.TestCase):
    def test_get_and_authenticated_post(self):
        import urllib.error
        import urllib.request
        from keystroke_lab import bind_server
        with tempfile.TemporaryDirectory() as d:
            binds_file = Path(d) / "keybinds.json"
            server = bind_server.start(lambda: {"sprint": "1"}, lambda: ["x"], [], binds_file=binds_file, port=0, secret="s3cret")
            port = server.server_address[1]
            try:
                got = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/binds"))
                self.assertEqual(got["binds"]["sprint"], "1")
                self.assertEqual(got["habits"], ["x"])
                req = urllib.request.Request(f"http://127.0.0.1:{port}/binds", json.dumps({"action": "sprint", "key": "2"}).encode(),
                                             {"Content-Type": "application/json"})
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(req)
                self.assertEqual(ctx.exception.code, 403)
                ctx.exception.close()
                req.add_header("X-KT-Token", "s3cret")
                self.assertTrue(json.load(urllib.request.urlopen(req))["ok"])
                self.assertEqual(__import__("keystroke_lab.bind_profiles", fromlist=["ProfileStore"]).ProfileStore(binds_file).snapshot.primary()["sprint"], "2")
            finally:
                server.shutdown()
                server.server_close()


class IgnoredKeyTests(unittest.TestCase):
    def test_print_screen_is_not_game_input(self):
        h = Habits(path=None, min_presses=1, min_minutes=1)
        t = KeyTracker({"wall": "q"}, habits=h)
        self.assertEqual(t.press("print_screen", 0.0)[0], "ignore")
        self.assertEqual(h.data, {})          # never learned as a habit
        self.assertEqual(t.press("cmd", 1.0)[0], "ignore")
        self.assertEqual(t.press("media_volume_up", 2.0)[0], "ignore")


class AutostartTests(unittest.TestCase):
    def test_game_detection_reads_tasklist_text(self):
        from keystroke_lab import autostart
        self.assertTrue(autostart.game_running(lambda: "FortniteClient-Win64-Shipping.exe  1234 Console"))
        self.assertFalse(autostart.game_running(lambda: "INFO: No tasks are running which match the specified criteria."))
        self.assertFalse(autostart.game_running(lambda: (_ for _ in ()).throw(OSError("no tasklist"))))

    def test_watcher_starts_once_and_stops_with_the_game(self):
        from keystroke_lab import autostart

        class Child:
            def __init__(self):
                self.alive, self.terminated = True, False

            def poll(self):
                return None if self.alive else 0

            def terminate(self):
                self.alive, self.terminated = False, True

        states = iter([True, True, True, False, False])   # game opens, stays, closes
        children, ticks = [], {"n": 0}

        def launch():
            children.append(Child())
            return children[-1]

        def lister():
            return "FortniteClient-Win64-Shipping.exe" if next(states) else ""

        autostart.watch(adopt=lambda: False, lister=lister, launch=launch, sleep=lambda s: ticks.update(n=ticks["n"] + 1),
                        stop=lambda: ticks["n"] >= 5)
        self.assertEqual(len(children), 1)           # one overlay for one game session
        self.assertTrue(children[0].terminated)      # ended when the game closed

    def test_restarts_overlay_if_it_dies_while_game_runs(self):
        from keystroke_lab import autostart

        class Child:
            def __init__(self):
                self.alive = True

            def poll(self):
                return None if self.alive else 1

            def terminate(self):
                self.alive = False

        made = []

        def launch():
            made.append(Child())
            if len(made) == 1:
                made[0].alive = False                # first overlay crashes at once
            return made[-1]

        ticks = {"n": 0}
        autostart.watch(adopt=lambda: False, lister=lambda: "FortniteClient-Win64-Shipping.exe", launch=launch,
                        sleep=lambda s: ticks.update(n=ticks["n"] + 1), stop=lambda: ticks["n"] >= 3)
        self.assertGreaterEqual(len(made), 2)


class TasklistTruncationTests(unittest.TestCase):
    def test_truncated_image_name_is_detected(self):
        from keystroke_lab import autostart
        # What tasklist really prints: the image name cut to 25 characters.
        self.assertTrue(autostart.game_running(lambda: "FortniteClient-Win64-Ship    25272 Console    1  4,484,584 K"))
