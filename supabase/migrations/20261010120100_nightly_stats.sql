-- Nightly per-player edit stats (also refreshed for one player after each ingest by the Edge Function).
create extension if not exists pg_cron;
select cron.schedule('kt-refresh-player-stats', '17 3 * * *', $$select keystroke_trainer.refresh_player_stats(null)$$);
