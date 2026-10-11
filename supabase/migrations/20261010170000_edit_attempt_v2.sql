-- Evidence-aware outcomes; legacy 'completed' stays historical, never verified.
alter table keystroke_trainer.attempts drop constraint attempts_outcome_check;
alter table keystroke_trainer.attempts add constraint attempts_outcome_check
  check (outcome in ('completed','wrong_shape','reset','abandoned',
                    'selection_matched','confirm_observed','result_verified','unknown'));

-- Serialize concurrent upserts: an old retry must not overwrite a reviewed revision,
-- and even a service-role upsert cannot transfer another player's attempt.
create function keystroke_trainer.guard_attempt_revision()
returns trigger language plpgsql set search_path = '' as $$
begin
  if old.player_id <> new.player_id then raise exception 'attempt owner cannot change'; end if;
  -- Permit the first explicitly revisioned upgrade of an unrevisioned legacy row.
  if not (old.record ? 'record_revision') and new.record ? 'record_revision' then return new; end if;
  if coalesce((new.record->>'record_revision')::bigint, 1) <= coalesce((old.record->>'record_revision')::bigint, 1)
    then return old; end if;
  return new;
end $$;
create trigger guard_attempt_revision before update on keystroke_trainer.attempts
  for each row execute function keystroke_trainer.guard_attempt_revision();
revoke all on function keystroke_trainer.guard_attempt_revision() from public;

create or replace function keystroke_trainer.refresh_player_stats(p_player uuid default null)
returns integer language plpgsql security definer set search_path = '' as $$
declare n integer;
begin
  delete from keystroke_trainer.player_edit_stats s where p_player is null or s.player_id = p_player;
  insert into keystroke_trainer.player_edit_stats(player_id, edit_id, attempts, completed, followed, median_confirm_s, mean_travel)
  select a.player_id, coalesce(a.record->>'reviewed_edit_id', a.matched_edit_id),
    count(*),
    count(*) filter (where case when a.record ? 'review_result_confirmed'
      then a.record->>'review_result_confirmed' = 'true'
      else a.record->>'result_confirmed' = 'true' and a.record->>'result_evidence' in ('authored','reviewed') end),
    count(*) filter (where a.followed_suggestion),
    percentile_cont(0.5) within group (order by
      case when a.record->>'confirmation_evidence' in ('press','release')
        then (a.record->>'t_confirm')::double precision - (a.record->>'t_edit_open')::double precision end),
    avg(case when a.record->>'complete_observation' = 'true' then (a.record->>'travel')::real end)
  from keystroke_trainer.attempts a
  where (p_player is null or a.player_id = p_player)
    and coalesce(a.record->>'reviewed_edit_id', a.matched_edit_id) is not null
    and coalesce(a.record->>'label_status', 'auto') <> 'rejected'
    and (a.piece_evidence in ('observed','authored') or
         (a.record->>'review_result_confirmed' = 'true' and a.record->>'reviewed_piece' = a.piece))
    and not exists (select 1 from keystroke_trainer.labels l where l.attempt_id = a.attempt_id and l.status = 'rejected')
  group by a.player_id, coalesce(a.record->>'reviewed_edit_id', a.matched_edit_id);
  get diagnostics n = row_count;
  return n;
end $$;
