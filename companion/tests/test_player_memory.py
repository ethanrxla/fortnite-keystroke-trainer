import unittest,tempfile
from pathlib import Path
from keystroke_lab.player_profiles import PlayerProfiles
from keystroke_lab.bind_profiles import ProfileStore
class PlayerMemoryTests(unittest.TestCase):
 def test_separate_players_persist_and_switch(self):
  with tempfile.TemporaryDirectory() as d:
   active=ProfileStore(Path(d)/'active.json');memory=PlayerProfiles(Path(d)/'players.json')
   active.update('sprint',['1'],'move');a=memory.save('A',active.snapshot)
   active.update('sprint',['shift'],'move');b=memory.save('B',active.snapshot)
   self.assertNotEqual(a.profile_id,b.profile_id)
   reread=PlayerProfiles(memory.path)
   self.assertEqual(reread.load('A').primary()['sprint'],'1')
   self.assertEqual(reread.load('B').primary()['sprint'],'shift')
   before=active.snapshot.revision;active.activate(reread.load('A'))
   self.assertGreater(active.snapshot.revision,before)
   self.assertEqual(ProfileStore(active.path).snapshot,active.snapshot)
 def test_empty_name_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):PlayerProfiles(Path(d)/'p.json').save(' ',ProfileStore(Path(d)/'active.json').snapshot)
