-- Server-only entry points for the Edge Functions.
-- The Data API serves only the `api` schema (for every role, service_role included), so the Edge Functions cannot read
-- core / keystroke_trainer tables directly. These functions are their door: security definer, callable by service_role
-- only (revoked from public, anon and authenticated), and they take the player id the function verified from the JWT.

create or replace function api.svc_player(p_player uuid)
returns core.players language sql stable security definer set search_path = '' as $$
  select * from core.players where id = p_player;
$$;

-- Upsert validated attempts for one player (validation against edit_attempt.v1 happens in the ingest function).
-- Returns {"accepted": [ids], "foreign": [ids already owned by another player], "limited": bool}.
create or replace function api.svc_ingest(p_player uuid, p_session text, p_client text, p_rows jsonb,
                                          p_key_summary jsonb default null, p_hourly_limit integer default 5000)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare
  used integer;
  incoming integer := jsonb_array_length(p_rows);
  foreign_ids uuid[];
  accepted uuid[];
begin
  if p_player is null or not exists (select 1 from core.players where id = p_player and consent_upload) then
    raise exception 'upload consent not given';
  end if;
  select coalesce(sum(records), 0) into used from core.ingest_log
   where player_id = p_player and at > now() - interval '1 hour';
  if used + incoming > p_hourly_limit then
    return jsonb_build_object('accepted', '[]'::jsonb, 'foreign', '[]'::jsonb, 'limited', true);
  end if;

  select coalesce(array_agg(a.attempt_id), '{}') into foreign_ids
    from keystroke_trainer.attempts a
    join jsonb_array_elements(p_rows) r on a.attempt_id = (r->>'attempt_id')::uuid
   where a.player_id <> p_player;

  insert into core.sessions(player_id, id, map_id, client_version)
  values (p_player, left(p_session, 64), 'keystroke_trainer', left(coalesce(p_client, ''), 32))
  on conflict (player_id, id) do nothing;

  with rows as (
    select r from jsonb_array_elements(p_rows) r
     where not ((r->>'attempt_id')::uuid = any(foreign_ids))
  ), up as (
    insert into keystroke_trainer.attempts(attempt_id, player_id, session_id, piece, piece_evidence, outcome,
        suggested_edit_id, matched_edit_id, followed_suggestion, auto_label_confidence, side, far, aim_u, aim_v,
        t_edit_open, t_close, catalog_version, policy_version, record)
    select (r->>'attempt_id')::uuid, p_player, r->>'session_id', r->>'piece', r->>'piece_evidence', r->>'outcome',
           r->>'suggested_edit_id', r->>'matched_edit_id', (r->>'followed_suggestion')::boolean,
           (r->>'auto_label_confidence')::real, (r#>>'{context,side}')::smallint, (r#>>'{context,far}')::boolean,
           (r#>>'{context,aim_uv,0}')::real, (r#>>'{context,aim_uv,1}')::real,
           to_timestamp((r->>'t_edit_open')::double precision), to_timestamp((r->>'t_close')::double precision),
           (r->>'catalog_version')::integer, r->>'policy_version', r
      from rows
    on conflict (attempt_id) do update set record = excluded.record, outcome = excluded.outcome,
        matched_edit_id = excluded.matched_edit_id, followed_suggestion = excluded.followed_suggestion,
        auto_label_confidence = excluded.auto_label_confidence, received_at = now()
     where keystroke_trainer.attempts.player_id = p_player
    returning attempt_id
  )
  select coalesce(array_agg(attempt_id), '{}') into accepted from up;

  if array_length(accepted, 1) > 0 then
    insert into core.ingest_log(player_id, records) values (p_player, array_length(accepted, 1));
    perform keystroke_trainer.refresh_player_stats(p_player);
  end if;
  if p_key_summary is not null then
    insert into keystroke_trainer.key_summaries(player_id, session_id, counts, updated_at)
    values (p_player, left(p_session, 64), p_key_summary, now())
    on conflict (player_id, session_id) do update set counts = excluded.counts, updated_at = now();
  end if;
  return jsonb_build_object('accepted', to_jsonb(accepted), 'foreign', to_jsonb(foreign_ids), 'limited', false);
end $$;

create or replace function api.svc_jev_take(p_player uuid, p_limit integer)
returns boolean language sql security definer set search_path = '' as $$
  select core.jev_take(p_player, p_limit);
$$;

revoke execute on function api.svc_player(uuid), api.svc_ingest(uuid, text, text, jsonb, jsonb, integer),
  api.svc_jev_take(uuid, integer) from public, anon, authenticated;
grant execute on function api.svc_player(uuid), api.svc_ingest(uuid, text, text, jsonb, jsonb, integer),
  api.svc_jev_take(uuid, integer) to service_role;
grant usage on schema api to service_role;
