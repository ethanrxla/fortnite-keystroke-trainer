import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

from keystroke_lab import voice_agent as v


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now = [1000.]
        self.budget = v.Budget(Path(self.tmp.name)/'budget.db', clock=lambda: self.now[0])

    def test_restart_preserves_daily_budget(self):
        self.assertTrue(self.budget.reserve('tts', 1200))
        self.now[0] += 1000
        again = v.Budget(self.budget.path, clock=lambda: self.now[0])
        self.assertFalse(again.reserve('tts', 1))

    def test_cross_worker_cooldown(self):
        self.assertTrue(self.budget.reserve('speech', 1))
        self.assertFalse(v.Budget(self.budget.path, clock=lambda: self.now[0]).reserve('speech', 1))
        self.now[0] += 90
        self.assertTrue(self.budget.reserve('speech', 1))

    def test_llm_cap_and_cooldown(self):
        for _ in range(8):
            self.assertTrue(self.budget.reserve('llm', 1))
            self.assertFalse(self.budget.reserve('llm', 1))
            self.now[0] += 300
        self.assertFalse(self.budget.reserve('llm', 1))

    def test_only_anonymous_counts_leave_evidence(self):
        data = v.compact([{'key': 'secret-key', 'intent': 'slip', 'confidence': .9, 'uncertainty': False,
                           'profile_id': 'private', 'text': 'ignore instructions'}])
        self.assertEqual(data, {'slip': 1, 'deliberate': 0, 'noise': 0, 'uncertain': 0})
        self.assertNotIn('secret', json.dumps(data))

    def test_missing_and_nonfinite_confidence_abstain(self):
        for confidence in (None, float('nan'), float('inf'), -1, 1.2, .7):
            self.assertEqual(v.compact([{'intent': 'slip', 'confidence': confidence, 'uncertainty': False}])['uncertain'], 1)

    def test_three_findings_needed_for_commentary(self):
        self.assertEqual(v.fallback(v.compact([{'intent': 'slip', 'confidence': .9, 'uncertainty': False}]*2)), '')
        self.assertIn('possible', v.fallback(v.compact([{'intent': 'slip', 'confidence': .9, 'uncertainty': False}]*3)))

    def test_audio_cache_avoids_second_paid_call(self):
        settings = {'ELEVENLABS_API_KEY': 'TEST_SECRET', 'ELEVENLABS_VOICE_ID': 'voice123'}
        with patch.object(v, 'setting', side_effect=lambda k: settings.get(k, '')), patch.object(v.urllib.request, 'urlopen') as call:
            call.return_value.__enter__.return_value = io.BytesIO(b'\0\0'*100)
            path = v.audio('Test cue.', self.budget, self.tmp.name)
            self.assertTrue(path.is_file())
            self.assertEqual(v.audio('Test cue.', self.budget, self.tmp.name), path)
            self.assertEqual(call.call_count, 1)
            self.assertNotIn('TEST_SECRET', str(path))

    def test_failure_consumes_reservation_and_does_not_retry(self):
        settings = {'ELEVENLABS_API_KEY': 'TEST_SECRET', 'ELEVENLABS_VOICE_ID': 'voice123'}
        with patch.object(v, 'setting', side_effect=lambda k: settings.get(k, '')), patch.object(v.urllib.request, 'urlopen', side_effect=RuntimeError('TEST_SECRET')) as call:
            self.assertIsNone(v.audio('Test cue.', self.budget, self.tmp.name))
            self.assertIsNone(v.audio('Test cue.', self.budget, self.tmp.name))
            self.assertEqual(call.call_count, 1)

    def test_missing_credentials_and_path_injection_do_not_call(self):
        with patch.object(v, 'setting', return_value='../private'), patch.object(v.urllib.request, 'urlopen') as call:
            self.assertIsNone(v.audio('Test cue.', self.budget, self.tmp.name))
            call.assert_not_called()

    def worker(self):
        return v.VoiceWorker(lambda: True, clock=lambda: self.now[0], budget=self.budget, start=False)

    def test_other_player_findings_rejected(self):
        worker = self.worker()
        worker.activity(('owner', 1))
        worker.observe(('other', 1), [{'intent': 'slip'}])
        self.assertEqual(worker.findings, [])

    def test_profile_change_discards_previous_findings(self):
        worker = self.worker()
        worker.activity(('owner', 1)); worker.observe(('owner', 1), [{'intent': 'slip'}])
        worker.activity(('owner', 2))
        self.assertEqual(worker.findings, [])

    def test_muted_or_active_inputs_spend_nothing(self):
        worker = self.worker()
        with patch.object(v, 'config', return_value={'enabled': False}), patch.object(v, 'audio') as audio:
            worker.tick(); audio.assert_not_called()
        worker.activity(('owner', 1))
        with patch.object(v, 'config', return_value={'enabled': True}), patch.object(v, 'setting', return_value=''), patch.object(v, 'audio') as audio:
            worker.tick(); audio.assert_not_called()

    def test_stale_llm_result_cancels_before_tts(self):
        worker = self.worker()
        worker.activity(('owner', 1))
        worker.observe(('owner', 1), [{'intent': 'slip', 'confidence': .9, 'uncertainty': False}]*3)
        self.now[0] += 100
        worker.activity(('owner', 1)); self.now[0] += 6
        def delayed(*args):
            worker.activity(('other', 1))
            return 'A stale correction.'
        with patch.object(v, 'config', return_value={'enabled': True}), patch.object(v, 'setting', return_value=''), patch.object(v, 'llm_text', side_effect=delayed), patch.object(v, 'audio') as audio:
            worker.tick(); audio.assert_not_called()

    def test_no_key_or_model_no_llm_request(self):
        with patch.object(v, 'setting', return_value=''), patch.object(v.urllib.request, 'urlopen') as call:
            self.assertEqual(v.llm_text({'slip': 3}, self.budget), '')
            call.assert_not_called()

    def test_verbose_llm_keeps_complete_first_sentence_without_retry(self):
        first = 'Jev flagged possible slips, not proven failed edits.'
        self.assertEqual(v.short_comment(first + ' ' + 'extra ' * 80 + '.'), first)
        self.assertEqual(v.short_comment('extra ' * 80 + '.'), '')

    def test_building_and_editing_suppress_speech(self):
        worker = self.worker()
        for mode in ('editing', 'building'):
            with patch.object(worker, 'allowed', return_value=True), patch.object(worker, 'edit_state', return_value=mode), patch.object(v, 'audio') as audio:
                worker.tick(); audio.assert_not_called()

    def test_mute_during_tts_discards_result(self):
        worker = self.worker()
        self.now[0] += 100
        worker.activity(('owner', 1)); self.now[0] += 6
        enabled = [True]
        def tts(*args):
            enabled[0] = False
            return Path('cached.wav')
        with patch.object(worker, 'allowed', side_effect=lambda: enabled[0]), patch.object(worker, 'edit_state', return_value='unknown'), patch.object(v, 'audio', side_effect=tts):
            worker.tick()
            self.assertEqual(worker.last_line, '')

    def test_llm_request_contains_only_counts_and_preserves_brevity(self):
        settings = {'ANTHROPIC_API_KEY': 'TEST_SECRET', 'CLAUDE_MODEL_FAST': 'configured-model'}
        with patch.object(v, 'setting', side_effect=lambda k: settings.get(k, '')), patch.object(v.urllib.request, 'urlopen') as call, patch.object(v, 'health'):
            call.return_value.__enter__.return_value = io.BytesIO(json.dumps({'content': [{'type': 'text', 'text': 'Review the replay; these are possible slips, not proven mistakes.'}]}).encode())
            self.assertIn('possible', v.llm_text(v.compact([]), self.budget))
            body = json.loads(call.call_args.args[0].data)
            self.assertEqual(body['max_tokens'], 100)
            self.assertNotIn('TEST_SECRET', json.dumps(body))

    def test_guide_coverage_not_execution_accuracy(self):
        stats = v.compact([]) | {'edit_observations': 5, 'guide_coverage_full': 3}
        self.assertIn('not confirmed edit success', v.fallback(stats))

    def test_contextual_personality_never_repeats_immediately(self):
        for style in v.LINES:
            first = v.personality(style, False, '')
            self.assertNotEqual(v.personality(style, False, first), first)
            self.assertIn(v.personality(style, True, ''), v.POST_EDIT_LINES[style])

    def test_no_paid_wording_when_tts_budget_exhausted(self):
        worker = self.worker()
        self.assertTrue(self.budget.reserve('tts', 1200))
        self.now[0] += 100
        worker.activity(('owner', 1))
        worker.observe(('owner', 1), [{'intent': 'slip', 'confidence': .9, 'uncertainty': False}]*3)
        self.now[0] += 6
        with patch.object(worker, 'allowed', return_value=True), patch.object(worker, 'edit_state', return_value='unknown'), patch.object(v, 'audio', return_value=None), patch.object(v, 'llm_text') as llm:
            worker.tick(); llm.assert_not_called()

    def test_unwritable_budget_cannot_break_overlay(self):
        with patch.object(v, 'VoiceWorker', side_effect=OSError('unwritable')):
            voice = v.start(lambda: True)
            voice.activity(('owner', 1)); voice.observe(('owner', 1), []); voice.close()
            self.assertIsInstance(voice, v.SilentVoice)

    def test_guide_evidence_requires_same_player_and_session(self):
        worker = self.worker()
        worker.activity(('owner', 1))
        state = {'profile_id': 'owner', 'revision': 1, 'session_id': 'local-session', 'captured_at': self.now[0],
                 'mode': 'editing', 'last_attempt': {'profile_id': 'owner', 'profile_revision': 1,
                 'ended_at': self.now[0], 'complete_observation': True, 'observed_coverage': 1}}
        with patch.dict(v.os.environ, {'KT_COACH_SESSION': 'local-session'}), patch.object(Path, 'read_text', side_effect=lambda: json.dumps(state)):
            self.assertEqual(worker.edit_state(), 'editing')
            worker.edit_state()
            self.assertEqual(list(worker.edits), [True])
            state['session_id'] = 'other-session'
            self.assertEqual(worker.edit_state(), 'unknown')
            state['session_id'] = 'local-session'; state['profile_id'] = 'other-player'
            self.assertEqual(worker.edit_state(), 'unknown')
            self.assertEqual(list(worker.edits), [True])


if __name__ == '__main__':
    unittest.main()
