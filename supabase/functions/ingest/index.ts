// deno-lint-ignore-file no-explicit-any
// POST /functions/v1/ingest   Authorization: Bearer <the player's anonymous session token>
// Body: {"session_id": "...", "client_version": "...", "attempts": [edit_attempt.v1, ...],
//        "key_summary": {"ok": n, "unmapped": n, "keys": {...}} (optional)}
// Reply: {"accepted": [attempt ids], "rejected": [{"attempt_id", "errors"}]}
//
// The only write path for players. It checks the caller's identity and consent, validates every record against the
// shared JSON Schema, rate-limits per player, and upserts idempotently on attempt_id (a retry never duplicates).
// Records whose attempt_id already belongs to another player are rejected.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import schema from "../_shared/edit_attempt.v1.json" with { type: "json" };
import { errors } from "../_shared/validate.ts";

const MAX_PER_REQUEST = 200;
const MAX_PER_HOUR = 5000;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const url = Deno.env.get("SUPABASE_URL")!;
  const service = createClient(url, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, { auth: { persistSession: false } });
  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const { data: who, error: authError } = await service.auth.getUser(token);
  if (authError || !who?.user) return json({ error: "not signed in" }, 401);
  const player = who.user.id;

  const core = service.schema("core");
  const { data: me } = await core.from("players").select("consent_upload, consent_frames").eq("id", player).maybeSingle();
  if (!me?.consent_upload) return json({ error: "upload consent not given" }, 403);

  let body: any;
  try { body = await req.json(); } catch { return json({ error: "body must be JSON" }, 400); }
  const attempts: any[] = Array.isArray(body?.attempts) ? body.attempts : [];
  const sessionId = String(body?.session_id ?? "").slice(0, 64);
  if (!sessionId || attempts.length === 0) return json({ error: "session_id and attempts required" }, 400);
  if (attempts.length > MAX_PER_REQUEST) return json({ error: `at most ${MAX_PER_REQUEST} attempts per request` }, 413);

  const since = new Date(Date.now() - 3600_000).toISOString();
  const { data: recent } = await core.from("ingest_log").select("records").eq("player_id", player).gte("at", since);
  const used = (recent ?? []).reduce((n: number, r: any) => n + r.records, 0);
  if (used + attempts.length > MAX_PER_HOUR) return json({ error: "hourly limit reached, retry later" }, 429);

  const accepted: string[] = [];
  const rejected: { attempt_id: unknown; errors: string[] }[] = [];
  const rows: any[] = [];
  for (const a of attempts) {
    const problems = errors(a, schema);
    if (a?.session_id !== sessionId) problems.push("$.session_id: does not match the request");
    if (!me.consent_frames && Array.isArray(a?.frames) && a.frames.length) problems.push("$.frames: frame consent not given");
    if (problems.length) { rejected.push({ attempt_id: a?.attempt_id, errors: problems.slice(0, 10) }); continue; }
    const ctx = a.context ?? {};
    rows.push({
      attempt_id: a.attempt_id, player_id: player, session_id: a.session_id, piece: a.piece,
      piece_evidence: a.piece_evidence, outcome: a.outcome, suggested_edit_id: a.suggested_edit_id ?? null,
      matched_edit_id: a.matched_edit_id ?? null, followed_suggestion: a.followed_suggestion ?? null,
      auto_label_confidence: a.auto_label_confidence ?? null, side: ctx.side ?? null, far: ctx.far ?? null,
      aim_u: ctx.aim_uv?.[0] ?? null, aim_v: ctx.aim_uv?.[1] ?? null,
      t_edit_open: new Date(a.t_edit_open * 1000).toISOString(), t_close: new Date(a.t_close * 1000).toISOString(),
      catalog_version: a.catalog_version ?? null, policy_version: a.policy_version ?? null, record: a,
    });
  }

  if (rows.length) {
    // An attempt id owned by someone else is never overwritten.
    const ids = rows.map((r) => r.attempt_id);
    const kt = service.schema("keystroke_trainer");
    const { data: taken } = await kt.from("attempts").select("attempt_id, player_id").in("attempt_id", ids);
    const foreign = new Set((taken ?? []).filter((t: any) => t.player_id !== player).map((t: any) => t.attempt_id));
    const mine = rows.filter((r) => !foreign.has(r.attempt_id));
    for (const id of foreign) rejected.push({ attempt_id: id, errors: ["$.attempt_id: already used"] });
    await core.from("sessions").upsert({ player_id: player, id: sessionId, map_id: "keystroke_trainer",
      client_version: String(body.client_version ?? "").slice(0, 32) }, { onConflict: "player_id,id", ignoreDuplicates: true });
    const { error } = await kt.from("attempts").upsert(mine, { onConflict: "attempt_id" });
    if (error) return json({ error: "database write failed", detail: error.message }, 500);
    accepted.push(...mine.map((r) => r.attempt_id));
    await core.from("ingest_log").insert({ player_id: player, records: mine.length });
    await kt.rpc("refresh_player_stats", { p_player: player });
  }
  if (body?.key_summary && typeof body.key_summary === "object") {
    await service.schema("keystroke_trainer").from("key_summaries").upsert(
      { player_id: player, session_id: sessionId, counts: body.key_summary, updated_at: new Date().toISOString() },
      { onConflict: "player_id,session_id" });
  }
  return json({ accepted, rejected });
});
