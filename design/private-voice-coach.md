# Private companion voice coach

The agent runs in the Windows companion, not in Verse or an ElevenLabs hosted
conversational-agent session. No microphone is opened. Audio goes to the local
Windows playback device only; it is never sent to Fortnite voice chat or a
shared island audio device. Use headphones to avoid microphone/speaker bleed.
Public island players do not automatically get this companion service. Do not
distribute creator API credentials; a public service still requires a separately
approved authenticated proxy and per-player consent/quotas.

## Behavior

- Funny, brainrot and competitive one-liners, randomized without immediate repeats.
- Player/profile-scoped Jev finding counts, with thoughtful LLM wording only after
  at least three supported possible-slip findings or five complete edit observations.
- Edit commentary describes observed coverage of suggested tiles, not confirmed
  execution success, accuracy, skill rank or whether an alternative edit was wrong.
- Existing local guide state suppresses speech during detected building/editing.
  The coach otherwise waits for a 5–25 second input pause; it stays silent when
  Fortnite is not focused. Resuming inputs interrupts speech. No random victory,
  death, CTF or zone claim is inferred from inputs. Those richer match reactions
  need authenticated, player-scoped outcome events before they can be enabled.
- A profile change clears pending findings. Mute, focus loss, changed profile or
  resumed input after a request prevents stale audio playback.

## Credit limits (this new voice agent only)

- Minimum 90 seconds between speech attempts; at most 40 per UTC day.
- At most 1,200 new ElevenLabs characters per UTC day, including failed requests.
- At most eight LLM requests per UTC day, at least five minutes apart, maximum
  100 output tokens per request. Existing Jev/text-overlay budgets are separate.
- Cached WAVs are reused without TTS calls. Cache identity includes voice, text,
  model, settings and audio format. Speech uses Eleven Flash v2.5, PCM 22.05 kHz.
- SQLite reservations persist through restarts and are atomic across processes.
  These are request/character caps, not a dollar guarantee or account-wide cap.
- No automatic retries or startup synthesis. Missing services fail quietly;
  unavailable LLM wording uses the evidence template. Missing TTS means silence.

## Controls

In the Windows repository's `companion` folder, double-click `mute_coach.cmd` or
`enable_coach.cmd`. The updated overlay reads changes while running. Defaults
are disabled until explicitly enabled on the creator PC.

Advanced: `python -m keystroke_lab.voice_agent enable --style brainrot` (or
`funny`, `competitive`, `mixed`). `status` shows settings; `check` performs
non-generating credential/voice/model access checks. `demo` spends at most one
short TTS request unless cached; `llm-check` spends one bounded LLM request.

Credentials use the existing external `.env`, process environment or Windows user
environment. The coach defaults to the configured Claude model. NIM is available
with `KT_VOICE_LLM_PROVIDER=nim`, `NVIDIA_API_KEY`, `NVIDIA_MODEL_ID`; it is not
claimed to be configured or faster without a successful test. No secrets are
written to the repository or diagnostics. Only allowlisted aggregate counters
reach the LLM; ElevenLabs receives the short sentence to speak. Raw keys, binds,
player IDs, traces and images do not leave through this integration.

Local configuration, budget, health status and audio cache live in ignored
`companion/.runtime/voice/`. Deleting the budget resets local cost accounting;
do not do this to bypass the cap. The cache may contain spoken personal summary
sentences; it is local-only and can be removed separately from `budget.sqlite3`.

No locked edit-guide file is modified. Network/TTS work runs on its own worker,
not on capture or rendering threads. The small keyboard-overlay integration only
reports activity and completed Jev findings, and closes the voice worker on exit.
