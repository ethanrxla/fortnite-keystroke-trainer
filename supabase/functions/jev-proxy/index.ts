// deno-lint-ignore-file no-explicit-any
// POST /functions/v1/jev-proxy   Authorization: Bearer <the player's anonymous session token>
// Body: the Jev System One request {state, model, questions}. Reply: Jev's response, unchanged.
//
// Keeps JEV_API_KEY on the server (the companion repo is public), allows only the pinned model and 1-8 questions,
// and charges each player's daily budget atomically (api.svc_jev_take -> core.jev_take). Set the secret with:
//   npx supabase secrets set JEV_API_KEY=...
import { createClient } from "npm:@supabase/supabase-js@2.45.4";

const JEV_URL = "https://api.typesafe.ai/v1/systemone";
const MODELS = new Set(["jev-1.13.0"]);
const DAILY_LIMIT = Number(Deno.env.get("JEV_DAILY_LIMIT") ?? "200");
const MAX_BODY = 64_000;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const key = Deno.env.get("JEV_API_KEY");
  if (!key) return json({ error: "Jev is not configured on the server" }, 503);
  const service = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false }, db: { schema: "api" } });
  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "");
  const { data: who, error } = await service.auth.getUser(token);
  if (error || !who?.user) return json({ error: "not signed in" }, 401);

  const raw = await req.text();
  if (raw.length > MAX_BODY) return json({ error: "request too large" }, 413);
  let body: any;
  try { body = JSON.parse(raw); } catch { return json({ error: "body must be JSON" }, 400); }
  const questions = body?.questions;
  const count = questions && typeof questions === "object" ? Object.keys(questions).length : 0;
  if (!MODELS.has(body?.model) || count < 1 || count > 8 || typeof body?.state !== "object") {
    return json({ error: "expected {state, model: jev-1.13.0, questions: 1-8}" }, 400);
  }
  // Only `api` is served by the Data API: the budget goes through the service-only api.svc_jev_take.
  const { data: allowed } = await service.rpc("svc_jev_take", { p_player: who.user.id, p_limit: DAILY_LIMIT });
  if (!allowed) return json({ error: "daily Jev budget used" }, 429);

  const upstream = await fetch(JEV_URL, {
    method: "POST",
    headers: { "authorization": `Bearer ${key}`, "content-type": "application/json" },
    body: JSON.stringify({ state: body.state, model: body.model, questions }),
  });
  const text = await upstream.text();
  const headers: Record<string, string> = { "content-type": "application/json" };
  const retry = upstream.headers.get("retry-after");
  if (retry) headers["retry-after"] = retry;
  return new Response(text, { status: upstream.status, headers });
});
