# PR4 review follow-up

Integrated current origin/main and resolved guide positioning using main's stats slot.
Preserved projection/route drawing and attempt evidence code. Keyboard capture no longer
requires edit-state.json. Chat toggle is repeat-safe and focus-aware; pause remains explicit.
Stats render only in stats_panel; keyboard status/tip restored. Keyboard scale restored.
Capture control writes only on state/session change, with session-associated pause state.
Legacy completed samples cannot train or score verified policy examples. Collector summary
counts verified results; v2 confirm joins use v2 outcome names without certifying results.
Malformed capture ids are skipped. Removed duplicate images and unused habit construction.
Legacy unrevisioned rows accept their first explicitly revisioned update; versioned retries
still cannot overwrite newer rows. Foreign-id filtering already exists in svc_ingest,
including an owner condition on conflict: the reported missing filter was not reproduced.

Validation: 319 companion tests passed on Windows with existing vision dependencies and
hydrated fixtures before the optional-fixture skip documentation adjustment. No running
companion was restarted and no game input sent. SQL changes remain undeployed and require
staging database verification. Native InputHud overlap requires a live island check; this
change consolidates companion statistics only. Live chat/focus/DPI and route stability
remain manual acceptance items, not claimed fixed by unit tests alone.
