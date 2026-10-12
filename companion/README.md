# Companion verification

Run `python -m unittest discover -s tests -t .` from this directory.
Vision tests require NumPy and OpenCV plus the images under tests/fixtures/edit-vision.
Run `git lfs pull` to hydrate fixtures. A .vision_packages folder is optional; a normal
Python environment containing the dependencies also works. Missing optional vision
packages or recorded images are reported as skips, not successful vision validation.
The Windows integration pass used the existing local .vision_packages on PYTHONPATH.
Always report skip counts. A passing suite does not replace a live DPI/focus/playtest.

The keyboard works independently of the edit observer. Enter opens/sends chat; Escape
cancels it, and focus loss clears chat state. F8 pause survives focus loss. No timeout
resumes collection during typing. Edit evidence retains its own profile/session gates.
The independent stats panel owns the statistics surface; keyboard status/tips remain
visible. The edit guide reserves the panel slot and retains projected boxes and routes.
