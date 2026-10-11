// deno-lint-ignore-file no-explicit-any
// POST /functions/v1/ingest   Authorization: Bearer <the player's anonymous session token>
// Body: {"session_id": "...", "client_version": "...", "attempts": [edit_attempt.v1, ...],
//        "key_summary": {"verdicts": {...}, "keys": {...}} (optional, counts only)}
// Reply: {"accepted": [attempt ids], "rejected": [{"attempt_id", "errors"}]}
//
// The only write path for players. Verifies the caller from their JWT, validates every record against the shared JSON
// Schema (same file as the companion), then hands the valid rows to api.svc_ingest, a service-role-only database
// function that checks consent, rate-limits per player, refuses attempt ids owned by another player and upserts
// idempotently on attempt_id (a retry never duplicates). Map schemas stay unexposed; this is their only write door.
import { createClient } from "npm:@supabase/supabase-js@2.45.4";
import schema from "../_shared/edit_attempt.v1.json" with { type: "json" };
import schemaV2 from "../_shared/edit_attempt.v2.json" with { type: "json" };
import { errors, keySummaryErrors } from "../_shared/validate.ts";

const MAX_PER_REQUEST = 200;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const service = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false }, db: { schema: "api" } });
  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const { data: who, error: authError } = await service.auth.getUser(token);
  if (authError || !who?.user) return json({ error: "not signed in" }, 401);
  const player = who.user.id;

  const { data: me } = await service.rpc("svc_player", { p_player: player });
  if (!me?.consent_upload) return json({ error: "upload consent not given" }, 403);

  let body: any;
  try { body = await req.json(); } catch { return json({ error: "body must be JSON" }, 400); }
  const attempts: any[] = Array.isArray(body?.attempts) ? body.attempts : [];
  const sessionId = String(body?.session_id ?? "").slice(0, 64);
  if (!sessionId || attempts.length === 0) return json({ error: "session_id and attempts required" }, 400);
  if (attempts.length > MAX_PER_REQUEST) return json({ error: `at most ${MAX_PER_REQUEST} attempts per request` }, 413);

  const rejected: { attempt_id: unknown; errors: string[] }[] = [];
  const rows: any[] = [];
  for (const a of attempts) {
    const problems = errors(a, a?.schema === "edit_attempt.v2" ? schemaV2 : schema);
    if (Array.isArray(a?.frames) && a.frames.length) problems.push("$.frames: image upload disabled");
    if (a?.schema === "edit_attempt.v2" && (a.aim_trace?.length || a.selection_trace?.length || a.gesture_trace?.length))
      problems.push("$: upload summaries only, not raw traces");
    if (a?.session_id !== sessionId) problems.push("$.session_id: does not match the request");
    if (!me.consent_frames && Array.isArray(a?.frames) && a.frames.length) problems.push("$.frames: frame consent not given");
    if (problems.length) rejected.push({ attempt_id: a?.attempt_id, errors: problems.slice(0, 10) });
    else rows.push(a);
  }
  const summary = body?.key_summary && typeof body.key_summary === "object" ? body.key_summary : null;
  const summaryProblems=keySummaryErrors(summary);
  if(summaryProblems.length)return json({error:summaryProblems[0]},400);
  if (!rows.length && !summary) return json({ accepted: [], rejected });

  const { data, error } = await service.rpc("svc_ingest", {
    p_player: player, p_session: sessionId, p_client: String(body.client_version ?? "").slice(0, 32),
    p_rows: rows, p_key_summary: summary,
  });
  if (error) return json({ error: "database write failed", detail: error.message }, 500);
  if (data?.limited) return json({ error: "hourly limit reached, retry later" }, 429);
  for (const id of data?.foreign ?? []) rejected.push({ attempt_id: id, errors: ["$.attempt_id: already used"] });
  return json({ accepted: data?.accepted ?? [], rejected });
});
