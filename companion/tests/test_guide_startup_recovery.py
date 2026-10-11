import unittest
from unittest.mock import patch
from keystroke_lab import autostart


class Process:
    def __init__(self, code=None):self.code=code;self.stopped=False
    def poll(self):return self.code
    def terminate(self):self.stopped=True;self.code=0


class GuideRecoveryTests(unittest.TestCase):
    def test_restored_pipeline_and_recorder_initialize_together(self):
        try:
            from keystroke_lab.edit_window import ContextPipeline
            from keystroke_lab.bind_profiles import ProfileStore
            from keystroke_lab.attempt_recorder import default_matcher
        except ImportError as exc:
            if exc.name in ('cv2','numpy'):
                self.skipTest('optional local vision dependencies missing')
            raise
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            pipeline=ContextPipeline(ProfileStore(Path(folder)/'binds.json'))
            try:
                matcher=default_matcher(pipeline.advisor.dictionary)
                self.assertEqual(matcher('wall',[4],None),'window_center')
            finally:
                pipeline.advisor.close()

    def test_guide_crash_restarts_without_keyboard_restart(self):
        keyboard=Process();old=Process(1);replacement=Process();calls=[]
        group=autostart._Group(keyboard,Process(),guide=old,
                              guide_launch=lambda:(calls.append(1) or replacement))
        with patch.object(autostart,'mutex_running',return_value=False):
            group.maintain(10);group.maintain(11)
        self.assertEqual(len(calls),1)
        self.assertIs(group.guide,replacement)
        self.assertFalse(keyboard.stopped)

    def test_existing_guide_is_not_duplicated(self):
        calls=[]
        group=autostart._Group(Process(),Process(),guide_launch=lambda:calls.append(1))
        with patch.object(autostart,'mutex_running',return_value=True):group.maintain(10)
        self.assertEqual(calls,[])

    def test_adopted_keyboard_still_recovers_missing_guide(self):
        guide=Process();group=autostart._Adopted()
        with patch.object(autostart,'mutex_running',return_value=False),patch.object(autostart,'spawn_component',return_value=guide) as spawn:
            group.maintain(10);group.maintain(11)
        spawn.assert_called_once()
        group.terminate()
        self.assertTrue(guide.stopped)

    def test_stopping_group_stops_guide_even_with_dead_keyboard(self):
        guide=Process();group=autostart._Group(Process(1),Process(),guide=guide)
        group.terminate()
        self.assertTrue(guide.stopped)
