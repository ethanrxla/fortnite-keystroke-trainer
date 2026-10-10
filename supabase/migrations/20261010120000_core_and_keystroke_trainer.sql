-- Player-data backend for RXLA maps. One shared `core` schema, one private schema per map, and a small `api` schema
-- that is the only thing exposed through the Data API (config.toml [api] schemas = ["api"]).
--
-- Encapsulation: map schemas (keystroke_trainer.*) are never exposed. Clients read through `api` functions and write
-- only through the `ingest` Edge Function, which validates every record against shared/schemas/edit_attempt.v1.json.
-- Identity: each companion install signs in anonymously (no account, no login screen); auth.uid() is the player id.
-- Privacy: no Epic account ids, display names or e-mails are stored. Raw keystrokes and frames need separate opt-ins.

create schema if not exists core;
create schema if not exists keystroke_trainer;
create schema if not exists api;

-- ---------------------------------------------------------------- core: shared across maps
create table core.maps (
  id          text primary key,
  name        text not null,
  created_at  timestamptz not null default now()
);
insert into core.maps(id, name) values ('keystroke_trainer', 'RXLA Keystroke Trainer') on conflict do nothing;

create table core.players (
  id                uuid primary key references auth.users(id) on delete cascade,
  created_at        timestamptz not null default now(),
  consent_upload    boolean not null default false,
  consent_frames    boolean not null default false,
  consent_raw_keys  boolean not null default false,
  consent_at        timestamptz
);

create table core.reviewers (
  user_id  uuid primary key references auth.users(id) on delete cascade,
  added_at timestamptz not null default now()
);

create table core.sessions (
  player_id       uuid not null references core.players(id) on delete cascade,
  id              text not null,
  map_id          text not null references core.maps(id),
  first_seen      timestamptz not null default now(),
  client_version  text,
  primary key (player_id, id)
);

create table core.edit_catalog (
  map_id        text not null references core.maps(id),
  version       integer not null,
  data          jsonb not null,
  published_at  timestamptz not null default now(),
  primary key (map_id, version)
);

create table core.policies (
  id            text primary key,                 -- e.g. 'wall-2026-10-10-blend'
  map_id        text not null references core.maps(id),
  piece         text not null check (piece in ('wall','floor','cone','ramp')),
  method        text not null,                    -- jev_prior | blend | personal
  data          jsonb not null,                   -- {edits:[...], priors:{"ub,vb,side,far":[...]}}
  metrics       jsonb,                            -- eval_edit_policy.py scores
  active        boolean not null default false,
  published_at  timestamptz not null default now()
);
create unique index policies_one_active on core.policies(map_id, piece) where active;

create table core.jev_usage (
  player_id  uuid not null references core.players(id) on delete cascade,
  day        date not null default current_date,
  calls      integer not null default 0,
  primary key (player_id, day)
);

create table core.ingest_log (
  player_id    uuid not null references core.players(id) on delete cascade,
  at           timestamptz not null default now(),
  records      integer not null
);
create index ingest_log_recent on core.ingest_log(player_id, at);

-- ---------------------------------------------------------------- keystroke_trainer: private to this map
create table keystroke_trainer.attempts (
  attempt_id             uuid primary key,
  player_id              uuid not null references core.players(id) on delete cascade,
  session_id             text not null,
  piece                  text not null check (piece in ('wall','floor','cone','ramp','unknown')),
  piece_evidence         text not null,
  outcome                text not null check (outcome in ('completed','wrong_shape','reset','abandoned')),
  suggested_edit_id      text,
  matched_edit_id        text,
  followed_suggestion    boolean,
  auto_label_confidence  real,
  side                   smallint,
  far                    boolean,
  aim_u                  real,
  aim_v                  real,
  t_edit_open            timestamptz not null,
  t_close                timestamptz not null,
  catalog_version        integer,
  policy_version         text,
  record                 jsonb not null,
  received_at            timestamptz not null default now()
);
create index attempts_player_time on keystroke_trainer.attempts(player_id, t_edit_open);
create index attempts_situation on keystroke_trainer.attempts(piece, side, far, matched_edit_id);

create table keystroke_trainer.labels (
  attempt_id  uuid not null references keystroke_trainer.attempts(attempt_id) on delete cascade,
  at          timestamptz not null default now(),
  status      text not null check (status in ('approved','rejected','relabelled')),
  edit_id     text,
  reviewer    uuid references auth.users(id) on delete set null,
  note        text,
  primary key (attempt_id, at)
);

create table keystroke_trainer.player_edit_stats (
  player_id           uuid not null references core.players(id) on delete cascade,
  edit_id             text not null,
  attempts            integer not null default 0,
  completed           integer not null default 0,
  followed            integer not null default 0,
  median_confirm_s    real,
  mean_travel         real,
  factor              real not null default 1.0,
  updated_at          timestamptz not null default now(),
  primary key (player_id, edit_id)
);

create table keystroke_trainer.key_summaries (
  player_id   uuid not null references core.players(id) on delete cascade,
  session_id  text not null,
  counts      jsonb not null,          -- {"ok": n, "unmapped": n, "repeat": n, "keys": {"c": n, ...}} (no order/timing)
  updated_at  timestamptz not null default now(),
  primary key (player_id, session_id)
);

-- ---------------------------------------------------------------- row level security (deny by default)
alter table core.maps enable row level security;
alter table core.players enable row level security;
alter table core.reviewers enable row level security;
alter table core.sessions enable row level security;
alter table core.edit_catalog enable row level security;
alter table core.policies enable row level security;
alter table core.jev_usage enable row level security;
alter table core.ingest_log enable row level security;
alter table keystroke_trainer.attempts enable row level security;
alter table keystroke_trainer.labels enable row level security;
alter table keystroke_trainer.player_edit_stats enable row level security;
alter table keystroke_trainer.key_summaries enable row level security;

create policy maps_read on core.maps for select using (true);
create policy catalog_read on core.edit_catalog for select using (true);
create policy policies_read on core.policies for select using (active);
create policy players_own on core.players for select using (id = auth.uid());
create policy sessions_own on core.sessions for select using (player_id = auth.uid());
create policy attempts_own on keystroke_trainer.attempts for select using (player_id = auth.uid());
create policy stats_own on keystroke_trainer.player_edit_stats for select using (player_id = auth.uid());
create policy keys_own on keystroke_trainer.key_summaries for select using (player_id = auth.uid());
create policy labels_own on keystroke_trainer.labels for select using (
  exists (select 1 from keystroke_trainer.attempts a where a.attempt_id = labels.attempt_id and a.player_id = auth.uid()));
-- No insert/update/delete policies: writes happen only in security-definer functions and the ingest Edge Function.

-- ---------------------------------------------------------------- api: the public interface
create or replace function core.is_reviewer() returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from core.reviewers r where r.user_id = auth.uid());
$$;

create or replace function api.register(upload boolean, frames boolean default false, raw_keys boolean default false)
returns core.players language plpgsql security definer set search_path = '' as $$
declare me core.players;
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  insert into core.players(id, consent_upload, consent_frames, consent_raw_keys, consent_at)
  values (auth.uid(), upload, upload and frames, upload and raw_keys, now())
  on conflict (id) do update set consent_upload = excluded.consent_upload, consent_frames = excluded.consent_frames,
    consent_raw_keys = excluded.consent_raw_keys, consent_at = now()
  returning * into me;
  return me;
end $$;

create or replace function api.me() returns core.players
language sql stable security definer set search_path = '' as $$
  select * from core.players where id = auth.uid();
$$;

create or replace function api.delete_my_data() returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'not signed in'; end if;
  delete from core.players where id = auth.uid();          -- cascades to every map schema
  return true;
end $$;

create or replace function api.my_edit_stats()
returns setof keystroke_trainer.player_edit_stats
language sql stable security definer set search_path = '' as $$
  select * from keystroke_trainer.player_edit_stats where player_id = auth.uid() order by edit_id;
$$;

create or replace function api.active_policies(p_map text default 'keystroke_trainer')
returns setof core.policies language sql stable security definer set search_path = '' as $$
  select * from core.policies where map_id = p_map and active;
$$;

create or replace function api.latest_catalog(p_map text default 'keystroke_trainer')
returns core.edit_catalog language sql stable security definer set search_path = '' as $$
  select * from core.edit_catalog where map_id = p_map order by version desc limit 1;
$$;

create or replace function api.review_queue(p_limit integer default 50, p_status text default 'auto')
returns setof keystroke_trainer.attempts language plpgsql stable security definer set search_path = '' as $$
begin
  if not core.is_reviewer() then raise exception 'reviewers only'; end if;
  return query
    select a.* from keystroke_trainer.attempts a
    where (p_status = 'all') or not exists (select 1 from keystroke_trainer.labels l where l.attempt_id = a.attempt_id)
    order by a.t_edit_open desc limit least(p_limit, 500);
end $$;

create or replace function api.label_attempt(p_attempt uuid, p_status text, p_edit text default null, p_note text default null)
returns keystroke_trainer.labels language plpgsql security definer set search_path = '' as $$
declare row keystroke_trainer.labels;
begin
  if not core.is_reviewer() then raise exception 'reviewers only'; end if;
  insert into keystroke_trainer.labels(attempt_id, status, edit_id, reviewer, note)
  values (p_attempt, p_status, p_edit, auth.uid(), p_note) returning * into row;
  return row;
end $$;

-- Recompute one player's per-edit stats from their attempts (also run nightly for everyone, see below).
create or replace function keystroke_trainer.refresh_player_stats(p_player uuid default null)
returns integer language plpgsql security definer set search_path = '' as $$
declare n integer;
begin
  delete from keystroke_trainer.player_edit_stats s where p_player is null or s.player_id = p_player;
  insert into keystroke_trainer.player_edit_stats(player_id, edit_id, attempts, completed, followed, median_confirm_s, mean_travel)
  select a.player_id, coalesce(a.matched_edit_id, a.suggested_edit_id),
         count(*), count(*) filter (where a.outcome = 'completed'), count(*) filter (where a.followed_suggestion),
         percentile_cont(0.5) within group (order by extract(epoch from (a.t_close - a.t_edit_open))),
         avg((a.record->>'travel')::real)
  from keystroke_trainer.attempts a
  where (p_player is null or a.player_id = p_player) and coalesce(a.matched_edit_id, a.suggested_edit_id) is not null
    and not exists (select 1 from keystroke_trainer.labels l where l.attempt_id = a.attempt_id and l.status = 'rejected')
  group by a.player_id, coalesce(a.matched_edit_id, a.suggested_edit_id);
  get diagnostics n = row_count;
  return n;
end $$;

-- Privileges: the API roles see only the api schema; map schemas stay private.
revoke all on schema core, keystroke_trainer from anon, authenticated;
grant usage on schema api to anon, authenticated;
revoke execute on all functions in schema api from public;
grant execute on function api.active_policies(text), api.latest_catalog(text) to anon, authenticated;
grant execute on function api.register(boolean, boolean, boolean), api.me(), api.delete_my_data(), api.my_edit_stats(),
  api.review_queue(integer, text), api.label_attempt(uuid, text, text, text) to authenticated;
-- service_role (Edge Functions, admin tools) keeps full access.
grant usage on schema core, keystroke_trainer to service_role;
grant all on all tables in schema core, keystroke_trainer to service_role;
grant execute on all functions in schema core, keystroke_trainer to service_role;
