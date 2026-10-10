"""Synthetic verified definitions for unit tests. Never written to the game catalog."""
from keystroke_lab.edit_dictionary import EditDictionary
def verified_dictionary():
    d=EditDictionary()
    d.edits={key:dict(e) for key,e in d.all.items() if e.get('confirmed') and e.get('suggest') and e['piece']=='wall'}
    return d
