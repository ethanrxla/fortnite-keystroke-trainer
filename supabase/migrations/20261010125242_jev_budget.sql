-- Atomic per-player daily Jev budget for the jev-proxy Edge Function (service role only).
create or replace function core.jev_take(p_player uuid, p_limit integer)
returns boolean language plpgsql security definer set search_path = '' as $$
declare used integer;
begin
  insert into core.jev_usage(player_id, day, calls) values (p_player, current_date, 1)
  on conflict (player_id, day) do update set calls = core.jev_usage.calls + 1
  returning calls into used;
  if used > p_limit then
    update core.jev_usage set calls = calls - 1 where player_id = p_player and day = current_date;
    return false;
  end if;
  return true;
end $$;
revoke execute on function core.jev_take(uuid, integer) from public, anon, authenticated;
grant execute on function core.jev_take(uuid, integer) to service_role;
